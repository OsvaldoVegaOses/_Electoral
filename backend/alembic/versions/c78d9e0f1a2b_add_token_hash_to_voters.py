"""add_token_hash_to_voters

Revision ID: c78d9e0f1a2b
Revises: a65f5ab1bc4a
Create Date: 2026-10-27 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c78d9e0f1a2b'
down_revision: Union[str, Sequence[str], None] = 'a65f5ab1bc4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: agrega columna token_hash con índice único para credenciales de sufragio seguras (P8)."""
    op.add_column('voters', sa.Column('token_hash', sa.String(length=128), nullable=True))
    op.create_index(op.f('ix_voters_token_hash'), 'voters', ['token_hash'], unique=True)


def downgrade() -> None:
    """Downgrade schema: elimina índice y columna token_hash."""
    op.drop_index(op.f('ix_voters_token_hash'), table_name='voters')
    op.drop_column('voters', 'token_hash')
