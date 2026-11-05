"""Security boundaries of provisional access; synthetic data, no email or live service."""
import csv
import hashlib
from pathlib import Path
import sys
import threading
import time

import httpx
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from services.pilot_access import (AccessDenied,COOKIE,Portal,native_password_update,password_hash,
                                   password_matches,server)

ORIGIN='https://pilot.example.invalid'
TEMP='Synthetic-Initial-2026'
NEW='Synthetic-Replacement-2026'


@pytest.fixture
def portal(tmp_path):
    return Portal(tmp_path/'state',ORIGIN,sync=lambda *args:None)


def account(portal,role='trustee',email='member@example.invalid'):
    route={'trustee':'trustee','administrator':'admin','credential_authority':'credauth'}[role]
    portal.provision(email,'Synthetic member',role,TEMP,ORIGIN+'/'+route+'#synthetic-role-reference')
    return email


def test_new_secret_revokes_provisional_and_all_old_sessions(portal):
    email=account(portal)
    first,pending=portal.login(email,TEMP,'synthetic-ip');assert pending
    second,_=portal.login(email,TEMP,'synthetic-ip')
    fresh=portal.change(first,portal.csrf(first),NEW,NEW)
    assert portal.user(fresh)['must_change']==0
    for token in (first,second):
        with pytest.raises(AccessDenied):portal.user(token)
    with pytest.raises(AccessDenied):portal.login(email,TEMP,'synthetic-ip')
    _,pending=portal.login(email,NEW,'synthetic-ip');assert not pending
    assert TEMP.encode() not in portal.database.read_bytes() and NEW.encode() not in portal.database.read_bytes()


@pytest.mark.parametrize('password,confirmation',[(TEMP,TEMP),('short','short'),
    ('lowercase-only-2026','lowercase-only-2026'),(NEW,'different'),(' '+NEW,' '+NEW)])
def test_initial_change_rejects_same_weak_or_mismatched_secret(portal,password,confirmation):
    email=account(portal);token,_=portal.login(email,TEMP,'ip')
    with pytest.raises(AccessDenied):portal.change(token,portal.csrf(token),password,confirmation)
    assert portal.user(token)['must_change']==1


def test_csrf_cannot_be_omitted_or_borrowed_from_another_session(portal):
    email=account(portal);token,_=portal.login(email,TEMP,'ip');other,_=portal.login(email,TEMP,'ip')
    for csrf in ('',portal.csrf(other)):
        with pytest.raises(AccessDenied):portal.change(token,csrf,NEW,NEW)
    assert portal.user(token)['must_change']==1


def test_admin_native_sync_failure_does_not_clear_restriction(portal):
    email=account(portal,'administrator');token,_=portal.login(email,TEMP,'ip')
    def unavailable(*args):raise OSError('synthetic unavailable')
    portal.sync=unavailable
    with pytest.raises(OSError):portal.change(token,portal.csrf(token),NEW,NEW)
    assert portal.user(token)['must_change']==1


def test_only_admin_password_change_updates_native_passwords(portal):
    calls=[];portal.sync=lambda *args:calls.append(args)
    trustee=account(portal);token,_=portal.login(trustee,TEMP,'ip')
    portal.change(token,portal.csrf(token),NEW,NEW);assert calls==[]
    admin=account(portal,'administrator','admin@example.invalid');token,_=portal.login(admin,TEMP,'ip')
    portal.change(token,portal.csrf(token),NEW,NEW);assert calls==[(admin,NEW)]


def test_subsequent_change_requires_current_secret(portal):
    email=account(portal);token,_=portal.login(email,TEMP,'ip')
    active=portal.change(token,portal.csrf(token),NEW,NEW)
    next_password='Synthetic-Next-Secret-2026'
    with pytest.raises(AccessDenied):portal.change(active,portal.csrf(active),next_password,next_password)
    portal.change(active,portal.csrf(active),next_password,next_password,NEW)


def test_expired_temporary_account_and_session_fail_closed(portal):
    email=account(portal);token,_=portal.login(email,TEMP,'ip')
    with portal.connection() as db:db.execute('UPDATE users SET expires=?',(time.time()-1,))
    with pytest.raises(AccessDenied):portal.user(token)
    with pytest.raises(AccessDenied):portal.login(email,TEMP,'ip')


