"""Explicit engine intent, durable delivery intents and conservative legacy repair."""
from alembic import op
import sqlalchemy as sa

revision = "s3002_delivery"
down_revision = "s3001_merge"
branch_labels = None
depends_on = None

def repair_denominators(bind):
    # Only legacy rows without a canonical snapshot may be reconstructed.
    bind.execute(sa.text("""UPDATE elections SET total_habilitados_congelado = (
        SELECT COUNT(DISTINCT UPPER(TRIM(familia_id))) FROM voters WHERE election_id=elections.id)
        WHERE config_snapshot IS NULL AND total_habilitados_congelado IS NULL
        AND regla_votacion='Un voto por familia' AND estado IN ('Abierta','Cerrada','Finalizada')
        AND EXISTS (SELECT 1 FROM voters WHERE election_id=elections.id)
        AND NOT EXISTS (SELECT 1 FROM voters WHERE election_id=elections.id
                        AND (familia_id IS NULL OR TRIM(familia_id)=''))"""))
    bind.execute(sa.text("""UPDATE elections SET total_padron_congelado=NULL,
        total_habilitados_congelado=NULL WHERE config_snapshot IS NULL
        AND total_padron_congelado=0
        AND NOT EXISTS (SELECT 1 FROM voters WHERE election_id=elections.id)
        AND NOT EXISTS (SELECT 1 FROM voting_entitlements WHERE election_id=elections.id)"""))

def upgrade():
    bind=op.get_bind()
    repair_denominators(bind)
    if bind.dialect.name == 'postgresql':
        # The former session GUC was user-settable. Purge remains disabled until epochs exist.
        bind.execute(sa.text("""CREATE OR REPLACE FUNCTION audit_logs_prevent_mutation()
            RETURNS trigger AS $$ BEGIN
            RAISE EXCEPTION 'audit_logs es append-only; purga y cambios bloqueados';
            END; $$ LANGUAGE plpgsql"""))
    op.add_column('elections',sa.Column('motor',sa.String(16),nullable=False,server_default='mvp'))
    bind.execute(sa.text("UPDATE elections SET motor='belenios' WHERE id IN (SELECT election_id FROM belenios_bindings)"))
    op.create_table('credential_deliveries',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('voter_id',sa.Integer(),sa.ForeignKey('voters.id'),nullable=False),
        sa.Column('previous_hash',sa.String(128)),sa.Column('proposed_hash',sa.String(128),nullable=False),
        sa.Column('status',sa.String(24),nullable=False),sa.Column('message_id',sa.String(255)),
        sa.Column('active_slot',sa.String(50),unique=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('confirmed_at',sa.DateTime(timezone=True)))
    op.create_index('ix_credential_deliveries_voter_id','credential_deliveries',['voter_id'])

def downgrade():
    bind=op.get_bind()
    if bind.execute(sa.text('SELECT COUNT(*) FROM credential_deliveries')).scalar_one():
        raise RuntimeError('Existen operaciones de entrega: requiere respaldo y plan de retiro aprobado.')
    if bind.execute(sa.text("SELECT COUNT(*) FROM elections WHERE motor='belenios'")).scalar_one():
        raise RuntimeError('Existen elecciones Belenios: requiere respaldo y plan de retiro aprobado.')
    op.drop_table('credential_deliveries')
    op.drop_column('elections','motor')
