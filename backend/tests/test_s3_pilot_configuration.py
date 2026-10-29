from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import hashlib
import json
import pytest
from fastapi import HTTPException
from app.config import settings
from app.belenios.deployment import enabled,https_destination,alias_domain,confirm_manifest,COMMIT
from app.belenios.client import BeleniosClient

@pytest.fixture
def pilot(monkeypatch):
    monkeypatch.setattr(settings,'ENVIRONMENT','production')
    monkeypatch.setattr(settings,'BELENIOS_MODE','pilot')
    monkeypatch.setattr(settings,'BELENIOS_APPROVED_SCHOOLS','3')
    monkeypatch.setattr(settings,'BELENIOS_PILOT_APPROVAL','synthetic-g3-ref')
    monkeypatch.setattr(settings,'BELENIOS_ALLOWED_HOSTS','urna.example.test,verifier.internal')

def test_pilot_requires_both_approval_and_school_scope(pilot,monkeypatch):
    assert enabled(SimpleNamespace(school_id=3))
    assert not enabled(SimpleNamespace(school_id=4))
    monkeypatch.setattr(settings,'BELENIOS_PILOT_APPROVAL','')
    assert not enabled()

@pytest.mark.parametrize('url',['http://urna.example.test','https://attacker.test','https://urna.example.test@attacker.test',
                               'https://urna.example.test:8443','https://urna.example.test/?secret=1','https://urna.example.test/%2e%2e'])
def test_pilot_rejects_untrusted_destinations_without_network(pilot,url):
    with pytest.raises(HTTPException):
        https_destination(url)

def test_pilot_does_not_accept_laboratory_aliases(pilot,monkeypatch):
    monkeypatch.setattr(settings,'BELENIOS_ALIAS_DOMAIN','ejemplo.test')
    with pytest.raises(HTTPException):
        alias_domain()
    monkeypatch.setattr(settings,'BELENIOS_ALIAS_DOMAIN','votantes.osvaldovega.cl')
    assert alias_domain()=='votantes.osvaldovega.cl'

def test_runtime_evidence_requires_digest_policy_and_freshness(pilot,monkeypatch,tmp_path):
    now=datetime.now(timezone.utc)
    manifest={'observed_at':now.isoformat(),'valid_until':(now+timedelta(hours=1)).isoformat(),
              'approval_ref':'synthetic-g3-ref','profiles':{'R2':{'base_url':'https://urna.example.test',
                    'upstream_commit':COMMIT,'deny_revote':True,'image_digest':'sha256:'+'a'*64}}}
    path=tmp_path/'runtime.json'
    def write():
        path.write_text(json.dumps(manifest),encoding='utf-8')
        monkeypatch.setattr(settings,'BELENIOS_RUNTIME_MANIFEST',str(path))
        monkeypatch.setattr(settings,'BELENIOS_RUNTIME_MANIFEST_SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
    write();confirm_manifest('R2','https://urna.example.test')
    path.write_text('{}')
    with pytest.raises(HTTPException):confirm_manifest('R2','https://urna.example.test')
    manifest['profiles']['R2']['deny_revote']=False
    write()
    with pytest.raises(HTTPException):confirm_manifest('R2','https://urna.example.test')
    manifest['profiles']['R2']['deny_revote']=True
    manifest['valid_until']=(now-timedelta(seconds=1)).isoformat()
    write()
    with pytest.raises(HTTPException):confirm_manifest('R2','https://urna.example.test')
