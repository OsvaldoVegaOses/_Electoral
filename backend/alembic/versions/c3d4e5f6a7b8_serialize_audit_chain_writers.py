"""Serialize audit-chain writers using a PostgreSQL row lock.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    legacy_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM audit_logs "
            "WHERE prev_hash IS NULL OR record_hash IS NULL"
        )
    ).scalar_one()
    if legacy_count:
        raise RuntimeError(
            "La bitácora contiene eventos legacy sin hash. Se bloqueó la migración "
            "para no crear una génesis falsa; requiere reconciliación y respaldo "
            "aprobados antes de habilitar la cadena."
        )

    op.create_table(
        "audit_chain_heads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("head_hash", sa.String(length=64), nullable=False),
        sa.Column("last_log_id", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    last_log = bind.execute(
        sa.text(
            "SELECT id, record_hash FROM audit_logs ORDER BY id DESC LIMIT 1"
        )
    ).first()
    head_hash = last_log.record_hash if last_log and last_log.record_hash else "0" * 64
    last_log_id = last_log.id if last_log else None
    bind.execute(
        sa.text(
            "INSERT INTO audit_chain_heads (id, head_hash, last_log_id) "
            "VALUES (1, :head_hash, :last_log_id)"
        ),
        {"head_hash": head_hash, "last_log_id": last_log_id},
    )


def downgrade() -> None:
    op.drop_table("audit_chain_heads")
