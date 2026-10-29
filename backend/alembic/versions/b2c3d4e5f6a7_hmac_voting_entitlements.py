"""Replace clear-text entitlement unit identifiers with keyed digests.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
import hashlib
import hmac
import os
import re

from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _secret() -> bytes:
    value = os.getenv("ENTITLEMENT_HMAC_KEY", "")
    secret = value.encode("utf-8")
    if len(secret) < 32:
        raise RuntimeError(
            "ENTITLEMENT_HMAC_KEY de al menos 32 bytes es obligatoria para "
            "migrar los unit_key existentes."
        )
    if value in (os.getenv("SECRET_KEY"), os.getenv("VOTE_HMAC_KEY")) or value.startswith(("CHANGE_ME", "CAMBIAR")):
        raise RuntimeError("ENTITLEMENT_HMAC_KEY debe ser independiente y no un ejemplo.")
    return secret


def _digest(secret: bytes, election_id: int, canonical_unit: str) -> str:
    kind, separator, value = canonical_unit.partition(":")
    value = value.strip().upper()
    if kind == "RUT" and re.fullmatch(r"[0-9K.\s-]+", value):
        value = re.sub(r"[^0-9K]", "", value)
    elif kind != "FAM":
        raise RuntimeError("Se encontró un identificador electoral inválido; requiere conciliación.")
    if not separator or not value or any(ord(character) < 32 for character in value):
        raise RuntimeError("Se encontró un identificador electoral inválido; requiere conciliación.")
    canonical_unit = f"{kind}:{value}"
    message = (
        f"theogen-entitlement:v1:{election_id}:{canonical_unit}"
    ).encode("utf-8")
    return "h1:" + hmac.new(secret, message, hashlib.sha256).hexdigest()


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("LOCK TABLE voting_entitlements IN ACCESS EXCLUSIVE MODE"))
    rows = bind.execute(
        sa.text(
            "SELECT id, election_id, unit_key FROM voting_entitlements ORDER BY id"
        )
    ).mappings().all()
    if not rows:
        return
    secret = None
    transformed = []
    seen = set()
    # Validate the entire batch before the first UPDATE, including malformed
    # h1-prefixed values and collisions after normalization.
    for row in rows:
        key = row["unit_key"]
        if key.startswith("h1:"):
            if not re.fullmatch(r"h1:[0-9a-f]{64}", key):
                raise RuntimeError("Se encontró un identificador HMAC inválido; requiere conciliación.")
        else:
            if secret is None:
                secret = _secret()
            key = _digest(secret, row["election_id"], key)
            transformed.append({"id": row["id"], "unit_key": key})
        identity = (row["election_id"], key)
        if identity in seen:
            raise RuntimeError("Colisión de identificadores electorales; requiere conciliación sin perder derechos.")
        seen.add(identity)
    for row in transformed:
        bind.execute(
            sa.text(
                "UPDATE voting_entitlements SET unit_key = :unit_key WHERE id = :id"
            ),
            row,
        )


def downgrade() -> None:
    bind = op.get_bind()
    hashed_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM voting_entitlements WHERE unit_key LIKE 'h1:%'"
        )
    ).scalar_one()
    if hashed_count:
        raise RuntimeError(
            "La migración HMAC es irreversible sin restaurar el respaldo "
            "protegido previo; no se modificó la base de datos."
        )
