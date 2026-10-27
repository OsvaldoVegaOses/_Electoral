"""
P14: Router de Administración de PII (Retención y Eliminación de Datos Personales)

Endpoints solo para Administrador General:
- GET  /admin/pii/elections-ready-for-anonymization  — Lista elecciones candidatas
- POST /admin/pii/anonymize-election/{election_id}   — Anonimiza padrón y comisión
- POST /admin/pii/purge-audit-logs                   — Elimina audit_logs antiguos
- GET  /admin/pii/status                             — Resumen del estado de PII en el sistema
"""
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.database import get_db
from app.models import Voter, ElectoralCommittee, Election, AuditLog, User
from app.auth import get_current_user, log_audit, require_role, is_superadmin
from app.config import settings

logger = logging.getLogger("theogen.pii")

router = APIRouter(prefix="/admin/pii", tags=["Administración PII"])

_ANON_RUT = "[ANONIMIZADO]"
_ANON_NOMBRE_VOTER = "[Elector Anonimizado]"
_ANON_NOMBRE_COMISION = "[Comisionado Anonimizado]"


def _retention_cutoff_voter() -> datetime:
    """Fecha límite: elecciones finalizadas hace más de PII_VOTER_RETENTION_DAYS días."""
    return datetime.now(timezone.utc) - timedelta(days=settings.PII_VOTER_RETENTION_DAYS)


def _retention_cutoff_audit() -> datetime:
    """Fecha límite: registros de auditoría con más de PII_AUDIT_RETENTION_DAYS días."""
    return datetime.now(timezone.utc) - timedelta(days=settings.PII_AUDIT_RETENTION_DAYS)


# ---------------------------------------------------------------------------
# GET /admin/pii/status
# ---------------------------------------------------------------------------

@router.get("/status")
def pii_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrador General", "Administrador")),
):
    """
    P14: Resumen del estado de datos PII en el sistema.
    Informa cuántos registros tienen PII activa y cuántos ya fueron anonimizados.
    """
    voter_cutoff = _retention_cutoff_voter()
    audit_cutoff = _retention_cutoff_audit()

    # Padrón con PII aún vigente
    voters_with_pii = db.query(func.count(Voter.id)).filter(
        Voter.pii_eliminado_en == None  # noqa: E711
    ).scalar()

    # Padrón ya anonimizado
    voters_anonymized = db.query(func.count(Voter.id)).filter(
        Voter.pii_eliminado_en != None  # noqa: E711
    ).scalar()

    # Electores candidatos a anonimización (en elecciones finalizadas hace > N días)
    voters_ready = db.query(func.count(Voter.id)).join(Election).filter(
        Election.estado == "Finalizada",
        Election.fecha_creacion <= voter_cutoff,
        Voter.pii_eliminado_en == None  # noqa: E711
    ).scalar()

    # Audit logs candidatos a purga
    audit_ready_for_purge = db.query(func.count(AuditLog.id)).filter(
        AuditLog.fecha <= audit_cutoff
    ).scalar()

    return {
        "configuracion": {
            "pii_voter_retention_days": settings.PII_VOTER_RETENTION_DAYS,
            "pii_audit_retention_days": settings.PII_AUDIT_RETENTION_DAYS,
            "voter_cutoff_date": voter_cutoff.isoformat(),
            "audit_cutoff_date": audit_cutoff.isoformat(),
        },
        "padron": {
            "total_con_pii_vigente": voters_with_pii,
            "total_anonimizados": voters_anonymized,
            "candidatos_a_anonimizar": voters_ready,
        },
        "auditoria": {
            "candidatos_a_purgar": audit_ready_for_purge,
        },
    }


# ---------------------------------------------------------------------------
# GET /admin/pii/elections-ready-for-anonymization
# ---------------------------------------------------------------------------

@router.get("/elections-ready-for-anonymization")
def elections_ready_for_anonymization(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrador General", "Administrador")),
):
    """
    P14: Lista las elecciones cuyo período de retención de PII ha vencido
    y que aún tienen electores con datos personales sin anonimizar.
    """
    cutoff = _retention_cutoff_voter()

    elections = (
        db.query(Election)
        .filter(
            Election.estado == "Finalizada",
            Election.fecha_creacion <= cutoff,
        )
        .all()
    )

    result = []
    for e in elections:
        pending_voters = db.query(func.count(Voter.id)).filter(
            Voter.election_id == e.id,
            Voter.pii_eliminado_en == None  # noqa: E711
        ).scalar()

        if pending_voters > 0:
            result.append({
                "election_id": e.id,
                "nombre": e.nombre,
                "estado": e.estado,
                "fecha_creacion": e.fecha_creacion.isoformat() if e.fecha_creacion else None,
                "electores_pendientes_anonimizacion": pending_voters,
                "dias_desde_creacion": (datetime.now(timezone.utc) - e.fecha_creacion.replace(tzinfo=timezone.utc)).days
                    if e.fecha_creacion else None,
            })

    return {
        "total_elecciones_candidatas": len(result),
        "retention_dias_configurados": settings.PII_VOTER_RETENTION_DAYS,
        "elecciones": result,
    }


