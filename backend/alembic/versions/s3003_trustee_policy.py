"""Record explicit trustee policy without inventing approval for legacy bindings."""
from alembic import op
import sqlalchemy as sa

revision = "s3003_trustees"
down_revision = "s3002_delivery"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("belenios_bindings", sa.Column("trustee_policy_json", sa.Text(), nullable=True))


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM belenios_bindings WHERE trustee_policy_json IS NOT NULL")).scalar_one():
        raise RuntimeError("Existen políticas de custodia: requiere respaldo y plan de retiro aprobado.")
    op.drop_column("belenios_bindings", "trustee_policy_json")
