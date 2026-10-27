import hmac
import hashlib
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Voter, Election, Candidate, Vote, School, VotingEntitlement
from app.schemas import (
    TokenValidateRequest, TokenValidateResponse, VoteSubmitRequest,
    VoteReceiptResponse, CandidateResponse
)
from app.auth import (
    log_audit, check_rate_limit, record_failed_attempt, clear_failed_attempts,
    get_client_ip, hash_voting_token
)
from app.config import settings
from app.rut_validator import clean_rut

router = APIRouter(prefix="/voting", tags=["Sala de Votación Pública"])


def get_entitlement_key(election: Election, voter: Voter) -> str:
    """
    A4 - P0: Calcula la clave canónica de unidad electoral para el derecho a sufragio.
    Garantiza que todos los electores de una misma familia compartan la misma unidad de bloqueo.
    """
    if election.regla_votacion == "Un voto por familia":
        fam = (voter.familia_id or "").strip().upper()
        if not fam:
            raise HTTPException(
                status_code=400,
                detail="Registro electoral anómalo: falta 'familia_id' en elección con regla familiar."
            )
        return f"FAM:{fam}"
    else:
        clean = voter.rut_normalizado or clean_rut(voter.rut)
        return f"RUT:{clean}"


@router.post("/validate-token", response_model=TokenValidateResponse)
def validate_voting_token(
    payload: TokenValidateRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Módulo 5 & 3: Valida el token del elector y verifica las reglas de votación
    (persona vs familia, estado de la elección, sufragio previo, ventana temporal UTC).
    Protegido con rate limiting contra ataques de fuerza bruta y enumeración de tokens.
    """
    client_ip = get_client_ip(request)
    check_rate_limit(client_ip)

    token_clean = payload.token.strip()
    token_hash_computed = hash_voting_token(token_clean)
    voter = db.query(Voter).filter(
        or_(
            Voter.token_hash == token_hash_computed,
            Voter.token_votacion == token_clean,
            Voter.token_votacion == token_hash_computed,
        )
    ).first()
    
    if not voter:
        record_failed_attempt(client_ip)
        return TokenValidateResponse(
            valido=False,
            mensaje="Token de votación no reconocido o inválido. Verifique las credenciales provistas."
        )

    # Token válido reconocido: limpiar intentos fallidos
    clear_failed_attempts(client_ip)

    election = db.query(Election).filter(Election.id == voter.election_id).first()
    if not election:
        return TokenValidateResponse(valido=False, mensaje="Elección asociada no encontrada.")

    # 1. Validar estado de la elección
    if election.estado != "Abierta":
        return TokenValidateResponse(
            valido=False,
            mensaje=f"La elección no se encuentra abierta para recibir sufragios (Estado actual: {election.estado})."
        )

    # B1: Autoridad horaria del servidor (UTC)
    now_utc = datetime.now(timezone.utc)
    if election.fecha_inicio:
        inicio_utc = election.fecha_inicio.replace(tzinfo=timezone.utc) if election.fecha_inicio.tzinfo is None else election.fecha_inicio
        if now_utc < inicio_utc:
            return TokenValidateResponse(
                valido=False,
                mensaje=f"El proceso de votación aún no inicia. Apertura programada para: {inicio_utc.strftime('%d/%m/%Y a las %H:%M UTC')}."
            )
    if election.fecha_fin:
        fin_utc = election.fecha_fin.replace(tzinfo=timezone.utc) if election.fecha_fin.tzinfo is None else election.fecha_fin
        if now_utc > fin_utc:
            return TokenValidateResponse(
                valido=False,
                mensaje=f"El proceso de votación ha concluido por expiración de plazo el {fin_utc.strftime('%d/%m/%Y a las %H:%M UTC')}."
            )

    # 2. Validar si el elector individual ya votó
    if voter.estado == "Votó":
        fecha_str = voter.fecha_voto.strftime("%d/%m/%Y a las %H:%M hrs") if voter.fecha_voto else "previamente"
        return TokenValidateResponse(
            valido=False,
            mensaje=f"Su sufragio ya fue emitido y registrado de forma irreversible el {fecha_str}."
        )

    if voter.estado == "Bloqueado":
        return TokenValidateResponse(
            valido=False,
            mensaje="Su registro se encuentra bloqueado por la Comisión Electoral o cuota familiar completada."
        )

    # 3. A4: Validación a través de la entidad estable VotingEntitlement y verificación familiar
    unit_key = get_entitlement_key(election, voter)
    entitlement = db.query(VotingEntitlement).filter(
        VotingEntitlement.election_id == election.id,
        VotingEntitlement.unit_key == unit_key
    ).first()

    entitlement_consumed = entitlement and entitlement.estado == "Consumido"
    
    # Fallback de compatibilidad: verificar si otro miembro de la familia figura como "Votó"
    family_voted = False
    if election.regla_votacion == "Un voto por familia" and voter.familia_id:
        family_voted = db.query(Voter).filter(
            Voter.election_id == election.id,
            Voter.familia_id == voter.familia_id,
            Voter.estado == "Votó"
        ).first() is not None

    if entitlement_consumed or family_voted:
        if election.regla_votacion == "Un voto por familia":
            mensaje = (
                f"La regla electoral vigente para este proceso es 'Un voto por familia'. "
                f"Ya se ha registrado el sufragio correspondiente a su grupo familiar ({voter.familia_id})."
            )
        else:
            mensaje = "Su sufragio ya fue emitido y registrado previamente."
        return TokenValidateResponse(valido=False, mensaje=mensaje)

    # Cargar candidatos ordenados
    candidates = db.query(Candidate).filter(
        Candidate.election_id == election.id
    ).order_by(Candidate.orden.asc()).all()

    candidates_response = [
        CandidateResponse(
            id=c.id,
            nombre=c.nombre,
            cargo=c.cargo,
            descripcion=c.descripcion,
            foto=c.foto,
            orden=c.orden,
            es_blanco=c.es_blanco,
            es_nulo=c.es_nulo,
            election_id=c.election_id,
            votos_count=0  # Secrecía: No exponer votos acumulados en la pantalla de votación
        )
        for c in candidates
    ]

    school_nombre = election.school.nombre if election.school else "Institución Organizadora"

    return TokenValidateResponse(
        valido=True,
        mensaje="Token verificado correctamente. Elector habilitado para emitir sufragio.",
        elector_nombre=voter.nombre,
        eleccion_nombre=election.nombre,
        eleccion_tipo=election.tipo_votacion,
        regla_votacion=election.regla_votacion,
        colegio_nombre=school_nombre,
        candidatos=candidates_response
    )

@router.post("/submit", response_model=VoteReceiptResponse)
def submit_vote(
    vote_in: VoteSubmitRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Módulo 5: Emisión transaccional de sufragio (A4 - P0).
    - Orden consistente de locks libre de deadlocks: Election -> VotingEntitlement -> Voter
    - Bloqueo de fila sobre la unidad de derecho a sufragio (VotingEntitlement)
    - Validación rigurosa de ventana de horarios server-side UTC (B1)
    - Garantía estricta de 1 voto por persona o 1 voto por familia
    - Secrecía y trazabilidad mediante HMAC-SHA256 de Integridad (CRIT-05)
    - Rate limiting contra abuso
    """
    client_ip = get_client_ip(request)
    check_rate_limit(client_ip)

    token_clean = vote_in.token.strip()
    token_hash_computed = hash_voting_token(token_clean)

    # 1. Obtener votante para identificar la elección
    voter = db.query(Voter).filter(
        or_(
            Voter.token_hash == token_hash_computed,
            Voter.token_votacion == token_clean,
            Voter.token_votacion == token_hash_computed,
        )
    ).first()

    if not voter:
        record_failed_attempt(client_ip)
        raise HTTPException(status_code=400, detail="Token de votación inválido")

    # 2. LOCK CONSISTENTE 1: Bloquear la fila Election con with_for_update()
    # Esto serializa el cierre de elección vs emisión de votos, impidiendo carreras cierre/submit
    election = db.query(Election).filter(
        Election.id == voter.election_id
    ).with_for_update().first()

    if not election or election.estado != "Abierta":
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La elección no se encuentra abierta para votación (Estado: {election.estado if election else 'inexistente'})."
        )

    # 3. B1: Validación de autoridad horaria en UTC
    now = datetime.now(timezone.utc)
    if election.fecha_inicio:
        inicio_utc = election.fecha_inicio.replace(tzinfo=timezone.utc) if election.fecha_inicio.tzinfo is None else election.fecha_inicio
        if now < inicio_utc:
            record_failed_attempt(client_ip)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El proceso de votación aún no inicia según el cronograma oficial."
            )
    if election.fecha_fin:
        fin_utc = election.fecha_fin.replace(tzinfo=timezone.utc) if election.fecha_fin.tzinfo is None else election.fecha_fin
        if now > fin_utc:
            record_failed_attempt(client_ip)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El proceso de votación ha concluido por expiración de plazo."
            )

    # 4. LOCK CONSISTENTE 2: Bloquear la unidad de derecho a sufragio (VotingEntitlement)
    unit_key = get_entitlement_key(election, voter)
    entitlement = db.query(VotingEntitlement).filter(
        VotingEntitlement.election_id == election.id,
        VotingEntitlement.unit_key == unit_key
    ).with_for_update().first()

    if not entitlement:
        # Auto-provisionamiento seguro si no fue creado previamente
        entitlement = VotingEntitlement(
            election_id=election.id,
            unit_key=unit_key,
            estado="Pendiente"
        )
        db.add(entitlement)
        db.flush()

    if entitlement.estado == "Consumido":
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El derecho a sufragio correspondiente a este elector o grupo familiar ya ha sido ejercido."
        )

    # Re-bloquear fila Voter
    voter_locked = db.query(Voter).filter(Voter.id == voter.id).with_for_update().first()
    if voter_locked.estado != "Pendiente":
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este elector ya no se encuentra habilitado para sufragar."
        )

    # Validar candidato
    candidate = db.query(Candidate).filter(
        Candidate.id == vote_in.candidate_id,
        Candidate.election_id == election.id
    ).first()
    if not candidate:
        raise HTTPException(status_code=400, detail="La opción o candidato seleccionado no pertenece a esta elección")

    # CRIT-05: Generar HMAC-SHA256 de Integridad Criptográfica (con clave secreta)
    hash_seed = f"{voter_locked.id}-{candidate.id}-{now.isoformat()}-{uuid.uuid4()}"
    hash_integridad = hmac.new(
        settings.VOTE_HMAC_KEY.encode("utf-8"),
        hash_seed.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # 5. Consumir atómicamente el derecho a sufragio
    entitlement.estado = "Consumido"
    entitlement.fecha_consumo = now
    entitlement.voter_id_consumidor = voter_locked.id

    # 6. Marcar elector individual y consumir credencial criptográfica (P8)
    voter_locked.estado = "Votó"
    voter_locked.fecha_voto = now
    voter_locked.token_votacion = None
    voter_locked.token_hash = None

    # 7. Si rige regla familiar, bloquear a los demás miembros y revocar credenciales
    if election.regla_votacion == "Un voto por familia" and voter_locked.familia_id:
        db.query(Voter).filter(
            Voter.election_id == election.id,
            Voter.familia_id == voter_locked.familia_id,
            Voter.id != voter_locked.id
        ).update({"estado": "Bloqueado", "token_votacion": None, "token_hash": None}, synchronize_session=False)

    # 8. Registrar voto en la urna
    vote = Vote(
        candidate_id=candidate.id,
        voter_id=voter_locked.id,
        election_id=election.id,
        fecha_voto=now,
        hash_integridad=hash_integridad
    )
    db.add(vote)

    # 9. Registrar en Auditoría dentro de la misma transacción atómica (sin revelar el candidato votado)
    log_audit(
        db,
        accion="Emitió voto",
        detalle=f"Voto verificado con Hash: {hash_integridad[:16]}... para elección '{election.nombre}' (Elector ID: {voter_locked.id})",
        usuario="Elector Anónimo",
        school_id=election.school_id,
        commit=False
    )
    db.commit()


    school_nombre = election.school.nombre if election.school else "Institución Organizadora"
    clear_failed_attempts(client_ip)

    return VoteReceiptResponse(
        success=True,
        mensaje="¡Tu voto ha sido registrado y sellado con éxito!",
        hash_integridad=hash_integridad,
        fecha_voto=now,
        eleccion_nombre=election.nombre,
        colegio_nombre=school_nombre
    )
