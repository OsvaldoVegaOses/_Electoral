import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


def _migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "s3002_delivery_and_engine.py"
    )
    spec = importlib.util.spec_from_file_location("s2b_snapshot_migration", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_backfill_only_freezes_family_denominators_when_evidence_is_complete():
    engine = create_engine("sqlite://")
    migration = _migration()
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE elections "
            "(id INTEGER PRIMARY KEY, estado VARCHAR(50), regla_votacion VARCHAR(50), config_snapshot TEXT, total_padron_congelado INTEGER, total_habilitados_congelado INTEGER)"
        ))
        connection.execute(text(
            "CREATE TABLE voters "
            "(id INTEGER PRIMARY KEY, election_id INTEGER, familia_id VARCHAR(100))"
        ))
        connection.execute(text(
            "CREATE TABLE voting_entitlements "
            "(id INTEGER PRIMARY KEY, election_id INTEGER)"
        ))
        connection.execute(text(
            "INSERT INTO elections (id, estado, regla_votacion) VALUES "
            "(1, 'Finalizada', 'Un voto por familia'), "
            "(2, 'Finalizada', 'Un voto por familia'), "
            "(3, 'Finalizada', 'Un voto por persona')"
        ))
        connection.execute(text(
            "INSERT INTO voters (election_id, familia_id) VALUES "
            "(1, 'A'), (1, 'A'), (1, 'A'), (1, 'B'), (1, 'B'), "
            "(2, 'A'), (2, NULL), (3, NULL), (3, NULL)"
        ))

        with Operations.context(MigrationContext.configure(connection)):
            connection.execute(text("UPDATE elections SET total_padron_congelado=(SELECT COUNT(*) FROM voters WHERE voters.election_id=elections.id)"))
            connection.execute(text("UPDATE elections SET total_habilitados_congelado=total_padron_congelado WHERE regla_votacion='Un voto por persona'"))
            migration.repair_denominators(connection)

        counts = connection.execute(text(
            "SELECT id, total_padron_congelado, total_habilitados_congelado "
            "FROM elections ORDER BY id"
        )).all()

        assert counts == [(1, 5, 2), (2, 2, None), (3, 2, 2)]
