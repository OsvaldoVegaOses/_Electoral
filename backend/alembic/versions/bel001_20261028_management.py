"""ADR-001 isolated management tables; no rewriting historical votes or credentials."""
from alembic import op
import sqlalchemy as sa

revision = "bel001_20261028"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("belenios_bindings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("election_id", sa.Integer(), sa.ForeignKey("elections.id"), nullable=False, unique=True),
        sa.Column("reference", sa.String(32), nullable=False, unique=True),
        sa.Column("policy", sa.String(2), nullable=False), sa.Column("remote_uuid", sa.String(14)),
        sa.Column("phase", sa.String(32), nullable=False), sa.Column("inflight", sa.String(36)),
        sa.Column("draft_json", sa.Text(), nullable=False), sa.Column("approval_ref", sa.String(100), nullable=False),
        sa.Column("total_people", sa.Integer(), nullable=False), sa.Column("total_units", sa.Integer(), nullable=False),
        sa.Column("verified_result", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("policy", "remote_uuid", name="uq_belenios_remote"))
    op.create_table("belenios_units", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("binding_id", sa.Integer(), sa.ForeignKey("belenios_bindings.id"), nullable=False),
        sa.Column("representative_id", sa.Integer(), sa.ForeignKey("voters.id"), nullable=False),
        sa.Column("alias", sa.String(80), nullable=False),
        sa.UniqueConstraint("binding_id", "representative_id", name="uq_belenios_representative"),
        sa.UniqueConstraint("binding_id", "alias", name="uq_belenios_alias"))
    op.create_index("ix_belenios_units_binding_id", "belenios_units", ["binding_id"])
    op.create_table("belenios_operations", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("binding_id", sa.Integer(), sa.ForeignKey("belenios_bindings.id"), nullable=False),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False), sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_belenios_operations_binding_id", "belenios_operations", ["binding_id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM belenios_bindings")).scalar():
        raise RuntimeError("Hay vinculaciones Belenios: requiere respaldo y plan de retiro; no se eliminan automáticamente.")
    op.drop_table("belenios_operations")
    op.drop_table("belenios_units")
    op.drop_table("belenios_bindings")
