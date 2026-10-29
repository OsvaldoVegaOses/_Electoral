"""P14: add pii_eliminado_en to voters and electoral_committees

Revision ID: d4e5f6a7b8c9
Revises: c78d9e0f1a2b
Create Date: 2026-10-27 18:07:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c78d9e0f1a2b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Columna de marca de tiempo de anonimización en voters
    op.add_column(
        'voters',
        sa.Column('pii_eliminado_en', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_voters_pii_eliminado_en', 'voters', ['pii_eliminado_en'])

    # Columna de marca de tiempo de anonimización en electoral_committees
    op.add_column(
        'electoral_committees',
        sa.Column('pii_eliminado_en', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        'ix_electoral_committees_pii_eliminado_en',
        'electoral_committees',
        ['pii_eliminado_en']
    )


def downgrade() -> None:
    op.drop_index('ix_electoral_committees_pii_eliminado_en', table_name='electoral_committees')
    op.drop_column('electoral_committees', 'pii_eliminado_en')
    op.drop_index('ix_voters_pii_eliminado_en', table_name='voters')
    op.drop_column('voters', 'pii_eliminado_en')
