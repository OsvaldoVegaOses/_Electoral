"""Native SSO and roster finalization cannot bypass first-access or role boundaries."""
import json
from pathlib import Path
import sys
import threading
import time
import io
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from services.pilot_access import AccessDenied,COOKIE,NativeBridge,NativeUnavailable,Portal,server

ORIGIN='https://pilot.example.invalid'
TEMP='Synthetic-Initial-2026'
NEW='Synthetic-Replacement-2026'


@pytest.fixture
def bridge(tmp_path):
    path=tmp_path/'native.json'
    path.write_text(json.dumps({'admin@example.invalid':{'account_id':7,'service_password':'synthetic-service-secret',
        'token':'synthetic-native-token','expiration':time.time()+3600,'uuid':'CvnVFmybmHMb19',
        'required_recipients':['admin@example.invalid']}}))
    mail=tmp_path/'mail.json';mail.write_text(json.dumps({'allowed_recipients':['admin@example.invalid'],
        'aliases':{'unit@example.invalid':'voter@example.invalid'},'credential_authority_channel':False}))
    def transport(method,route,**kwargs):
        if route=='account':return 200,{'id':7}
        if route.endswith('/status'):return 200,{'credentials_ready':False}
        if route.endswith('/voters'):return 200,['unit@example.invalid,DEMO-01','second@example.invalid,DEMO-02']
        if route=='login':return 200,None
        return 200,{'token':'synthetic-renewed-token','expiration':time.time()+3600}
    return NativeBridge(path,transport=transport,mail_path=mail)


def test_native_bridge_uses_correct_identity_and_does_not_change_native_password(bridge):
    assert bridge.token('admin@example.invalid')=='synthetic-native-token'
    before=json.loads(bridge.path.read_text())['admin@example.invalid']['service_password']
    bridge.revoke('admin@example.invalid')
    assert bridge.token('admin@example.invalid')=='synthetic-renewed-token'
    assert json.loads(bridge.path.read_text())['admin@example.invalid']['service_password']==before
    with pytest.raises(AccessDenied):bridge.token('trustee@example.invalid')


def test_wrong_native_identity_is_never_returned(bridge):
    bridge.transport=lambda *args,**kwargs:(200,{'id':999})
    with pytest.raises(NativeUnavailable):bridge.token('admin@example.invalid')


def test_roster_confirmation_routes_only_reviewed_recipients_and_freezes_hash(bridge):
    assert not bridge.roster_confirmed()
    assert bridge.confirm_roster('admin@example.invalid')==2
    assert bridge.roster_confirmed()
    mail=json.loads(bridge.mail_path.read_text())
    assert set(mail['allowed_recipients'])=={'admin@example.invalid','voter@example.invalid','second@example.invalid'}
    assert mail['credential_authority_channel'] is False
    assert bridge.confirm_roster('admin@example.invalid')==2
    original=bridge.transport
    def changed(method,route,**kwargs):
        if route.endswith('/voters'):return 200,['third@example.invalid','fourth@example.invalid']
        return original(method,route,**kwargs)
    bridge.transport=changed
    assert not bridge.roster_confirmed()
    with pytest.raises(AccessDenied,match='reconciliation'):bridge.confirm_roster('admin@example.invalid')


@pytest.mark.parametrize('voters,status',[
    ([],{'credentials_ready':False}),
    (['unit@example.invalid','voter@example.invalid'],{'credentials_ready':False}),
    (['a@example.invalid,,2','b@example.invalid'],{'credentials_ready':False}),
    (['a@example.invalid','b@example.invalid'],{'credentials_ready':True}),
    (['a@example.invalid','b@example.invalid'],{'credentials_ready':False,'credentials_left':1}),
])
def test_bad_or_started_roster_does_not_enable_credential_authority(bridge,voters,status):
    original=bridge.transport
    def response(method,route,**kwargs):
        if route.endswith('/voters'):return 200,voters
        if route.endswith('/status'):return 200,status
        return original(method,route,**kwargs)
    bridge.transport=response
    before=bridge.mail_path.read_bytes()
    with pytest.raises(AccessDenied):bridge.confirm_roster('admin@example.invalid')
    assert bridge.mail_path.read_bytes()==before and not bridge.roster_confirmed()


