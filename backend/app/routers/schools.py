from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import School, User
from app.schemas import SchoolCreate, SchoolUpdate, SchoolResponse
from app.auth import get_current_user, log_audit, is_superadmin, check_school_access

router = APIRouter(prefix="/schools", tags=["Colegios e Instituciones"])

@router.get("", response_model=List[SchoolResponse])
def list_schools(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """Lista los colegios u organizaciones registradas según el ámbito del usuario (A3 - P0)"""
    query = db.query(School)
    if not is_superadmin(current_user):
        if current_user.school_id:
            query = query.filter(School.id == current_user.school_id)
        else:
            query = query.filter(False)
    return query.order_by(School.nombre).offset(skip).limit(limit).all()

@router.post("", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
def create_school(
    school_in: SchoolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crea un nuevo colegio u organización electoral (Solo Administrador General)"""
    if not is_superadmin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes: solo el Administrador General puede crear nuevas instituciones."
        )

    school = School(**school_in.model_dump())
    db.add(school)
    db.commit()
    db.refresh(school)
    
    log_audit(
        db,
        accion="Creó colegio",
        detalle=f"Institución '{school.nombre}' (RBD: {school.rbd}) registrada",
        usuario=current_user.email,
        school_id=school.id
    )
    return school

@router.get("/{school_id}", response_model=SchoolResponse)
def get_school(
    school_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """Obtiene el detalle de un colegio por su ID con verificación anti-IDOR"""
    check_school_access(current_user, school_id, write=False)
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="Colegio no encontrado")
    return school

@router.put("/{school_id}", response_model=SchoolResponse)
def update_school(
    school_id: int,
    school_in: SchoolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Actualiza la información de un colegio (restringido a Superadmin o Responsable de esa institución)"""
    check_school_access(current_user, school_id, write=True)
    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="Colegio no encontrado")

    update_data = school_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(school, field, val)

    db.commit()
    db.refresh(school)

    log_audit(
        db,
        accion="Actualizó colegio",
        detalle=f"Institución '{school.nombre}' actualizada",
        usuario=current_user.email,
        school_id=school.id
    )
    return school

