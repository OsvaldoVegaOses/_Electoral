from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Candidate, Election, Vote, User
from app.schemas import CandidateCreate, CandidateResponse
from app.auth import get_current_user, log_audit, check_election_access

router = APIRouter(prefix="/elections/{election_id}/candidates", tags=["Candidatos y Listas"])

@router.get("", response_model=List[CandidateResponse])
def list_candidates(
    election_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """Lista todos los candidatos y opciones de votación para una elección con validación anti-IDOR"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=False)

    candidates = db.query(Candidate).filter(
        Candidate.election_id == election_id
    ).order_by(Candidate.orden.asc()).offset(skip).limit(limit).all()
    
    # A2 - P0: Ocultar conteo de votos salvo que la elección esté formalmente Cerrada o Finalizada
    result = []
    for c in candidates:
        if election and election.estado in ["Cerrada", "Finalizada"]:
            v_count = db.query(Vote).filter(Vote.candidate_id == c.id).count()
        else:
            v_count = 0
        cand_dict = {**c.__dict__, "votos_count": v_count}
        result.append(cand_dict)
    return result

@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def create_candidate(
    election_id: int,
    candidate_in: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Agrega un candidato o lista a la elección con validación anti-IDOR"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=True)

    if election.estado != "Borrador":
        raise HTTPException(
            status_code=409,
            detail="La nómina de candidaturas se encuentra congelada tras la apertura de la elección."
        )

    candidate = Candidate(**candidate_in.model_dump(), election_id=election_id)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    log_audit(
        db,
        accion="Creó candidato",
        detalle=f"Candidato/Lista '{candidate.nombre}' agregado a la elección '{election.nombre}'",
        usuario=current_user.email,
        school_id=election.school_id
    )
    return candidate

@router.delete("/{candidate_id}")
def delete_candidate(
    election_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina un candidato si la elección aún no ha recibido votos (verificación anti-IDOR)"""
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=True)

    if election.estado != "Borrador":
        raise HTTPException(
            status_code=409,
            detail="La nómina de candidaturas se encuentra congelada tras la apertura de la elección."
        )

    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id,
        Candidate.election_id == election_id
    ).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato no encontrado")

    votes_count = db.query(Vote).filter(Vote.candidate_id == candidate_id).count()
    if votes_count > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar un candidato que ya posee sufragios registrados")

    nombre = candidate.nombre
    db.delete(candidate)
    db.commit()

    log_audit(
        db,
        accion="Eliminó candidato",
        detalle=f"Candidato '{nombre}' removido de la elección",
        usuario=current_user.email,
        school_id=election.school_id
    )
    return {"mensaje": "Candidato eliminado con éxito"}

