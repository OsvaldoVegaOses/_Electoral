import io
import re
import uuid
import logging
import secrets
import pandas as pd
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Voter, Election, User
from app.schemas import VoterCreate, VoterResponse, VoterBulkUploadResult
from app.auth import get_current_user, log_audit, check_election_access, sanitize_formula_injection
from app.rut_validator import validate_rut, format_rut, clean_rut, mask_rut

logger = logging.getLogger("theogen.voters")

router = APIRouter(prefix="/elections/{election_id}/voters", tags=["Padrón Electoral y Votantes"])

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

# MED-02: Límite máximo de archivo de carga masiva (10 MB)
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def _escape_like(value: str) -> str:
    """MED-03: Escapa caracteres especiales de LIKE/ILIKE"""
    return value.replace("%", r"\%").replace("_", r"\_")


@router.get("", response_model=List[VoterResponse])
def list_voters(
    election_id: int,
    estado: Optional[str] = None,
    q: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """Lista los votantes de una elección con verificación anti-IDOR"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=False)

    query = db.query(Voter).filter(Voter.election_id == election_id)
    if estado:
        query = query.filter(Voter.estado == estado)
    if q:
        safe_q = _escape_like(q)  # MED-03
        query = query.filter(
            (Voter.nombre.ilike(f"%{safe_q}%")) |
            (Voter.rut.ilike(f"%{safe_q}%")) |
            (Voter.curso.ilike(f"%{safe_q}%")) |
            (Voter.correo.ilike(f"%{safe_q}%"))
        )
    return query.order_by(Voter.id.asc()).offset(skip).limit(limit).all()

@router.post("", response_model=VoterResponse, status_code=status.HTTP_201_CREATED)
def create_voter(
    election_id: int,
    voter_in: VoterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Agrega manualmente un elector al padrón con verificación anti-IDOR"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=True)

    if election.estado != "Borrador":
        raise HTTPException(
            status_code=409,
            detail="El padrón electoral se encuentra congelado tras la apertura de la elección."
        )

    # Validar RUT
    if not validate_rut(voter_in.rut):
        raise HTTPException(status_code=400, detail="El RUT ingresado no es matemáticamente válido (Módulo 11)")

    formatted = format_rut(voter_in.rut)
    cleaned = clean_rut(voter_in.rut)

    # Validar duplicados de RUT en la misma elección
    existing = db.query(Voter).filter(
        Voter.election_id == election_id,
        (Voter.rut == formatted) | (Voter.rut == cleaned) | (Voter.rut_normalizado == cleaned)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"El elector con RUT {formatted} ya se encuentra registrado")

    # Validar formato correo si viene provisto
    if voter_in.correo and not re.match(EMAIL_REGEX, voter_in.correo):
        raise HTTPException(status_code=400, detail="El formato del correo electrónico es inválido")

    clean_nombre = sanitize_formula_injection(voter_in.nombre.strip())
    clean_curso = sanitize_formula_injection(voter_in.curso.strip()) if voter_in.curso else None
    clean_familia = sanitize_formula_injection(voter_in.familia_id.strip()) if voter_in.familia_id else None

    token = str(uuid.uuid4())
    voter = Voter(
        rut=formatted,
        rut_normalizado=cleaned,
        nombre=clean_nombre,
        curso=clean_curso,
        correo=voter_in.correo.strip().lower() if voter_in.correo else None,
        familia_id=clean_familia,
        token_votacion=token,
        estado="Pendiente",
        election_id=election_id
    )
    db.add(voter)
    log_audit(
        db,
        accion="Agregó elector",
        detalle=f"Elector {voter.nombre} (RUT: {mask_rut(voter.rut)}) añadido al padrón",
        usuario=current_user.email,
        school_id=election.school_id,
        commit=False
    )
    db.commit()
    db.refresh(voter)
    return voter


@router.post("/upload-excel", response_model=VoterBulkUploadResult)
async def upload_voters_file(
    election_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Módulo 2: Carga masiva de padrón desde archivo Excel (.xlsx) o CSV.
    Valida:
    - Lectura en streaming por chunks (máx 10 MB) para prevenir saturación de memoria RAM
    - Rechazo de formato .xls legado por motivos de seguridad
    - Tipos de datos forzados a string (dtype=str) para evitar pérdida de ceros a la izquierda
    - Neutralización de inyección de fórmulas CSV/Excel (CSV Formula Injection)
    - RUT con Módulo 11 chileno
    - Correo electrónico válido
    - Duplicados en el archivo y contra la BD
    - Registro de auditoría atómico con la inserción del lote
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=True)

    if election.estado != "Borrador":
        raise HTTPException(
            status_code=409,
            detail="El padrón electoral se encuentra congelado tras la apertura de la elección."
        )

    # MED-02: Streaming de archivo en chunks para evitar saturación de memoria RAM
    CHUNK_SIZE = 1024 * 1024  # 1 MB por chunk
    total_bytes = 0
    buffer = io.BytesIO()

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El archivo excede el tamaño máximo permitido de {MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB."
            )
        buffer.write(chunk)

    buffer.seek(0)
    filename = file.filename.lower() if file.filename else ""

    # Rechazar explícitamente formato .xls legado por motivos de seguridad e interoperabilidad
    if filename.endswith(".xls"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El formato .xls legado no está permitido por motivos de seguridad e interoperabilidad. Por favor guarde o exporte su archivo en formato .xlsx moderno o .csv."
        )

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(buffer, dtype=str)
        elif filename.endswith(".xlsx"):
            df = pd.read_excel(buffer, dtype=str)
        else:
            raise HTTPException(status_code=400, detail="Formato de archivo no soportado. Debe ser .xlsx o .csv")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el archivo: {str(e)}")

    # Normalizar nombres de columnas a minúsculas sin acentos
    df.columns = [str(col).strip().lower() for col in df.columns]

    # Mapeo de columnas tolerante
    col_rut = next((c for c in df.columns if "rut" in c), None)
    col_nombre = next((c for c in df.columns if "nombre" in c), None)
    col_curso = next((c for c in df.columns if "curso" in c or "grado" in c), None)
    col_correo = next((c for c in df.columns if "correo" in c or "email" in c or "mail" in c), None)
    col_familia = next((c for c in df.columns if "familia" in c), None)

    if not col_rut or not col_nombre:
        raise HTTPException(
            status_code=400,
            detail="El archivo debe contener al menos las columnas 'RUT' y 'Nombre'. Columnas opcionales: 'Curso', 'Correo', 'Familia ID'."
        )

    # Cargar RUTs existentes en la base de datos para esta elección
    existing_ruts_db = {clean_rut(r[0]) for r in db.query(Voter.rut).filter(Voter.election_id == election_id).all()}

    ruts_in_file = set()
    voters_to_insert = []
    errores = []

    for idx, row in df.iterrows():
        fila_num = idx + 2  # Asumiendo fila 1 cabeceras
        raw_rut = str(row.get(col_rut, '')).strip()
        raw_nombre = str(row.get(col_nombre, '')).strip()
        raw_curso = str(row.get(col_curso, '')).strip() if col_curso and pd.notna(row.get(col_curso)) else ""
        raw_correo = str(row.get(col_correo, '')).strip() if col_correo and pd.notna(row.get(col_correo)) else ""
        raw_familia = str(row.get(col_familia, '')).strip() if col_familia and pd.notna(row.get(col_familia)) else ""

        # Ignorar filas vacías
        if not raw_rut or raw_rut.lower() == 'nan':
            continue

        if not raw_nombre or raw_nombre.lower() == 'nan':
            errores.append({"fila": fila_num, "rut": raw_rut, "motivo": "Falta el nombre del elector"})
            continue

        # 1. Validar RUT chileno
        if not validate_rut(raw_rut):
            errores.append({"fila": fila_num, "rut": raw_rut, "motivo": "RUT inválido (error en dígito verificador)"})
            continue

        cleaned = clean_rut(raw_rut)
        formatted = format_rut(raw_rut)

        # 2. Validar duplicado en el mismo archivo
        if cleaned in ruts_in_file:
            errores.append({"fila": fila_num, "rut": formatted, "motivo": "RUT duplicado dentro del archivo"})
            continue
        ruts_in_file.add(cleaned)

        # 3. Validar duplicado en la base de datos
        if cleaned in existing_ruts_db:
            errores.append({"fila": fila_num, "rut": formatted, "motivo": "RUT ya existe en el padrón de esta elección"})
            continue

        # 4. Validar correo si viene
        if raw_correo and raw_correo.lower() != 'nan':
            if not re.match(EMAIL_REGEX, raw_correo):
                errores.append({"fila": fila_num, "rut": formatted, "motivo": f"Formato de correo inválido: {raw_correo}"})
                continue
        else:
            raw_correo = None

        # Sanitizar inyección de fórmulas CSV en campos alfanuméricos
        clean_nombre = sanitize_formula_injection(raw_nombre)
        clean_curso = sanitize_formula_injection(raw_curso) if raw_curso and raw_curso.lower() != 'nan' else None
        clean_familia = sanitize_formula_injection(raw_familia) if raw_familia and raw_familia.lower() != 'nan' else None

        # Preparar voter
        token = str(uuid.uuid4())
        voters_to_insert.append(Voter(
            rut=formatted,
            rut_normalizado=cleaned,
            nombre=clean_nombre,
            curso=clean_curso,
            correo=raw_correo.lower() if raw_correo else None,
            familia_id=clean_familia,
            token_votacion=token,
            estado="Pendiente",
            election_id=election_id
        ))

    # Guardar en base de datos con auditoría atómica en la misma transacción
    if voters_to_insert:
        db.add_all(voters_to_insert)
        log_audit(
            db,
            accion="Subió padrón",
            detalle=f"Se cargaron {len(voters_to_insert)} electores desde archivo '{file.filename}'. {len(errores)} filas con error.",
            usuario=current_user.email,
            school_id=election.school_id,
            commit=False
        )
        db.commit()

    return {
        "total_leidos": len(df),
        "total_validos": len(voters_to_insert),
        "total_errores": len(errores),
        "errores": errores,
        "insertados": len(voters_to_insert)
    }

@router.post("/generate-tokens")
def generate_all_tokens(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Genera tokens UUID únicos para todos los electores de la elección con validación anti-IDOR"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=True)

    if election.estado != "Borrador":
        raise HTTPException(
            status_code=409,
            detail="No se pueden generar o modificar credenciales tras la apertura de la elección."
        )

    voters = db.query(Voter).filter(Voter.election_id == election_id, Voter.token_votacion.is_(None)).all()
    count = 0
    for v in voters:
        v.token_votacion = str(uuid.uuid4())
        count += 1

    log_audit(
        db,
        accion="Generó credenciales",
        detalle=f"Generados {count} tokens UUID de votación",
        usuario=current_user.email,
        school_id=election.school_id,
        commit=False
    )
    db.commit()
    return {"mensaje": f"Se generaron {count} credenciales únicas.", "generados": count}


@router.get("/simulate-email-dispatch")
def simulate_email_dispatch(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """
    Módulo 4: Simulación de despacho de credenciales con validación anti-IDOR.
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=False)


    voters = db.query(Voter).filter(Voter.election_id == election_id).limit(50).all()
    emails = []

    # Enlace genérico seguro sin credenciales expuestas en la URL
    vote_url = "http://localhost:5173/votar"

    for v in voters:
        html_preview = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px;">
            <div style="background-color: #0d233a; color: white; padding: 15px; border-radius: 6px; text-align: center;">
                <h2 style="margin: 0;">TheoGen Electoral</h2>
                <p style="margin: 5px 0 0 0; font-size: 12px; color: #94a3b8;">Participación transparente y verificable</p>
            </div>
            <div style="padding: 20px 0;">
                <p>Estimado/a <strong>{v.nombre}</strong> (RUT: {v.rut}):</p>
                <p>Se encuentra habilitado/a para emitir su sufragio en el proceso: <strong>{election.nombre}</strong>.</p>
                <div style="background-color: #f8fafc; border-left: 4px solid #1e40af; padding: 12px; margin: 15px 0;">
                    <p style="margin: 0; font-size: 13px;"><strong>Tu Token Único de Votación:</strong></p>
                    <code style="font-size: 14px; font-weight: bold; color: #0f172a;">[Credencial confidencial entregada por canal seguro]</code>
                </div>
                <p style="text-align: center; margin: 25px 0;">
                    <a href="{vote_url}" style="background-color: #1e40af; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                        Ingresar a la Sala de Votación (/votar)
                    </a>
                </p>
                <p style="font-size: 11px; color: #64748b;">Este voto es personal, secreto e irreversible. No comparta su credencial con terceros.</p>
            </div>
        </div>
        """
        emails.append({
            "voter_id": v.id,
            "nombre": v.nombre,
            "rut": v.rut,
            "correo": v.correo or "sin_correo@demo.cl",
            "token": "[protegido por secreto electoral]",
            "enlace_votacion": vote_url,
            "preview_html": html_preview,
            "estado": v.estado
        })

    return {
        "eleccion": election.nombre,
        "total_destinatarios": len(emails),
        "correos_simulados": emails
    }

@router.get("/template")
def download_padron_template():
    """Genera y descarga una plantilla Excel modelo con columnas RUT, Nombre, Curso, Correo, Familia ID"""
    df = pd.DataFrame([
        {"RUT": "16.234.567-2", "Nombre": "Francisca Silva", "Curso": "1° Básico A", "Correo": "fsilva@ejemplo.cl", "Familia ID": "FAM-101"},
        {"RUT": "17.123.456-7", "Nombre": "Camila Vergara", "Curso": "2° Básico B", "Correo": "cvergara@ejemplo.cl", "Familia ID": "FAM-102"},
        {"RUT": "18.345.678-4", "Nombre": "Felipe Errázuriz", "Curso": "3° Básico A", "Correo": "ferrazuriz@ejemplo.cl", "Familia ID": "FAM-103"}
    ])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Padron")
    output.seek(0)

    headers = {"Content-Disposition": 'attachment; filename="plantilla_padron_theogen.xlsx"'}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )
