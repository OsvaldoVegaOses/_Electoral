"""ADR-001 contract tests: real API/auth/DB; provider double never receives personal data."""
import hashlib
import io
import json
import tarfile
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.auth import get_current_user, ROLE_SUPERADMIN, ROLE_COMISION
from app.config import settings
from app.database import Base, get_db
from app.models import BeleniosBinding, BeleniosOperation, BeleniosUnit, Candidate, Election, School, User, Vote, Voter
from app.belenios.client import BeleniosClient, ProviderError
from app.belenios import service
from app.belenios.verification import verify_result
from app.routers.belenios import PrepareInput, VerifyInput


class Provider:
    def __init__(self):
        self.draft = None
        self.roster = None
        self.posts = 0
        self.lost = False
        self.state = "Closed"

    def check(self):
        pass

    def call(self, method, route, payload=None, match=False, raw=False):
        if route == "account":
            return {"id": 42}
        if method == "POST" and route == "elections":
            self.posts += 1
            self.draft = payload
            if self.lost:
                raise ProviderError("Simulated lost response")
            assert match
            return "Abc123Def456Gh"
        if route.endswith("/draft/voters"):
            if method == "PUT":
                assert match
                self.roster = payload
                return None
            return self.roster
        if route.endswith("/draft") and method == "GET":
            return self.draft
        if method == "POST":
            assert match
            self.state = service.TRANSITIONS[payload][1]
            return None
        return {"state": self.state}


@pytest.fixture
def lab(monkeypatch):
    monkeypatch.setattr(settings, "BELENIOS_MODE", "laboratory")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    db = Session()
    school = School(nombre="Institucion sintetica")
    other = School(nombre="Otra institucion sintetica")
    db.add_all([school, other]); db.flush()
    election = Election(nombre="Ensayo ADR", school_id=school.id, regla_votacion="Un voto por familia", estado="Borrador")
    user = User(nombre="Operador ficticio", email="operador@ejemplo.test", password_hash="not-used", rol=ROLE_SUPERADMIN)
    db.add_all([election, user]); db.flush()
    voters = [Voter(election_id=election.id, rut=f"SYNTHETIC-{i}", rut_normalizado=f"SYNTHETIC-{i}", nombre=f"Persona {i}",
                    correo=f"rep{i}@ejemplo.test", familia_id="family-1" if i < 2 else "family-2", token_votacion=f"synthetic-token-{i}") for i in range(3)]
    db.add_all(voters)
    db.add_all([Candidate(election_id=election.id, nombre=n, es_blanco=False, es_nulo=False) for n in ("Lista A", "Lista B")])
    db.commit()
    provider = Provider()
    monkeypatch.setattr(service, "BeleniosClient", lambda policy: provider)
    # Default arguments are bound at definition; patch the exported API wrapper's service call below.
    original_prepare = service.prepare
    monkeypatch.setattr(service, "prepare", lambda d,e,u,b: original_prepare(d,e,u,b,lambda policy: provider))
    original_transition = service.transition
    monkeypatch.setattr(service, "transition", lambda d,e,b,u,p: original_transition(d,e,b,u,p,lambda policy: provider))
    original_reconcile = service.reconcile
    monkeypatch.setattr(service, "reconcile", lambda d,b,uuid,key: original_reconcile(d,b,uuid,key,lambda policy: provider))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app, raise_server_exceptions=True)
    try:
        body = {"request_id": str(uuid4()), "policy": "R2", "representative_ids": [voters[0].id, voters[2].id],
                "approval_ref": "poc-review-1", "ballot_mode": "mandatory_single_choice_no_blank_no_null", "synthetic_laboratory": True}
        yield SimpleNamespace(db=db, Session=Session, client=client, user=user, election=election, voters=voters, provider=provider,
                              body=body, base=f"/api/elections/{election.id}/belenios", other=other)
    finally:
        client.close()
    app.dependency_overrides.clear()
    db.close(); engine.dispose()


def test_off_and_production_fail_closed(lab, monkeypatch):
    for mode, environment in (("off", "development"), ("laboratory", "production")):
        monkeypatch.setattr(settings, "BELENIOS_MODE", mode)
        monkeypatch.setattr(settings, "ENVIRONMENT", environment)
        assert lab.client.post(lab.base + "/prepare", json=lab.body).status_code == 503
    assert lab.provider.posts == 0 and lab.db.query(BeleniosBinding).count() == 0


def test_policy_and_ballot_semantics_are_explicit(lab):
    for key in ("policy", "ballot_mode", "synthetic_laboratory"):
        payload = dict(lab.body); payload.pop(key)
        assert lab.client.post(lab.base + "/prepare", json=payload).status_code == 422
    payload = dict(lab.body, private_credential="must-never-be-accepted")
    assert lab.client.post(lab.base + "/prepare", json=payload).status_code == 422
    assert lab.provider.posts == 0


