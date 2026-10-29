import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def _migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "c3d4e5f6a7b8_serialize_audit_chain_writers.py"
    )
    spec = importlib.util.spec_from_file_location("s2d_audit_migration", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_migration_refuses_unhashed_legacy_events_without_mutating_them():
    engine = create_engine("sqlite://")
    migration = _migration()
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE audit_logs "
            "(id INTEGER PRIMARY KEY, prev_hash VARCHAR(64), record_hash VARCHAR(64))"
        ))
        connection.execute(text(
            "INSERT INTO audit_logs (id, prev_hash, record_hash) VALUES (1, NULL, NULL)"
        ))

        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="génesis falsa"):
                migration.upgrade()

        row = connection.execute(
            text("SELECT prev_hash, record_hash FROM audit_logs WHERE id = 1")
        ).one()
        assert row == (None, None)
        assert "audit_chain_heads" not in inspect(connection).get_table_names()


def test_migration_initializes_empty_audit_chain_head():
    engine = create_engine("sqlite://")
    migration = _migration()
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE audit_logs "
            "(id INTEGER PRIMARY KEY, prev_hash VARCHAR(64), record_hash VARCHAR(64))"
        ))

        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        head = connection.execute(text(
            "SELECT head_hash, last_log_id FROM audit_chain_heads WHERE id = 1"
        )).one()
        assert head == ("0" * 64, None)
