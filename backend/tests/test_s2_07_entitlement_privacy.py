"""S2-07: loss of a key must never create a second voting entitlement."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.entitlements import derive_entitlement_key
from app.auth import hash_voting_token
from app.models import Candidate, Election, School, Vote, Voter, VotingEntitlement
from main import app


@pytest.fixture
def election_client(monkeypatch):
    monkeypatch.setattr(settings, "ENTITLEMENT_HMAC_KEY", "s2-07-persistent-test-key-" + "a" * 40)
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        school = School(nombre="S2-07 Synthetic", rbd="S2-07")
        db.add(school)
        db.flush()
        election = Election(nombre="Synthetic", school_id=school.id, estado="Abierta",
                            regla_votacion="Un voto por familia",
                            fecha_inicio=datetime.now(timezone.utc) - timedelta(days=1))
        db.add(election)
        db.flush()
        candidate = Candidate(nombre="Synthetic option", election_id=election.id)
        voter = Voter(nombre="Synthetic voter", rut="12.345.678-5", rut_normalizado="123456785",
                      familia_id=" FAMILY-1 ", election_id=election.id, estado="Pendiente",
                      token_hash=hash_voting_token("s2-07-synthetic-voting-token"))
        db.add_all([candidate, voter])
        db.add(VotingEntitlement(election_id=election.id,
                                unit_key=derive_entitlement_key(election.id, "FAM:FAMILY-1"),
                                estado="Pendiente"))
        db.commit()
        candidate_id = candidate.id

    def override_db():
        with sessions() as db:
            yield db

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, sessions, candidate_id
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    engine.dispose()


@pytest.mark.parametrize("endpoint", ["validate-token", "submit"])
def test_wrong_key_blocks_without_creating_another_entitlement(election_client, monkeypatch, endpoint):
    client, sessions, candidate_id = election_client
    monkeypatch.setattr(settings, "ENTITLEMENT_HMAC_KEY", "s2-07-different-test-key-" + "b" * 40)
    payload = {"token": "s2-07-synthetic-voting-token"}
    if endpoint == "submit":
        payload["candidate_id"] = candidate_id
    response = client.post(f"/api/voting/{endpoint}", json=payload)
    assert response.status_code == 503
    with sessions() as db:
        assert db.query(VotingEntitlement).count() == 1
        assert db.query(Vote).count() == 0
        assert db.query(Voter).one().estado == "Pendiente"


def test_restoring_key_restores_existing_right_without_rewriting_it(election_client, monkeypatch):
    client, sessions, candidate_id = election_client
    original = settings.ENTITLEMENT_HMAC_KEY
    with sessions() as db:
        right_id = db.query(VotingEntitlement).one().id
    monkeypatch.setattr(settings, "ENTITLEMENT_HMAC_KEY", "s2-07-different-test-key-" + "b" * 40)
    assert client.post("/api/voting/submit", json={"token": "s2-07-synthetic-voting-token",
                                                 "candidate_id": candidate_id}).status_code == 503
    monkeypatch.setattr(settings, "ENTITLEMENT_HMAC_KEY", original)
    response = client.post("/api/voting/submit", json={"token": "s2-07-synthetic-voting-token",
                                                    "candidate_id": candidate_id})
    assert response.status_code == 200
    with sessions() as db:
        right = db.query(VotingEntitlement).one()
        assert right.id == right_id
        assert right.estado == "Consumido"
        assert db.query(Vote).count() == 1


def test_missing_key_never_derives_a_usable_identifier(monkeypatch):
    monkeypatch.setattr(settings, "ENTITLEMENT_HMAC_KEY", "")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        derive_entitlement_key(1, "FAM:SYNTHETIC")
    assert error.value.status_code == 503


def test_unit_normalization_matches_opening_and_legacy_migration(monkeypatch):
    monkeypatch.setattr(settings, "ENTITLEMENT_HMAC_KEY", "s2-07-persistent-test-key-" + "a" * 40)
    assert derive_entitlement_key(41, "FAM: family-1 ") == derive_entitlement_key(41, "FAM:FAMILY-1")
    assert derive_entitlement_key(41, "RUT:12.345.678-5") == derive_entitlement_key(41, "RUT:123456785")
    assert derive_entitlement_key(41, "FAM:FAMILY-1") != derive_entitlement_key(42, "FAM:FAMILY-1")


def test_migration_rejects_malformed_hmac_before_touching_any_row(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "alembic/versions/b2c3d4e5f6a7_hmac_voting_entitlements.py"
    spec = importlib.util.spec_from_file_location("s207_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setenv("ENTITLEMENT_HMAC_KEY", "s2-07-persistent-test-key-" + "a" * 40)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE voting_entitlements "
                                "(id INTEGER PRIMARY KEY, election_id INTEGER, unit_key TEXT)"))
        connection.execute(text("INSERT INTO voting_entitlements VALUES "
                                "(1,41,'FAM:FAMILY-1'),(2,41,'h1:RUT:123456785')"))
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="identificador"):
                migration.upgrade()
        assert connection.execute(text("SELECT unit_key FROM voting_entitlements WHERE id=1")).scalar_one() == "FAM:FAMILY-1"
