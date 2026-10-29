"""
P14 / S2-C: Router de Administración de PII (Retención y Eliminación de Datos Personales)

Endpoints solo para Administrador General:
- GET  /admin/pii/elections-ready-for-anonymization  — Lista elecciones candidatas
- POST /admin/pii/anonymize-election/{election_id}   — Anonimiza padrón y comisión
- POST /admin/pii/purge-audit-logs                   — Simula candidatos; purga física bloqueada
- GET  /admin/pii/status                             — Resumen del estado de PII en el sistema
"""
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Voter, ElectoralCommittee, Election, AuditLog, User, VotingEntitlement
from app.auth import get_current_user, log_audit, require_role, is_superadmin
from app.config import settings

logger = logging.getLogger("theogen.pii")

router = APIRouter(prefix="/admin/pii", tags=["Administración PII"])

_ANON_RUT = "[ANONIMIZADO]"
_ANON_NOMBRE_VOTER = "[Elector Anonimizado]"
_ANON_NOMBRE_COMISION = "[Comisionado Anonimizado]"


def _retention_cutoff_voter() -> datetime:
    """S2-C: Fecha límite calc. desde ahora (usada internamente para configuración)."""
    return datetime.now(timezone.utc) - timedelta(days=settings.PII_VOTER_RETENTION_DAYS)


def _retention_cutoff_audit() -> datetime:
    """Fecha límite: registros de auditoría con más de PII_AUDIT_RETENTION_DAYS días."""
    return datetime.now(timezone.utc) - timedelta(days=settings.PII_AUDIT_RETENTION_DAYS)


def _election_retention_reference_date(election: Election):
    """
    S2-C: Retorna la fecha autoritativa de referencia para calcular retención.
    Usa fecha_cierre_efectiva o fecha_fin. Sin fecha de cierre verificable, no se
    puede establecer elegibilidad y la anonimización queda bloqueada.
    """
    return election.fecha_cierre_efectiva or election.fecha_fin


