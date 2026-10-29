import hashlib
import hmac
import re

from fastapi import HTTPException

from app.config import settings


def canonicalize_unit(unit: str) -> str:
    """Canonicalize both runtime input and legacy RUT/FAM identifiers."""
    kind, separator, value = unit.partition(":")
    value = value.strip().upper()
    if kind == "RUT" and re.fullmatch(r"[0-9K.\s-]+", value):
        value = re.sub(r"[^0-9K]", "", value)
    elif kind != "FAM":
        raise ValueError("Tipo de unidad electoral inválido.")
    if not separator or not value or any(ord(character) < 32 for character in value):
        raise ValueError("Unidad electoral vacía o inválida.")
    return f"{kind}:{value}"


def derive_entitlement_key(election_id: int, canonical_unit: str) -> str:
    """Deriva un identificador estable y opaco por elección y unidad electoral."""
    secret = settings.ENTITLEMENT_HMAC_KEY
    if (len(secret.encode("utf-8")) < 32
            or secret in (settings.SECRET_KEY, settings.VOTE_HMAC_KEY)
            or secret.startswith(("CHANGE_ME", "CAMBIAR"))):
        raise HTTPException(503, "Derechos electorales no disponibles: configure la clave persistente independiente.")
    canonical_unit = canonicalize_unit(canonical_unit)
    message = f"theogen-entitlement:v1:{election_id}:{canonical_unit}".encode("utf-8")
    digest = hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return f"h1:{digest}"