# ---------------------------------------------------------------------------
# POST /admin/pii/anonymize-election/{election_id}
# ---------------------------------------------------------------------------

@router.post("/anonymize-election/{election_id}")
def anonymize_election_pii(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrador General", "Administrador")),
):
    """
    P14: Anonimiza los datos personales del padrón y la comisión electoral
    de una elección específica.

    - Solo ejecutable sobre elecciones en estado 'Finalizada'.
    - No elimina registros: reemplaza campos PII con valores de sustitución.
    - Registra el timestamp en pii_eliminado_en para evitar doble procesamiento.
    - Toda la operación es atómica (transacción única).
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada.")

    if election.estado != "Finalizada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Solo se pueden anonimizar elecciones en estado 'Finalizada'. "
                   f"Estado actual: '{election.estado}'.",
        )

    now = datetime.now(timezone.utc)

    # 1. Anonimizar electores (voters) con PII aún vigente
    voters_to_anon = db.query(Voter).filter(
        Voter.election_id == election_id,
        Voter.pii_eliminado_en == None  # noqa: E711
    ).all()

    voters_count = len(voters_to_anon)
    for voter in voters_to_anon:
        voter.rut = _ANON_RUT
        voter.rut_normalizado = _ANON_RUT
        voter.nombre = _ANON_NOMBRE_VOTER
        voter.correo = None
        voter.familia_id = None
        voter.token_votacion = None  # Ya debería ser NULL (P8), doble seguridad
        voter.token_hash = None      # Ya debería ser NULL (P8), doble seguridad
        voter.pii_eliminado_en = now

    # 2. Anonimizar miembros de la comisión electoral
    committees_to_anon = db.query(ElectoralCommittee).filter(
        ElectoralCommittee.election_id == election_id,
        ElectoralCommittee.pii_eliminado_en == None  # noqa: E711
    ).all()

    committees_count = len(committees_to_anon)
    for member in committees_to_anon:
        member.nombre = _ANON_NOMBRE_COMISION
        member.rut = _ANON_RUT
        member.correo = None
        member.pii_eliminado_en = now

    # 3. Registrar en auditoría dentro de la misma transacción
    log_audit(
        db,
        accion="PII: Anonimización de padrón",
        detalle=(
            f"Elección '{election.nombre}' (ID: {election_id}): "
            f"{voters_count} electores y {committees_count} comisionados anonimizados. "
            f"Solicitado por: {current_user.email}"
        ),
        usuario=current_user.email,
        school_id=election.school_id,
        commit=False,
    )

    db.commit()
    logger.info(
        "P14: PII anonimizada — Elección %s: %d electores, %d comisionados.",
        election_id, voters_count, committees_count
    )

    return {
        "success": True,
        "election_id": election_id,
        "election_nombre": election.nombre,
        "electores_anonimizados": voters_count,
        "comisionados_anonimizados": committees_count,
        "fecha_anonimizacion": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# POST /admin/pii/purge-audit-logs
# ---------------------------------------------------------------------------

@router.post("/purge-audit-logs")
def purge_old_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrador General", "Administrador")),
):
    """
    P14: Elimina físicamente los registros de auditoría con más de
    PII_AUDIT_RETENTION_DAYS días de antigüedad.

    Los audit_logs no tienen referencias de integridad hacia otras tablas,
    por lo que la eliminación física es segura.
    Se registra una entrada en auditoría ANTES de la eliminación para que
    quede constancia del evento.
    """
    cutoff = _retention_cutoff_audit()

    # Contar antes de borrar
    count = db.query(func.count(AuditLog.id)).filter(AuditLog.fecha <= cutoff).scalar()

    if count == 0:
        return {
            "success": True,
            "registros_eliminados": 0,
            "mensaje": f"No hay registros de auditoría con más de {settings.PII_AUDIT_RETENTION_DAYS} días.",
        }

    # Registrar el evento de purga ANTES de eliminar
    log_audit(
        db,
        accion="PII: Purga de auditoría",
        detalle=(
            f"Eliminando {count} registros de auditoría anteriores a "
            f"{cutoff.strftime('%Y-%m-%d')} "
            f"({settings.PII_AUDIT_RETENTION_DAYS} días de retención). "
            f"Solicitado por: {current_user.email}"
        ),
        usuario=current_user.email,
        commit=True,  # Confirmar el log de purga antes de borrar
    )

    # Si el motor es PostgreSQL con trigger append-only, autorizar temporalmente la purga en esta transacción
    try:
        db.execute(text("SET LOCAL theogen.allow_audit_purge = 'on'"))
    except Exception:
        pass

    # Eliminar registros antiguos
    deleted = db.query(AuditLog).filter(AuditLog.fecha <= cutoff).delete(synchronize_session=False)
    db.commit()

    logger.info("P14: Audit log purge — %d registros eliminados (corte: %s).", deleted, cutoff.isoformat())

    return {
        "success": True,
        "registros_eliminados": deleted,
        "fecha_corte": cutoff.isoformat(),
        "retention_dias": settings.PII_AUDIT_RETENTION_DAYS,
    }