def _retention_has_elapsed(election: Election, now: datetime) -> bool:
    reference_date = _election_retention_reference_date(election)
    if reference_date is None:
        return False
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)
    return now - reference_date >= timedelta(days=settings.PII_VOTER_RETENTION_DAYS)


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
    now = datetime.now(timezone.utc)
    # Padrón con PII aún vigente
    voters_with_pii = db.query(func.count(Voter.id)).filter(
        Voter.pii_eliminado_en == None  # noqa: E711
    ).scalar()

    # Padrón ya anonimizado
    voters_anonymized = db.query(func.count(Voter.id)).filter(
        Voter.pii_eliminado_en != None  # noqa: E711
    ).scalar()

    # S2-C: Electores candidatos a anonimización basado en fecha_fin/fecha_cierre_efectiva
    all_finalized = db.query(Election).filter(Election.estado == "Finalizada").all()
    voters_ready = 0
    for e in all_finalized:
        if not e.legal_hold and _retention_has_elapsed(e, now):
            count = db.query(func.count(Voter.id)).filter(
                Voter.election_id == e.id,
                Voter.pii_eliminado_en == None  # noqa: E711
            ).scalar()
            voters_ready += count

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
    P14 / S2-C: Lista las elecciones cuyo período de retención de PII ha vencido
    basado en fecha_cierre_efectiva o fecha_fin (no en fecha_creacion).
    """
    # S2-C: Obtener todas las elecciones Finalizadas y filtrar en Python por fecha de referencia real
    elections = (
        db.query(Election)
        .filter(
            Election.estado == "Finalizada",
            Election.legal_hold.is_(False),
        )
        .all()
    )

    result = []
    now = datetime.now(timezone.utc)
    for e in elections:
        # S2-C: Calcular antigüedad desde la fecha de referencia correcta
        ref_date = _election_retention_reference_date(e)
        if ref_date is None:
            continue
        if ref_date.tzinfo is None:
            ref_date = ref_date.replace(tzinfo=timezone.utc)
        days_elapsed = (now - ref_date).days
        if days_elapsed < settings.PII_VOTER_RETENTION_DAYS:
            continue  # Aún dentro del período de retención

        pending_voters = db.query(func.count(Voter.id)).filter(
            Voter.election_id == e.id,
            Voter.pii_eliminado_en == None  # noqa: E711
        ).scalar()

        if pending_voters > 0:
            result.append({
                "election_id": e.id,
                "nombre": e.nombre,
                "estado": e.estado,
                "fecha_referencia_retencion": ref_date.isoformat(),
                "legal_hold": bool(e.legal_hold),
                "electores_pendientes_anonimizacion": pending_voters,
                "dias_desde_cierre": days_elapsed,
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
    dry_run: bool = Query(False, description="Simula la operación sin modificar la base de datos"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrador General", "Administrador")),
):
    """
    P14: Anonimiza los datos personales del padrón y la comisión electoral
    de una elección específica.
    S2-A: Bloqueo seguro en producción por defecto hasta completar PR S2-C.
    Permite simulación segura con ?dry_run=true.
    """
    if not dry_run and settings.ENVIRONMENT == "production" and not getattr(settings, "PII_OPERATIONS_MUTATIONS_ENABLED", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Operaciones destructivas de PII deshabilitadas por defecto en producción "
                "(contención de seguridad S2-A) hasta completar PR S2-C. "
                "Para simular sin alterar registros utilice el parámetro ?dry_run=true."
            ),
        )

    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada.")

    if election.estado != "Finalizada":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Solo se pueden anonimizar elecciones en estado 'Finalizada'. "
                   f"Estado actual: '{election.estado}'.",
        )

    # S2-C: Bloqueo por legal hold
    if election.legal_hold:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Anonimización bloqueada: esta elección tiene un legal hold activo. "
                   "Contacte al responsable legal antes de eliminar datos personales.",
        )

    now = datetime.now(timezone.utc)
    if not _retention_has_elapsed(election, now):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Anonimización bloqueada: el plazo de retención no ha vencido "
                "o la elección carece de una fecha de cierre verificable."
            ),
        )

    # S2-C: Identificar electores con PII vigente (idempotencia: solo los que no han sido anonimizados)
    voters_to_anon = db.query(Voter).filter(
        Voter.election_id == election_id,
        Voter.pii_eliminado_en == None  # noqa: E711
    ).all()
    voters_count = len(voters_to_anon)

    # 2. Identificar miembros de la comisión electoral
    committees_to_anon = db.query(ElectoralCommittee).filter(
        ElectoralCommittee.election_id == election_id,
        ElectoralCommittee.pii_eliminado_en == None  # noqa: E711
    ).all()
    committees_count = len(committees_to_anon)

    # Modo simulación (Dry Run)
    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "election_id": election_id,
            "election_nombre": election.nombre,
            "electores_que_serian_anonimizados": voters_count,
            "comisionados_que_serian_anonimizados": committees_count,
            "mensaje": "Simulación exitosa: ningún registro fue modificado en la base de datos.",
        }

    for voter in voters_to_anon:
        voter.rut = _ANON_RUT
        # S2-C: rut_normalizado debe quedar NULL para evitar colisión en UniqueConstraint(election_id, rut_normalizado)
        # SQL estándar garantiza que múltiples NULL no colisionan en restricciones únicas
        voter.rut_normalizado = None
        voter.nombre = _ANON_NOMBRE_VOTER
        voter.correo = None
        voter.familia_id = None
        voter.token_votacion = None  # S2-C: eliminar texto claro de tokens tras anonimización
        voter.token_hash = None      # El hash ya no tiene utilidad tras PII (no se puede votar en Finalizada)
        voter.pii_eliminado_en = now

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
        "dry_run": False,
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
    dry_run: bool = Query(False, description="Simula la purga sin eliminar registros de la base de datos"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrador General", "Administrador")),
):
    """
    P14: Elimina físicamente los registros de auditoría con más de
    PII_AUDIT_RETENTION_DAYS días de antigüedad.
    S2-A: Bloqueo seguro en producción por defecto hasta completar PR S2-C.
    Permite simulación segura con ?dry_run=true.
    """
    if not dry_run and settings.ENVIRONMENT == "production" and not getattr(settings, "PII_OPERATIONS_MUTATIONS_ENABLED", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Operaciones destructivas de PII deshabilitadas por defecto en producción "
                "(contención de seguridad S2-A) hasta completar PR S2-C. "
                "Para simular sin alterar registros utilice el parámetro ?dry_run=true."
            ),
        )

    cutoff = _retention_cutoff_audit()

    # Contar antes de borrar
    count = db.query(func.count(AuditLog.id)).filter(AuditLog.fecha <= cutoff).scalar()

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "registros_que_serian_eliminados": count,
            "fecha_corte": cutoff.isoformat(),
            "retention_dias": settings.PII_AUDIT_RETENTION_DAYS,
            "mensaje": (
                "Simulación únicamente. La purga está bloqueada hasta implementar "
                "retención por épocas y verificar un checkpoint externo."
            ),
        }

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Purga de auditoría bloqueada: la cadena no implementa aún retención "
            "por épocas con checkpoint externo verificado. Use dry_run=true; "
            "no se eliminó ningún registro."
        ),
    )
