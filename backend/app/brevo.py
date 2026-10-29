"""Brevo transactional transport. Acceptance is not proof of delivery.

This transport does not activate production credential issuance by itself.
Provisioning/outbox and reconciliation must be integrated before removing its guard.
"""
from dataclasses import dataclass
from uuid import UUID
from urllib.parse import urlsplit

import httpx

from app.config import settings
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)


class DeliveryRejected(RuntimeError):
    """Provider explicitly rejected the request; no response body is exposed."""


class DeliveryUnknown(RuntimeError):
    """Acceptance is indeterminate. Never retry automatically or rotate a token."""


@dataclass(frozen=True)
class AcceptedMessage:
    message_id: str
    status: str = "accepted"


def send_credential(recipient: str, raw_token: str, operation_id: str,
                    *, transport: httpx.BaseTransport | None = None) -> AcceptedMessage:
    if not settings.BREVO_DELIVERY_ENABLED:
        raise DeliveryRejected("Brevo está deshabilitado.")
    key = settings.BREVO_API_KEY.get_secret_value()
    url = urlsplit(settings.PUBLIC_VOTING_URL)
    if (not key or not settings.BREVO_SENDER_EMAIL or "@" not in settings.BREVO_SENDER_EMAIL
            or url.scheme != "https" or not url.hostname or url.query or url.fragment or url.username):
        raise DeliveryRejected("Configuración de entrega incompleta o inválida.")
    if not recipient or "@" not in recipient or any(c in recipient for c in "\r\n"):
        raise DeliveryRejected("Destinatario inválido.")
    # Only an opaque UUID is sent as the provider's finite-window idempotency key.
    operation_id = str(UUID(operation_id))
    payload = {
        "sender": {"name": settings.BREVO_SENDER_NAME, "email": settings.BREVO_SENDER_EMAIL},
        "to": [{"email": recipient}],
        "subject": "Credencial de acceso electoral",
        "textContent": ("Ingrese su credencial en " + settings.PUBLIC_VOTING_URL +
                        "\n\nCredencial: " + raw_token +
                        "\n\nNo comparta esta credencial. No responda con ella a este correo."),
        "headers": {"idempotencyKey": operation_id},
        "tags": ["theogen-" + operation_id],
    }
    try:
        with httpx.Client(transport=transport or httpx.HTTPTransport(local_address="0.0.0.0"), timeout=15, follow_redirects=False, trust_env=False) as client:
            response = client.post("https://api.brevo.com/v3/smtp/email",
                                   headers={"api-key": key, "accept": "application/json"}, json=payload)
    except httpx.HTTPError:
        raise DeliveryUnknown("Resultado de entrega indeterminado; requiere conciliación.") from None
    if response.status_code in (400, 401, 403, 404, 422, 429):
        # A duplicate request can refer to a previously accepted email.
        try:
            duplicate = response.json().get("code") == "duplicate_parameter"
        except (ValueError, AttributeError):
            duplicate = False
        if duplicate:
            raise DeliveryUnknown("Solicitud duplicada; conciliar aceptación previa.")
        raise DeliveryRejected(f"Brevo rechazó la solicitud (HTTP {response.status_code}).")
    if response.status_code != 201:
        raise DeliveryUnknown("Respuesta de entrega indeterminada; requiere conciliación.")
    try:
        message_id = response.json()["messageId"]
        if not isinstance(message_id, str) or not message_id.strip():
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise DeliveryUnknown("Aceptación sin identificador verificable; requiere conciliación.") from None
    return AcceptedMessage(message_id)


def confirmed_delivery(recipient: str, operation_id: str, message_id: str | None = None,
                       *, transport: httpx.BaseTransport | None = None) -> str | None:
    """A provider event must match recipient AND opaque operation tag AND message ID."""
    if not settings.BREVO_DELIVERY_ENABLED or not settings.BREVO_API_KEY.get_secret_value():
        raise DeliveryRejected("Brevo está deshabilitado.")
    tag = "theogen-" + str(UUID(operation_id))
    params = {"email": recipient, "tags": tag, "event": "delivered", "days": 30, "limit": 100}
    if message_id:
        params["messageId"] = message_id
    try:
        with httpx.Client(transport=transport or httpx.HTTPTransport(local_address="0.0.0.0"), timeout=15, follow_redirects=False, trust_env=False) as client:
            response = client.get("https://api.brevo.com/v3/smtp/statistics/events", params=params,
                                  headers={"api-key": settings.BREVO_API_KEY.get_secret_value()})
        if response.status_code != 200:
            raise DeliveryUnknown("No se pudo confirmar la entrega; no se reenvió.")
        matches = {event["messageId"] for event in response.json().get("events", [])
                   if event.get("event") == "delivered" and event.get("email", "").lower() == recipient.lower()
                   and event.get("tag") == tag and isinstance(event.get("messageId"), str)
                   and (message_id is None or event["messageId"] == message_id)}
        if len(matches) > 1:
            raise DeliveryUnknown("Hay múltiples mensajes: requiere revisión del proveedor.")
        return next(iter(matches), None)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        raise DeliveryUnknown("No se pudo confirmar la entrega; no se reenvió.") from None
