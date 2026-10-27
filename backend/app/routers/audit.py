from datetime import datetime, timezone
import hashlib
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from app.database import get_db
from app.models import AuditLog, User
from app.schemas import (
    AuditLogResponse,
    AuditIntegrityCheckResponse,
    AuditCheckpointResponse,
)
from app.auth import (
    get_current_user,
    is_superadmin,
    require_role,
    verify_audit_log_chain,
    log_audit,
    ROLE_SUPERADMIN,
    ROLE_LEGACY_ADMIN,
    GENESIS_HASH,
)


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


@router.get("/verify-integrity", response_model=AuditIntegrityCheckResponse)
def verify_audit_integrity(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_SUPERADMIN, ROLE_LEGACY_ADMIN)),
):
    """
    P15: Verifica la integridad de la cadena criptográfica de la bitácora append-only.
    Comprueba que ningún registro haya sido alterado, insertado o eliminado arbitrariamente.
    """
    return verify_audit_log_chain(db)


@router.post("/checkpoint", response_model=AuditCheckpointResponse)
def create_audit_checkpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_SUPERADMIN, ROLE_LEGACY_ADMIN)),
):
    """
    P15: Genera un anclaje criptográfico (checkpoint) del estado actual de la bitácora.
    El digest resultante debe exportarse o enviarse a un repositorio externo/TSA
    para proporcionar evidencia de inmutabilidad verificable e independiente.
    """
    total = db.query(func.count(AuditLog.id)).scalar() or 0
    last_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    head_hash = last_log.record_hash if (last_log and last_log.record_hash) else GENESIS_HASH
    last_id = last_log.id if last_log else None

    now = datetime.now(timezone.utc)
    raw_payload = f"CHECKPOINT|{now.isoformat()}|{total}|{last_id}|{head_hash}|{current_user.email}"
    checkpoint_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    # Registrar el evento en la propia bitácora
    log_audit(
        db,
        accion="AUDIT: Generación de anclaje de bitácora",
        detalle=f"Checkpoint hash: {checkpoint_hash} (total: {total} registros, head: {head_hash[:16]}...).",
        usuario=current_user.email,
        commit=True,
    )

    return {
        "success": True,
        "timestamp": now.isoformat(),
        "total_records": total,
        "last_record_id": last_id,
        "head_hash": head_hash,
        "checkpoint_hash": checkpoint_hash,
        "firmado_por": current_user.email,
        "instrucciones_anclaje": (
            "Exportar 'checkpoint_hash' a almacenamiento WORM (Write-Once-Read-Many), "
            "servidor syslog remoto independiente o Autoridad de Sellado de Tiempo (RFC 3161 TSA) "
            "para garantizar no repudio."
        ),
    }

