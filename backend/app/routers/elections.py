import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Election, School, ElectoralCommittee, Voter, Candidate, Vote, User
from app.schemas import (
    ElectionCreate, ElectionUpdate, ElectionResponse, ElectionDetailResponse,
    ElectoralCommitteeCreate, ElectoralCommitteeResponse
)
from app.auth import get_current_user, log_audit

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
    current_user: User = Depends(get_current_user),  # CRIT-03: Autenticación requerida
):
    """Lista todas las elecciones registradas (paginado — LOW-03)"""
    return db.query(Election).order_by(Election.fecha_creacion.desc()).offset(skip).limit(limit).all()

@router.post("", response_model=ElectionResponse, status_code=status.HTTP_201_CREATED)
def create_election(
    election_in: ElectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crea una nueva elección asociada a un colegio"""
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
        usuario=current_user.email
    )
    return election

@router.get("/{election_id}", response_model=ElectionDetailResponse)
def get_election_detail(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """Obtiene el detalle completo de una elección"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

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
    """Actualiza los datos básicos o estado de una elección"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    # HIGH-02: Validar transición de estado si se intenta cambiar
    update_data = election_in.model_dump(exclude_unset=True)
    if "estado" in update_data and update_data["estado"] != election.estado:
        new_state = update_data["estado"]
        allowed = VALID_STATE_TRANSITIONS.get(election.estado, [])
        if new_state not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Transición de estado inválida: '{election.estado}' → '{new_state}'. "
                       f"Transiciones permitidas: {allowed or 'ninguna'}"
            )

    for field, val in update_data.items():
        setattr(election, field, val)

    db.commit()
    db.refresh(election)
    
    log_audit(
        db,
        accion="Actualizó elección",
        detalle=f"Se actualizaron parámetros de la elección '{election.nombre}'",
        usuario=current_user.email
    )
    return election

@router.post("/{election_id}/abrir", response_model=ElectionResponse)
def open_election(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Abre la elección para votación pública.
    Genera automáticamente tokens UUID para todos los electores que no dispongan de uno.
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    # HIGH-02: Validar transición de estado
    if election.estado != "Borrador":
        allowed = VALID_STATE_TRANSITIONS.get(election.estado, [])
        raise HTTPException(
            status_code=400,
            detail=f"Solo se puede abrir una elección en estado 'Borrador'. "
                   f"Estado actual: '{election.estado}'. Transiciones permitidas: {allowed or 'ninguna'}"
        )

    # Módulo 4: Generar token UUID para cada elector que no lo tenga
    voters = db.query(Voter).filter(Voter.election_id == election_id).all()
    generated_count = 0
    for v in voters:
        if not v.token_votacion:
            v.token_votacion = str(uuid.uuid4())
            generated_count += 1

    election.estado = "Abierta"
    if not election.fecha_inicio:
        election.fecha_inicio = datetime.now(timezone.utc)

    db.commit()
    db.refresh(election)

    log_audit(
        db,
        accion="Abrió votación",
        detalle=f"Elección '{election.nombre}' abierta al público. Se generaron {generated_count} tokens de sufragio.",
        usuario=current_user.email
    )
    return election

@router.post("/{election_id}/cerrar", response_model=ElectionResponse)
def close_election(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cierra la elección y sella la urna digital para escrutinio definitivo"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    # HIGH-02: Validar transición de estado
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
        usuario=current_user.email
    )
    return election

@router.post("/{election_id}/comite", response_model=ElectoralCommitteeResponse)
def add_committee_member(
    election_id: int,
    member_in: ElectoralCommitteeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Agrega un miembro a la comisión electoral de una elección"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    member = ElectoralCommittee(**member_in.model_dump(), election_id=election_id)
    db.add(member)
    db.commit()
    db.refresh(member)

    log_audit(
        db,
        accion="Agregó miembro de comisión",
        detalle=f"{member.nombre} ({member.cargo}) incorporado a la comisión electoral",
        usuario=current_user.email
    )
    return member
