import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


@pytest.fixture
def migration():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "b2c3d4e5f6a7_hmac_voting_entitlements.py"
    )
    spec = importlib.util.spec_from_file_location("s2c_entitlement_migration", module_path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_hmac_backfill_fails_closed_without_key_and_is_not_silently_reversible(
    migration, monkeypatch
):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE voting_entitlements "
            "(id INTEGER PRIMARY KEY, election_id INTEGER NOT NULL, unit_key VARCHAR(100) NOT NULL)"
        ))
        connection.execute(text(
            "INSERT INTO voting_entitlements (id, election_id, unit_key) "
            "VALUES (1, 41, 'RUT:12345678-5'), (2, 41, 'FAM:FAM-9')"
        ))

        monkeypatch.delenv("ENTITLEMENT_HMAC_KEY", raising=False)
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="ENTITLEMENT_HMAC_KEY"):
                migration.upgrade()

        unchanged = connection.execute(
            text("SELECT unit_key FROM voting_entitlements ORDER BY id")
        ).scalars().all()
        assert unchanged == ["RUT:12345678-5", "FAM:FAM-9"]

        monkeypatch.setenv("ENTITLEMENT_HMAC_KEY", "s2-c-independent-key-" + "x" * 40)
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

        hashed = connection.execute(
            text("SELECT unit_key FROM voting_entitlements ORDER BY id")
        ).scalars().all()
        assert all(value.startswith("h1:") for value in hashed)
        assert all("12345678" not in value and "FAM-9" not in value for value in hashed)

        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="respaldo protegido"):
                migration.downgrade()

        after_failed_downgrade = connection.execute(
            text("SELECT unit_key FROM voting_entitlements ORDER BY id")
        ).scalars().all()
        assert after_failed_downgrade == hashed