def test_one_explicit_representative_per_unit(lab):
    for selection in ([v.id for v in lab.voters], [lab.voters[0].id], [lab.voters[0].id, 999999]):
        assert lab.client.post(lab.base + "/prepare", json=dict(lab.body, representative_ids=selection)).status_code == 422
    assert lab.provider.posts == 0


def test_scope_no_cross_institution_or_unassigned_commission(lab):
    for school_id, election_id in ((lab.other.id, lab.election.id), (lab.election.school_id, None)):
        intruder = User(id=999, nombre="Ficticio", email="test@ejemplo.test", password_hash="x", rol=ROLE_COMISION, school_id=school_id, election_id=election_id)
        app.dependency_overrides[get_current_user] = lambda: intruder
        for suffix, method in (("", "get"), ("/units", "get"), ("/prepare", "post")):
            response = getattr(lab.client, method)(lab.base + suffix, **({"json": lab.body} if method == "post" else {}))
            assert response.status_code == 403
    assert lab.provider.posts == 0


def prepare(lab):
    response = lab.client.post(lab.base + "/prepare", json=lab.body)
    assert response.status_code == 201, response.text
    return response.json()


def test_provider_gets_aliases_not_people_or_mvp_tokens(lab):
    result = prepare(lab)
    assert result["total_people"] == 3 and result["total_units"] == 2
    assert len(lab.provider.roster) == len(set(lab.provider.roster)) == 2
    sent = json.dumps([lab.provider.draft, lab.provider.roster])
    assert "SYNTHETIC" not in sent and "family-" not in sent and "rep0@" not in sent and "synthetic-token" not in sent
    assert lab.client.post(lab.base + "/prepare", json=lab.body).status_code == 409
    assert lab.provider.posts == 1
    private = lab.client.get(lab.base + '/units')
    assert private.status_code == 200 and private.headers['cache-control'] == 'no-store'
    assert len(private.json()['units']) == 2


def test_bound_election_cannot_fall_back_to_mvp_or_mutate_roster(lab):
    prepare(lab)
    prefix = f"/api/elections/{lab.election.id}"
    assert lab.client.post(prefix + "/abrir").status_code == 409
    assert lab.client.put(prefix, json={"nombre": "Changed"}).status_code == 409
    assert lab.client.post(prefix + "/candidates", json={"nombre": "C", "election_id": lab.election.id}).status_code == 409
    for path in ("/api/voting/validate-token", "/api/voting/submit"):
        response = lab.client.post(path, json={"token": lab.voters[0].token_votacion, **({"candidate_id": 1} if path.endswith("submit") else {})})
        assert response.status_code == 409
    assert lab.client.get(f"/api/reports/election/{lab.election.id}/scrutiny").status_code == 409
    assert lab.client.get("/api/reports/dashboard-stats").status_code == 409
    assert lab.db.query(Vote).count() == 0


def test_lost_creation_is_durable_and_never_repeated(lab):
    lab.provider.lost = True
    assert lab.client.post(lab.base + "/prepare", json=lab.body).status_code == 503
    lab.db.expire_all()
    binding = lab.db.query(BeleniosBinding).one()
    assert binding.phase == "UNKNOWN" and binding.inflight == lab.body["request_id"] and binding.remote_uuid is None
    with lab.Session() as reopened:
        assert reopened.get(BeleniosOperation, lab.body["request_id"]).phase == "UNKNOWN"
    assert lab.client.post(lab.base + "/prepare", json=dict(lab.body, request_id=str(uuid4()))).status_code == 409
    assert lab.provider.posts == 1
    assert lab.client.post(lab.base + "/reconcile", json={"operation_id": lab.body['request_id'], "candidate_uuid": "Abc123Def456Gh", "manually_reviewed": True}).status_code == 409
    binding = lab.db.query(BeleniosBinding).one()
    lab.provider.roster = [unit.alias for unit in service.units(lab.db, binding)]  # Explicit external human repair simulated.
    r = lab.client.post(lab.base + "/reconcile", json={"operation_id": lab.body['request_id'], "candidate_uuid": "Abc123Def456Gh", "manually_reviewed": True})
    assert r.status_code == 200 and r.json()['phase'] == 'Draft' and lab.provider.posts == 1


def test_ceremony_missing_and_unverified_results_are_blocked(lab):
    prepare(lab)
    # Deliberately incomplete ceremony response from provider.
    lab.provider.call_original = lab.provider.call
    def call(method, route, *args, **kw):
        if route.endswith('/draft/status'):
            return {'credentials_ready': False, 'trustees_ready': False}
        if route.endswith('/draft/trustees'):
            return ['Threshold', {'threshold': 2, 'trustees': []}]
        return lab.provider.call_original(method, route, *args, **kw)
    lab.provider.call = call
    assert lab.client.post(lab.base + '/transition', json={'request_id': str(uuid4()), 'action': 'ValidateElection'}).status_code == 409
    assert lab.client.get(lab.base + '/record').status_code == 409