def test_http_native_token_is_withheld_until_change_and_for_all_non_admins(tmp_path,bridge):
    portal=Portal(tmp_path/'state',ORIGIN,sync=lambda email,password:bridge.revoke(email))
    portal.provision('admin@example.invalid','Synthetic Admin','administrator',TEMP,ORIGIN+'/admin#elections/CvnVFmybmHMb19')
    portal.provision('trustee@example.invalid','Synthetic Trustee','trustee',TEMP,ORIGIN+'/trustee#generate/synthetic')
    portal.provision('authority@example.invalid','Synthetic Authority','credential_authority',TEMP,ORIGIN+'/credauth#generate/synthetic')
    http=server(('127.0.0.1',0),portal,bridge)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{http.server_port}',follow_redirects=False) as client:
            token,_=portal.login('admin@example.invalid',TEMP,'ip')
            assert client.get('/api-token',headers={'Cookie':COOKIE+'='+token}).status_code==403
            active=portal.change(token,portal.csrf(token),NEW,NEW)
            headers={'Cookie':COOKIE+'='+active}
            response=client.get('/api-token',headers=headers)
            assert response.status_code==200 and response.text=='synthetic-renewed-token'
            assert response.headers['content-type'].startswith('text/plain')
            authority,_=portal.login('authority@example.invalid',TEMP,'ip')
            authority=portal.change(authority,portal.csrf(authority),NEW,NEW)
            page=client.get('/acceso/panel',headers={'Cookie':COOKIE+'='+authority})
            assert 'padrón definitivo está pendiente' in page.text and '#generate/synthetic' not in page.text
            assert client.get('/api-token',headers={'Cookie':COOKIE+'='+authority}).status_code==403
            bridge.confirm_roster('admin@example.invalid')
            page=client.get('/acceso/panel',headers={'Cookie':COOKIE+'='+authority})
            assert '#generate/synthetic' in page.text
            rejected=client.delete('/api/login',headers={**headers,'Origin':ORIGIN,'Authorization':'Bearer incorrect'})
            assert rejected.status_code==403
            logout=client.delete('/api/login',headers={**headers,'Origin':ORIGIN,'Authorization':'Bearer synthetic-renewed-token'})
            assert logout.status_code==200 and logout.json() is None
            assert client.get('/api-token',headers=headers).status_code==403
    finally:http.shutdown();http.server_close();thread.join(timeout=2)


@pytest.mark.parametrize('count', [1000, 1001])
def test_native_roster_capacity_is_bounded_and_preserves_unit_weight(bridge,count):
    original=bridge.transport
    def transport(method,route,**kwargs):
        if route.endswith('/voters'):return 200,[f'unit-{index}@example.invalid,F-{index},1' for index in range(count)]
        return original(method,route,**kwargs)
    bridge.transport=transport
    before=bridge.mail_path.read_bytes()
    if count==1001:
        with pytest.raises(AccessDenied,match='invalid_roster'):bridge.confirm_roster('admin@example.invalid')
        assert bridge.mail_path.read_bytes()==before
    else:
        assert bridge.confirm_roster('admin@example.invalid')==1000
        assert len(json.loads(bridge.mail_path.read_text())['allowed_recipients'])==1001


def test_native_transport_reads_a_large_roster_without_truncation(monkeypatch):
    rows=[{'address':f'unit-{index}@example.invalid','name':'Synthetic '+('x'*90)} for index in range(1000)]
    raw=json.dumps(rows).encode();assert len(raw)>65536
    response=io.BytesIO(raw);response.status=200
    monkeypatch.setattr('services.pilot_access.build_opener',lambda *args:SimpleNamespace(open=lambda *args,**kwargs:response))
    assert NativeBridge.request('GET','elections/Synthetic00001/draft/voters')==(200,rows)
