import os

import pytest
from sqlalchemy import create_engine, text


database_url = os.getenv("S2_MIGRATION_DATABASE_URL", "")
if not database_url.startswith(("postgresql://", "postgresql+")):
    if os.getenv("REQUIRE_S2_SERVICES") == "1":
        raise RuntimeError("S2_MIGRATION_DATABASE_URL es obligatoria en integración.")
    pytest.skip("S2_MIGRATION_DATABASE_URL requiere PostgreSQL", allow_module_level=True)

engine = create_engine(database_url)


def test_postgres_migration_backfills_only_reconstructable_denominators():
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, total_padron_congelado, total_habilitados_congelado "
                "FROM elections ORDER BY id"
            )
        ).all()

    assert rows == [(1, 5, 2), (2, 2, None), (3, 1, 1)]


def test_postgres_migration_replaces_legacy_entitlement_identifiers():
    with engine.connect() as connection:
        unit_key = connection.execute(
            text("SELECT unit_key FROM voting_entitlements WHERE election_id = 3")
        ).scalar_one()

    assert unit_key.startswith("h1:")
    assert "LEGACY" not in unit_key
    assert "FAM:" not in unit_key