def test_late_completion_or_error_cannot_overwrite_reconciled_state(lab):
    prepare(lab)
    binding = lab.db.query(BeleniosBinding).one()
    first = service.reserve(lab.db, binding, lab.user, str(uuid4()), 'Open')
    service.complete(lab.db, binding, first, 'Open')
    second = service.reserve(lab.db, binding, lab.user, str(uuid4()), 'Close')
    service.complete(lab.db, binding, second, 'Closed')
    for finish in (lambda: service.complete(lab.db, binding, first, 'Open'), lambda: service.unknown(lab.db, binding, first)):
        with pytest.raises(HTTPException) as stopped:
            finish()
        assert stopped.value.status_code == 409
        lab.db.refresh(binding)
        assert binding.phase == 'Closed' and binding.inflight is None
        assert lab.db.get(Election, binding.election_id).estado == 'Cerrada'


def test_actual_threshold_variant_and_forward_lifecycle(lab):
    prepare(lab)
    original=lab.provider.call
    def call(method,route,*args,**kw):
        if route.endswith('/draft/status'): return {'credentials_ready':True,'trustees_ready':True,'num_voters':2}
        if route.endswith('/draft/trustees'): return ['Threshold',{'threshold':2,'trustees':[{}, {}, {}]}]
        return original(method,route,*args,**kw)
    lab.provider.call=call
    def transition(action): return lab.client.post(lab.base+'/transition',json={'request_id':str(uuid4()),'action':action})
    assert transition('ValidateElection').status_code==200
    assert transition('ComputeEncryptedTally').status_code==409
    for action in ('Open','Close'):
        assert transition(action).status_code==200
    assert transition('Open').status_code==409
    for action in ('ComputeEncryptedTally','ReleaseTally'):
        assert transition(action).status_code==200
    assert lab.db.get(Election,lab.election.id).fecha_cierre_efectiva is not None


def test_client_rejects_external_destination_without_network(monkeypatch):
    monkeypatch.setattr(settings, 'BELENIOS_MODE', 'laboratory')
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'development')
    monkeypatch.setattr(settings, 'BELENIOS_R2_URL', 'https://vote.belenios.org')
    with pytest.raises(HTTPException):
        BeleniosClient('R2')


def verification_fixture(lab):
    prepare(lab)
    binding = lab.db.query(BeleniosBinding).one(); binding.phase = 'Tallied'; lab.db.commit()
    raw = b'{"result":[["1","1"]]}'
    digest = hashlib.sha256(raw).hexdigest()
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w') as tar:
        info = tarfile.TarInfo(digest + '.data'); info.size = len(raw); tar.addfile(info, io.BytesIO(raw))
    data = archive.getvalue()
    body = VerifyInput(final_event_hash='a'*64, result_object_hash=digest, archive_sha256=hashlib.sha256(data).hexdigest(), anchor_reference='poc-reviewed')
    expected = json.loads(binding.draft_json)['questions']
    class Reader:
        def check(self): pass
        def call(self, method, route, raw=False):
            if route.endswith('/last-event'): return {'hash': 'a'*64}
            if route.endswith('/roots'): return {'result': digest}
            if '/objects/' in route: return b'{"result":[["1","1"]]}'
            if route.endswith('/election'): return {'name': expected['name'], 'description': expected['description'], 'questions': expected['questions']}
            if route.endswith('/ballots'): return {'b'*64: '1', 'c'*64: '1'}
            return {'state': 'Tallied'}
    return binding, body, Reader(), data


def test_verified_result_persists_only_aggregate_evidence(lab):
    binding, body, reader, archive = verification_fixture(lab)
    result = verify_result(lab.db, binding, body, reader, lambda *_: archive)
    assert [row['votes'] for row in result['options']] == [1, 1]
    assert result['enabled_units'] == 2 and result['total_people'] == 3 and result['participation'] == 1.0
    assert result['blank'] is None and result['null'] is None and not result['independent_custody_confirmed']
    assert lab.client.get(lab.base + '/record').json() == result


@pytest.mark.parametrize('fault', ['anchor', 'archive', 'verifier'])
def test_untrusted_results_never_persist(lab, fault):
    binding, body, reader, archive = verification_fixture(lab)
    if fault == 'anchor': body.final_event_hash = '0'*64
    if fault == 'archive': body.archive_sha256 = '0'*64
    def runner(*_):
        if fault == 'verifier': raise ProviderError('Verifier failed')
        return archive
    with pytest.raises((HTTPException, ProviderError)):
        verify_result(lab.db, binding, body, reader, runner)
    assert binding.verified_result is None