def test_repeated_wrong_login_is_limited(portal):
    email=account(portal)
    for _ in range(5):
        with pytest.raises(AccessDenied,match='invalid_login'):portal.login(email,'wrong','ip')
    with pytest.raises(AccessDenied,match='temporarily_limited'):portal.login(email,TEMP,'ip')


@pytest.mark.parametrize('role,target',[('trustee','/admin'),('administrator','/trustee'),('unknown','/admin'),
                                      ('trustee','https://outside.example.invalid/trustee')])
def test_provisioning_cannot_cross_role_or_host_boundaries(portal,role,target):
    target=target if target.startswith('https:') else ORIGIN+target
    with pytest.raises(ValueError):portal.provision('member@example.invalid','Synthetic',role,TEMP,target)


def test_native_password_update_matches_upstream_pbkdf2_and_preserves_other_account(tmp_path):
    path=tmp_path/'native.csv';path.write_text('admin@example.invalid,unused,blocked,admin@example.invalid\nother,keep,unchanged,other@example.invalid\n')
    native_password_update(path,'admin@example.invalid',NEW)
    rows=list(csv.reader(path.open()))
    assert password_matches(NEW,rows[0][1],rows[0][2])
    rounds,digest=rows[0][2].split('$')
    assert int(rounds)==600_000 and len(rows[0][1])>=16
    assert hashlib.pbkdf2_hmac('sha256',NEW.encode(),rows[0][1].encode(),600_000,32).hex()==digest
    assert rows[1]==['other','keep','unchanged','other@example.invalid']
    assert NEW not in path.read_text()
    before=path.read_bytes()
    with pytest.raises(AccessDenied):native_password_update(path,'unregistered@example.invalid',NEW)
    assert path.read_bytes()==before


@pytest.fixture
def live(portal):
    account(portal)
    http=server(('127.0.0.1',0),portal);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    with httpx.Client(base_url=f'http://127.0.0.1:{http.server_port}',follow_redirects=False) as client:
        yield portal,client
    http.shutdown();http.server_close();thread.join(timeout=2)


def test_http_requires_origin_secure_session_and_change_before_role_link(live):
    portal,client=live
    denied=client.post('/acceso/entrar',data={'email':'member@example.invalid','password':TEMP})
    assert denied.status_code==403
    login=client.post('/acceso/entrar',headers={'Origin':ORIGIN},data={'email':'member@example.invalid','password':TEMP})
    assert login.status_code==303 and login.headers['location']=='/acceso/cambiar-clave'
    assert all(value in login.headers['set-cookie'] for value in ('Secure','HttpOnly','SameSite=Strict','Path=/'))
    token=login.cookies[COOKIE]
    pending=client.get('/acceso/panel',headers={'Cookie':COOKIE+'='+token})
    assert 'synthetic-role-reference' not in pending.text and 'contraseña nueva' in pending.text
    assert pending.headers['cache-control']=='no-store' and "frame-ancestors 'none'" in pending.headers['content-security-policy']
    assert pending.headers['referrer-policy']=='same-origin'
    assert 'Votación Centro de Padres IAC' in pending.text and 'Belenios' not in pending.text
    changed=client.post('/acceso/cambiar-clave',headers={'Origin':ORIGIN,'Cookie':COOKIE+'='+token},
                        data={'csrf':portal.csrf(token),'password':NEW,'confirmation':NEW})
    assert changed.status_code==303
    active=client.get('/acceso/panel',headers={'Cookie':COOKIE+'='+changed.cookies[COOKIE]})
    assert 'synthetic-role-reference' in active.text and 'Custodia' in active.text
    assert 'Administración' not in active.text
    assert client.get('/acceso/panel?email=other@example.invalid').status_code==404


def test_logout_revokes_only_its_session(live):
    portal,client=live;email='member@example.invalid'
    token,_=portal.login(email,TEMP,'ip');other,_=portal.login(email,TEMP,'ip')
    response=client.post('/acceso/salir',headers={'Origin':ORIGIN,'Cookie':COOKIE+'='+token},data={'csrf':portal.csrf(token)})
    assert response.status_code==303 and 'Max-Age=0' in response.headers['set-cookie']
    with pytest.raises(AccessDenied):portal.user(token)
    assert portal.user(other)['must_change']==1
