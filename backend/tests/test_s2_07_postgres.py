"""Migration, wrong-key and recovery contracts on a disposable PostgreSQL DB."""
import importlib.util
import os
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from app.config import settings
from app.entitlements import derive_entitlement_key


DATABASE_URL = os.getenv("S2_PRIVACY_DATABASE_URL", "")
if not DATABASE_URL.startswith("postgresql"):
    if os.getenv("REQUIRE_S2_SERVICES") == "1":
        raise RuntimeError("S2_PRIVACY_DATABASE_URL es obligatoria en integración.")
    pytest.skip("S2_PRIVACY_DATABASE_URL no configurada", allow_module_level=True)


def _migration():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/b2c3d4e5f6a7_hmac_voting_entitlements.py"
    spec = importlib.util.spec_from_file_location("s207_pg_migration", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.fixture
def legacy_table():
    engine = create_engine(DATABASE_URL)
    # Each test owns its schema, never a shared application table.
    from uuid import uuid4
    schema = "s207_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        connection.execute(text("CREATE TABLE voting_entitlements (id INTEGER PRIMARY KEY, "
                                "election_id INTEGER NOT NULL, unit_key VARCHAR(100) NOT NULL, "
                                "estado TEXT, voter_id_consumidor INTEGER, "
                                "UNIQUE(election_id, unit_key))"))
        connection.execute(text("INSERT INTO voting_entitlements VALUES "
                                "(1,41,'RUT:12.345.678-5','Consumido',99),"
                                "(2,41,'FAM: family-1 ','Pendiente',NULL),"
                                "(3,42,'FAM:FAMILY-1','Pendiente',NULL)"))
    try:
        yield engine, schema
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_postgres_backfill_preserves_consumption_and_is_idempotent(legacy_table):
    engine, schema = legacy_table
    migration = _migration()
    with engine.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        rows = connection.execute(text("SELECT id,election_id,unit_key,estado,voter_id_consumidor "
                                       "FROM voting_entitlements ORDER BY id")).all()
        assert rows == [
            (1, 41, derive_entitlement_key(41, "RUT:123456785"), "Consumido", 99),
            (2, 41, derive_entitlement_key(41, "FAM:FAMILY-1"), "Pendiente", None),
            (3, 42, derive_entitlement_key(42, "FAM:FAMILY-1"), "Pendiente", None),
        ]
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="respaldo protegido"):
                migration.downgrade()
        assert connection.execute(text("SELECT count(*) FROM voting_entitlements")).scalar_one() == 3


def test_postgres_missing_key_leaves_all_rows_unchanged(legacy_table, monkeypatch):
    engine, schema = legacy_table
    monkeypatch.delenv("ENTITLEMENT_HMAC_KEY", raising=False)
    with engine.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        before = connection.execute(text("SELECT * FROM voting_entitlements ORDER BY id")).all()
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="ENTITLEMENT_HMAC_KEY"):
                _migration().upgrade()
        assert connection.execute(text("SELECT * FROM voting_entitlements ORDER BY id")).all() == before


def test_postgres_collision_is_rejected_without_partial_backfill(legacy_table):
    engine, schema = legacy_table
    with engine.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        connection.execute(text("INSERT INTO voting_entitlements VALUES "
                                "(4,41,'FAM:FAMILY-1','Consumido',100)"))
        before = connection.execute(text("SELECT * FROM voting_entitlements ORDER BY id")).all()
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="Colisión"):
                _migration().upgrade()
        assert connection.execute(text("SELECT * FROM voting_entitlements ORDER BY id")).all() == before


def test_postgres_restored_key_resolves_the_same_persisted_right(legacy_table, monkeypatch):
    engine, schema = legacy_table
    migration = _migration()
    original = settings.ENTITLEMENT_HMAC_KEY
    with engine.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        stored = connection.execute(text("SELECT unit_key FROM voting_entitlements WHERE id=1")).scalar_one()
    monkeypatch.setattr(settings, "ENTITLEMENT_HMAC_KEY", "s207-wrong-restored-key-" + "x" * 40)
    assert derive_entitlement_key(41, "RUT:123456785") != stored
    monkeypatch.setattr(settings, "ENTITLEMENT_HMAC_KEY", original)
    assert derive_entitlement_key(41, "RUT:123456785") == stored
