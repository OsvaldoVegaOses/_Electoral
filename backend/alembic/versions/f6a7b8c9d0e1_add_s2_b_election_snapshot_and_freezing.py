"""S2-B: add snapshot and frozen denominator columns to elections

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-27 22:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('elections', sa.Column('fecha_cierre_efectiva', sa.DateTime(timezone=True), nullable=True))
    op.add_column('elections', sa.Column('total_padron_congelado', sa.Integer(), nullable=True))
    op.add_column('elections', sa.Column('total_habilitados_congelado', sa.Integer(), nullable=True))
    op.add_column('elections', sa.Column('config_snapshot', sa.Text(), nullable=True))

    # Backfill para elecciones ya abiertas, cerradas o finalizadas
    bind = op.get_bind()
    try:
        # 1. Total padrón congelado desde votantes
        bind.execute(sa.text("""
            UPDATE elections
            SET total_padron_congelado = (
                SELECT COUNT(*) FROM voters WHERE voters.election_id = elections.id
            )
            WHERE estado IN ('Abierta', 'Cerrada', 'Finalizada')
              AND total_padron_congelado IS NULL
        """))

        # 2. Total habilitados congelado desde entitlements si existen
        bind.execute(sa.text("""
            UPDATE elections
            SET total_habilitados_congelado = (
                SELECT COUNT(*) FROM voting_entitlements WHERE voting_entitlements.election_id = elections.id
            )
            WHERE estado IN ('Abierta', 'Cerrada', 'Finalizada')
              AND total_habilitados_congelado IS NULL
              AND EXISTS (SELECT 1 FROM voting_entitlements WHERE voting_entitlements.election_id = elections.id)
        """))

        # 3. Si no hay entitlements (elección previa a PR3), calcular según regla
        bind.execute(sa.text("""
            UPDATE elections
            SET total_habilitados_congelado = total_padron_congelado
            WHERE estado IN ('Abierta', 'Cerrada', 'Finalizada')
              AND total_habilitados_congelado IS NULL
              AND regla_votacion = 'Un voto por persona'
        """))
    except Exception:
        pass


def downgrade() -> None:
    op.drop_column('elections', 'config_snapshot')
    op.drop_column('elections', 'total_habilitados_congelado')
    op.drop_column('elections', 'total_padron_congelado')
    op.drop_column('elections', 'fecha_cierre_efectiva')
