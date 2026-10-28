import uuid
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Election, School, ElectoralCommittee, Voter, Candidate, Vote, User, VotingEntitlement
from app.schemas import (
    ElectionCreate, ElectionUpdate, ElectionResponse, ElectionDetailResponse,
    ElectoralCommitteeCreate, ElectoralCommitteeResponse
)
from app.auth import (
    get_current_user, log_audit, is_superadmin, check_election_access,
    ROLE_RESPONSABLE, ROLE_COMISION, hash_voting_token
)
from app.rut_validator import clean_rut


router = APIRouter(prefix="/elections", tags=["Elecciones"])

# HIGH-02: Transiciones de estado válidas
VALID_STATE_TRANSITIONS = {
    "Borrador": ["Abierta"],
    "Abierta": ["Cerrada"],
    "Cerrada": ["Finalizada"],
    "Finalizada": [],
}

@router.get("", response_model=List[ElectionResponse])
def list_elections(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """Lista las elecciones registradas según el ámbito y permisos del usuario (A3 - P0)"""
    query = db.query(Election)
    if not is_superadmin(current_user):
        if current_user.rol == ROLE_RESPONSABLE:
            if current_user.school_id:
                query = query.filter(Election.school_id == current_user.school_id)
            else:
                query = query.filter(False)
        elif current_user.rol == ROLE_COMISION:
            # S2-A: Comisión requiere ambos school_id y election_id; si election_id es None, retorna vacío
            if current_user.school_id and current_user.election_id:
                query = query.filter(
                    Election.id == current_user.election_id,
                    Election.school_id == current_user.school_id
                )
            else:
                query = query.filter(False)
        else:
            query = query.filter(False)

    return query.order_by(Election.fecha_creacion.desc()).offset(skip).limit(limit).all()

@router.post("", response_model=ElectionResponse, status_code=status.HTTP_201_CREATED)
def create_election(
    election_in: ElectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crea una nueva elección asociada a un colegio (restringido a Superadmin o Responsable de esa institución)"""
    if not is_superadmin(current_user):
        if current_user.rol == ROLE_COMISION:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes: comisiones electorales no poseen permisos para crear elecciones."
            )
        if current_user.rol == ROLE_RESPONSABLE:
            if current_user.school_id != election_in.school_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Acceso denegado: no tiene permisos para crear elecciones en otra institución."
                )

    school = db.query(School).filter(School.id == election_in.school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="El colegio seleccionado no existe")

    election_data = election_in.model_dump(exclude={"committee"})
    election = Election(**election_data)
    db.add(election)
    db.flush()

    # Si se enviaron miembros de la comisión electoral
    if election_in.committee:
        for m in election_in.committee:
            comm = ElectoralCommittee(
                nombre=m.nombre,
                rut=m.rut,
                correo=m.correo,
                cargo=m.cargo,
                election_id=election.id
            )
            db.add(comm)

    # Agregar automáticamente opciones de "Voto en Blanco" y "Voto Nulo"
    db.add(Candidate(
        nombre="Voto en Blanco",
        cargo="Opción Institucional",
        descripcion="Voto deliberadamente no asignado a ninguna lista",
        es_blanco=True,
        es_nulo=False,
        orden=98,
        election_id=election.id
    ))
    db.add(Candidate(
        nombre="Voto Nulo",
        cargo="Opción Institucional",
        descripcion="Anulación voluntaria del voto",
        es_blanco=False,
        es_nulo=True,
        orden=99,
        election_id=election.id
    ))

    db.commit()
    db.refresh(election)

    log_audit(
        db,
        accion="Creó elección",
        detalle=f"Elección '{election.nombre}' creada para '{school.nombre}' con regla '{election.regla_votacion}'",
        usuario=current_user.email,
        school_id=school.id
    )
    return election

@router.get("/{election_id}", response_model=ElectionDetailResponse)
def get_election_detail(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """Obtiene el detalle completo de una elección con validación anti-IDOR"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=False)


    total_voters = db.query(Voter).filter(Voter.election_id == election_id).count()
    voted_count = db.query(Voter).filter(Voter.election_id == election_id, Voter.estado == "Votó").count()

    response_data = {
        **election.__dict__,
        "school": election.school,
        "committee_members": election.committee_members,
        "candidates": election.candidates,
        "total_voters": total_voters,
        "voted_count": voted_count
    }
    return response_data

@router.put("/{election_id}", response_model=ElectionResponse)
def update_election(
    election_id: int,
    election_in: ElectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza los datos básicos de una elección.
    B1: Prohíbe modificar 'estado' por este endpoint general (utilizar /abrir, /cerrar, /finalizar).
    B1: Congela parámetros estructurales una vez que la elección sale del estado 'Borrador'.
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=True)

    update_data = election_in.model_dump(exclude_unset=True)

    # B1: Prohibir alterar 'estado' mediante actualización general
    if "estado" in update_data and update_data["estado"] != election.estado:
        raise HTTPException(
            status_code=400,
            detail="El estado de la elección no puede modificarse mediante actualización general. "
                   "Utilice las transiciones explícitas: /abrir, /cerrar, /finalizar."
        )

    # B1: Congelar parámetros estructurales fuera de Borrador
    if election.estado != "Borrador":
        restricted_fields = {"regla_votacion", "tipo_votacion", "school_id"}
        altered = restricted_fields.intersection(update_data.keys())
        if altered:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Parámetros estructurales congelados: no se puede modificar '{', '.join(altered)}' "
                       f"en estado '{election.estado}'."
            )

    for field, val in update_data.items():
        setattr(election, field, val)

    db.commit()
    db.refresh(election)
    
    log_audit(
        db,
        accion="Actualizó elección",
        detalle=f"Se actualizaron parámetros de la elección '{election.nombre}'",
        usuario=current_user.email,
        school_id=election.school_id
    )
    return election

@router.post("/{election_id}/abrir", response_model=ElectionResponse)
def open_election(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    B1 & A4: Abre la elección para sufragio público tras validación atómica:
    - Estado previo debe ser exactamente 'Borrador'
    - Padrón íntegro no vacío (mínimo 1 elector)
    - En regla familiar: exige 'familia_id' válido en todos los electores
    - Candidaturas validadas (al menos 1 candidato de lista además de blanco/nulo)
    - Fechas coherentes (fecha_inicio <= fecha_fin)
    - Provisionamiento de unidades electorales (VotingEntitlement)
    - Instantánea de configuración con hash de integridad
    """
    election = db.query(Election).filter(Election.id == election_id).with_for_update().first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=True)

    # 1. Validar estado Borrador
    if election.estado != "Borrador":
        allowed = VALID_STATE_TRANSITIONS.get(election.estado, [])
        raise HTTPException(
            status_code=400,
            detail=f"Solo se puede abrir una elección en estado 'Borrador'. "
                   f"Estado actual: '{election.estado}'. Transiciones permitidas: {allowed or 'ninguna'}"
        )

    # 2. Validar padrón no vacío
    voters = db.query(Voter).filter(Voter.election_id == election_id).all()
    if not voters:
        raise HTTPException(
            status_code=400,
            detail="No se puede abrir una elección con el padrón electoral vacío. Incorpore electores antes de abrir."
        )

    # 3. Validar regla familiar (A4 - P0)
    if election.regla_votacion == "Un voto por familia":
        sin_familia = [v.rut for v in voters if not v.familia_id or not v.familia_id.strip()]
        if sin_familia:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede abrir la elección: existen {len(sin_familia)} electores sin 'familia_id' "
                       f"bajo regla 'Un voto por familia'. Sanee el padrón antes de abrir."
            )

    # 4. Validar candidaturas
    regular_candidates = db.query(Candidate).filter(
        Candidate.election_id == election_id,
        Candidate.es_blanco == False,
        Candidate.es_nulo == False
    ).count()
    if regular_candidates < 1:
        raise HTTPException(
            status_code=400,
            detail="No se puede abrir la elección sin al menos un candidato o lista inscrita."
        )

    # 5. Validar coherencia de fechas
    if election.fecha_inicio and election.fecha_fin and election.fecha_inicio > election.fecha_fin:
        raise HTTPException(
            status_code=400,
            detail="Fechas incoherentes: la fecha de inicio no puede ser posterior a la fecha de término."
        )

    now = datetime.now(timezone.utc)

    # 6. Generar tokens pendientes y provisionar VotingEntitlements
    generated_count = 0
    entitlement_keys = set()
    for v in voters:
        if not v.token_votacion and not v.token_hash:
            raw_token = str(uuid.uuid4())
            v.token_votacion = raw_token
            v.token_hash = hash_voting_token(raw_token)
            generated_count += 1
        if not v.rut_normalizado:
            v.rut_normalizado = clean_rut(v.rut)

        if election.regla_votacion == "Un voto por familia":
            key = f"FAM:{v.familia_id.strip().upper()}"
        else:
            key = f"RUT:{v.rut_normalizado}"
        entitlement_keys.add(key)

    for key in entitlement_keys:
        existing_ent = db.query(VotingEntitlement).filter(
            VotingEntitlement.election_id == election_id,
            VotingEntitlement.unit_key == key
        ).first()
        if not existing_ent:
            db.add(VotingEntitlement(
                election_id=election_id,
                unit_key=key,
                estado="Pendiente"
            ))

    # 7. Hash de configuración aprobada
    config_str = f"{election.id}:{election.nombre}:{election.regla_votacion}:{len(voters)}:{regular_candidates}:{now.isoformat()}"
    election.config_hash = hashlib.sha256(config_str.encode("utf-8")).hexdigest()

    election.estado = "Abierta"
    if not election.fecha_inicio:
        election.fecha_inicio = now

    db.commit()
    db.refresh(election)

    log_audit(
        db,
        accion="Abrió votación",
        detalle=f"Elección '{election.nombre}' abierta con configuración sellada (Hash: {election.config_hash[:16]}...). "
                f"{len(entitlement_keys)} derechos electorales provisionados. {generated_count} tokens generados.",
        usuario=current_user.email,
        school_id=election.school_id
    )
    return election

@router.post("/{election_id}/cerrar", response_model=ElectionResponse)
def close_election(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cierra la elección y sella la urna digital para escrutinio definitivo.
    Bloqueo estricto con SELECT FOR UPDATE sobre Election para evitar carreras contra votos simultáneos.
    """
    election = db.query(Election).filter(Election.id == election_id).with_for_update().first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=True)

    if election.estado != "Abierta":
        raise HTTPException(
            status_code=400,
            detail=f"Solo se puede cerrar una elección en estado 'Abierta'. Estado actual: '{election.estado}'."
        )

    election.estado = "Cerrada"
    election.fecha_fin = datetime.now(timezone.utc)

    db.commit()
    db.refresh(election)

    log_audit(
        db,
        accion="Cerró votación",
        detalle=f"Elección '{election.nombre}' cerrada formalmente para cómputo definitivo.",
        usuario=current_user.email,
        school_id=election.school_id
    )
    return election

@router.post("/{election_id}/finalizar", response_model=ElectionResponse)
def finalize_election(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    B1: Finaliza y archiva formalmente la elección tras el escrutinio.
    Estado terminal definitivo. No admite votos ni reaperturas.
    """
    election = db.query(Election).filter(Election.id == election_id).with_for_update().first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=True)

    if election.estado != "Cerrada":
        raise HTTPException(
            status_code=400,
            detail=f"Solo se puede finalizar una elección en estado 'Cerrada'. Estado actual: '{election.estado}'."
        )

    election.estado = "Finalizada"
    db.commit()
    db.refresh(election)

    log_audit(
        db,
        accion="Finalizó elección",
        detalle=f"Elección '{election.nombre}' finalizada y archivada formalmente.",
        usuario=current_user.email,
        school_id=election.school_id
    )
    return election

@router.post("/{election_id}/comite", response_model=ElectoralCommitteeResponse)
def add_committee_member(
    election_id: int,
    member_in: ElectoralCommitteeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Agrega un miembro a la comisión electoral (Solo permitido en estado 'Borrador')"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=True)

    # B1: Congelamiento de comisión tras apertura
    if election.estado != "Borrador":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se pueden agregar miembros de comisión en estado '{election.estado}'. "
                   f"La composición electoral está congelada."
        )

    member = ElectoralCommittee(**member_in.model_dump(), election_id=election_id)
    db.add(member)
    db.commit()
    db.refresh(member)

    log_audit(
        db,
        accion="Agregó miembro de comisión",
        detalle=f"{member.nombre} ({member.cargo}) incorporado a la comisión electoral",
        usuario=current_user.email,
        school_id=election.school_id
    )
    return member


