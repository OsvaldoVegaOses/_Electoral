from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import School, User
from app.schemas import SchoolCreate, SchoolResponse
from app.auth import get_current_user, log_audit

router = APIRouter(prefix="/schools", tags=["Colegios e Instituciones"])

@router.get("", response_model=List[SchoolResponse])
def list_schools(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03: Autenticación requerida
):
    """Lista todos los colegios u organizaciones registradas (paginado — LOW-03)"""
    return db.query(School).order_by(School.nombre).offset(skip).limit(limit).all()

@router.post("", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
def create_school(
    school_in: SchoolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crea un nuevo colegio u organización electoral"""
    school = School(**school_in.model_dump())
    db.add(school)
    db.commit()
    db.refresh(school)
    
    log_audit(
        db,
        accion="Creó colegio",
        detalle=f"Institución '{school.nombre}' (RBD: {school.rbd}) registrada",
        usuario=current_user.email
    )
    return school

@router.get("/{school_id}", response_model=SchoolResponse)
def get_school(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """Obtiene el detalle de un colegio por su ID"""
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="Colegio no encontrado")
    return school
