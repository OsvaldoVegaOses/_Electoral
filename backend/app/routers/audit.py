from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from app.database import get_db
from app.models import AuditLog, User
from app.schemas import AuditLogResponse
from app.auth import get_current_user, is_superadmin  # CRIT-03 + A3


def _escape_like(value: str) -> str:
    """MED-03: Escapa caracteres especiales de LIKE/ILIKE para evitar ataques de wildcard"""
    return value.replace("%", r"\%").replace("_", r"\_")


router = APIRouter(prefix="/audit", tags=["Trazabilidad y Auditoría"])

@router.get("/logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    accion: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """
    Módulo 9: Bitácora de auditoría con ámbito institucional (A3 - P0).
    Permite auditar acciones dentro del ámbito autorizado del usuario.
    """
    query = db.query(AuditLog)
    if not is_superadmin(current_user):
        if current_user.school_id:
            query = query.filter(
                or_(
                    AuditLog.school_id == current_user.school_id,
                    AuditLog.usuario == current_user.email
                )
            )
        else:
            query = query.filter(AuditLog.usuario == current_user.email)

    if accion:
        safe_accion = _escape_like(accion)
        query = query.filter(AuditLog.accion.ilike(f"%{safe_accion}%"))
    if q:
        safe_q = _escape_like(q)
        query = query.filter(
            (AuditLog.detalle.ilike(f"%{safe_q}%")) |
            (AuditLog.usuario.ilike(f"%{safe_q}%")) |
            (AuditLog.accion.ilike(f"%{safe_q}%"))
        )
    return query.order_by(AuditLog.fecha.desc()).limit(limit).all()

