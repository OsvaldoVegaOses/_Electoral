"""P15: add hash chain to audit_logs and append-only trigger

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-27 19:15:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Agregar columnas de encadenamiento criptográfico a audit_logs
    op.add_column('audit_logs', sa.Column('prev_hash', sa.String(length=64), nullable=True))
    op.add_column('audit_logs', sa.Column('record_hash', sa.String(length=64), nullable=True))
    op.create_index('ix_audit_logs_record_hash', 'audit_logs', ['record_hash'])

    # 2. En PostgreSQL: instalar función y disparador que prohíbe UPDATE y DELETE (append-only)
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("""
        CREATE OR REPLACE FUNCTION audit_logs_prevent_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF current_setting('theogen.allow_audit_purge', true) = 'on' THEN
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
            END IF;
            RAISE EXCEPTION 'Tabla audit_logs es append-only. Operacion % denegada por politica de inmutabilidad.', TG_OP;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs;
        CREATE TRIGGER trg_audit_logs_append_only
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION audit_logs_prevent_mutation();
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("""
        DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs;
        DROP FUNCTION IF EXISTS audit_logs_prevent_mutation();
        """)

    op.drop_index('ix_audit_logs_record_hash', table_name='audit_logs')
    op.drop_column('audit_logs', 'record_hash')
    op.drop_column('audit_logs', 'prev_hash')
