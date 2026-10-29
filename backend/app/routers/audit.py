from datetime import datetime, timezone
import hashlib
import json
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from app.database import get_db
from app.models import AuditLog, AuditChainHead, User
from app.schemas import (
    AuditLogResponse,
    AuditIntegrityCheckResponse,
    AuditCheckpointResponse,
    AuditCheckpointArtifact,
)
from app.auth import (
    get_current_user,
    is_superadmin,
    require_role,
    verify_audit_log_chain,
    verify_audit_checkpoint,
    log_audit,
    ROLE_SUPERADMIN,
    ROLE_LEGACY_ADMIN,
    GENESIS_HASH,
)


def _escape_like(value: str) -> str:
    """MED-03: Escapa caracteres especiales de LIKE/ILIKE para evitar ataques de wildcard"""
    return value.replace("%", r"\%").replace("_", r"\_")


router = APIRouter(prefix="/audit", tags=["Trazabilidad y Auditoría"])


@router.post("/checkpoint/verify")
def verify_checkpoint_artifact(
    artifact: AuditCheckpointArtifact,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(ROLE_SUPERADMIN, ROLE_LEGACY_ADMIN)),
):
    """Compara un artefacto conservado externamente con la cadena local."""
    return verify_audit_checkpoint(db, artifact.model_dump())


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
    El digest resultante debe exportarse o enviarse a un repositorio externo/TSA.
    Generarlo localmente no acredita custodia independiente ni anclaje verificable.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()
    if db.bind.dialect.name == "postgresql":
        head = (
            db.query(AuditChainHead)
            .filter(AuditChainHead.id == 1)
            .with_for_update()
            .one_or_none()
        )
        if head is None:
            raise RuntimeError("Falta audit_chain_heads; ejecute la migración S2-D.")
        head_hash = head.head_hash
        last_id = head.last_log_id
        count_query = db.query(func.count(AuditLog.id))
        if last_id is not None:
            count_query = count_query.filter(AuditLog.id <= last_id)
        total = count_query.scalar() or 0
    else:
        last_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        head_hash = last_log.record_hash if (last_log and last_log.record_hash) else GENESIS_HASH
        last_id = last_log.id if last_log else None
        total = db.query(func.count(AuditLog.id)).scalar() or 0

    artifact_fields = {
        "schema_version": 1,
        "timestamp": timestamp,
        "total_records": total,
        "last_record_id": last_id,
        "head_hash": head_hash,
    }
    canonical_artifact = json.dumps(artifact_fields, sort_keys=True, separators=(",", ":"))
    checkpoint_hash = hashlib.sha256(canonical_artifact.encode("utf-8")).hexdigest()

    # Registrar el evento en la propia bitácora
    log_audit(
        db,
        accion="AUDIT: Generación de anclaje de bitácora",
        detalle=(
            f"Checkpoint exportable generado; digest {checkpoint_hash}. "
            "Custodia independiente pendiente."
        ),
        usuario=current_user.email,
        commit=True,
    )

    return {
        "success": True,
        "timestamp": timestamp,
        "total_records": total,
        "last_record_id": last_id,
        "head_hash": head_hash,
        "checkpoint_hash": checkpoint_hash,
        "firmado_por": current_user.email,
        "artifact": {**artifact_fields, "digest_sha256": checkpoint_hash},
        "anchorage_status": "PENDIENTE_ANCLAJE_EXTERNO",
        "independent_custody_confirmed": False,
        "instrucciones_anclaje": (
            "Guardar el artifact fuera de este servidor en custodia independiente "
            "(WORM o TSA) y conservar el recibo verificable. La generación local "
            "no demuestra anclaje externo ni no repudio."
        ),
    }
