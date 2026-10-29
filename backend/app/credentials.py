from fastapi import HTTPException, status

from app.config import settings


def require_credential_delivery() -> None:
    if settings.ENVIRONMENT == "production" and not (
        settings.BREVO_DELIVERY_ENABLED and settings.BREVO_API_KEY.get_secret_value()
        and settings.BREVO_SENDER_EMAIL and settings.PUBLIC_VOTING_URL.startswith("https://")
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Emisión de credenciales bloqueada: no existe un canal real de "
                "entrega de un solo uso configurado y probado."
            ),
        )


def issue(db, voter, election, operation_id, *, sender=None):
    """Persist an intent/hash before sending. Clear token exists only in this call's memory."""
    from uuid import UUID
    import secrets
    from sqlalchemy.exc import IntegrityError
    from app.models import CredentialDelivery, Election, Voter
    from app.auth import hash_voting_token, log_audit
    from app import brevo
    require_credential_delivery()
    key = str(UUID(str(operation_id)))
    # Use the same election-first lock order as opening. Refresh stale ORM state.
    election = db.query(Election).filter_by(id=election.id).populate_existing().with_for_update().one()
    voter = db.query(Voter).filter_by(id=voter.id).populate_existing().with_for_update().one()
    if election.estado != "Borrador" or election.motor != "mvp" or voter.estado != "Pendiente":
        raise HTTPException(409, "La emisión/reemisión requiere un padrón MVP en borrador sin voto.")
    if not voter.correo:
        raise HTTPException(422, "El elector requiere un correo de entrega.")
    if db.get(CredentialDelivery, key):
        raise HTTPException(409, "Operación registrada; consulte y concilie, no repita el envío.")
    raw = secrets.token_urlsafe(32)
    operation = CredentialDelivery(id=key, voter_id=voter.id, previous_hash=voter.token_hash,
                                  proposed_hash=hash_voting_token(raw), status="PENDING", active_slot=str(voter.id))
    db.add(operation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Existe una entrega pendiente para este elector.") from None
    try:
        accepted = (sender or brevo.send_credential)(voter.correo, raw, key)
    except brevo.DeliveryRejected:
        operation.status, operation.active_slot = "REJECTED", None
    except Exception:
        # Lost response, process recovery or malformed acceptance never revokes the previous token.
        operation.status = "UNKNOWN"
    else:
        operation.status, operation.message_id = "ACCEPTED", accepted.message_id
    finally:
        del raw
    log_audit(db, accion="Entrega de credencial", detalle="Operación " + key + ": " + operation.status,
              school_id=election.school_id, commit=False)
    db.commit()
    return operation


def reconcile(db, operation, voter, election, *, checker=None):
    from datetime import datetime, timezone
    from app import brevo
    from app.models import CredentialDelivery, Election, Voter
    from app.auth import log_audit
    election = db.query(Election).filter_by(id=election.id).populate_existing().with_for_update().one()
    voter = db.query(Voter).filter_by(id=voter.id).populate_existing().with_for_update().one()
    operation = db.query(CredentialDelivery).filter_by(id=operation.id).populate_existing().with_for_update().one()
    if operation.status == "DELIVERED":
        return operation
    if operation.status not in ("PENDING", "ACCEPTED", "UNKNOWN"):
        raise HTTPException(409, "La operación no admite conciliación.")
    if election.estado != "Borrador" or election.motor != "mvp" or voter.estado != "Pendiente" or voter.token_hash != operation.previous_hash:
        raise HTTPException(409, "Cambió el estado o la credencial; no se revocó ni activó otra.")
    try:
        message = (checker or brevo.confirmed_delivery)(voter.correo, operation.id, operation.message_id)
    except (brevo.DeliveryUnknown, brevo.DeliveryRejected):
        raise HTTPException(503, "Entrega sin confirmar; la credencial previa se conserva.") from None
    if not message:
        raise HTTPException(409, "El proveedor aún no acredita entrega para esta operación.")
    voter.token_hash, voter.token_votacion = operation.proposed_hash, None
    operation.status, operation.message_id, operation.active_slot = "DELIVERED", message, None
    operation.confirmed_at = datetime.now(timezone.utc)
    log_audit(db, accion="Concilió entrega de credencial", detalle="Operación " + operation.id + ": DELIVERED",
              school_id=election.school_id, commit=False)
    db.commit()
    return operation
