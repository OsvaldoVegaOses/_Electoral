"""S2-C: Agregar legal_hold a elections para bloqueo de anonimización

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e1
Create Date: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'elections',
        sa.Column('legal_hold', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade():
    op.drop_column('elections', 'legal_hold')
