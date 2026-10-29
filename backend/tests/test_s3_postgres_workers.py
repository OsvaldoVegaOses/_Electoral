"""Independent processes and a non-owner PostgreSQL role on labelled disposable services."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4
import httpx
import pytest
import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url

URL=os.getenv('DATABASE_URL','')
REQUIRED=os.getenv('REQUIRE_S2_SERVICES')=='1'
if not URL.startswith('postgresql'):
    if REQUIRED:raise RuntimeError('PostgreSQL integration required')
    pytest.skip('S3 process tests require disposable PostgreSQL/Redis',allow_module_level=True)
BACKEND=Path(__file__).resolve().parents[1]

def test_two_processes_build_one_chain_with_non_owner_role():
    role='s3_audit_'+uuid4().hex[:10]
    password=uuid4().hex
    dsn=URL.replace('postgresql+psycopg2://','postgresql://',1)
    db=psycopg2.connect(dsn);db.autocommit=True
    with db.cursor() as cursor:
        cursor.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD %s').format(sql.Identifier(role)),(password,))
        cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(role)))
        cursor.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE ON audit_logs,audit_chain_heads TO {}').format(sql.Identifier(role)))
        cursor.execute(sql.SQL('GRANT DELETE ON audit_logs TO {}').format(sql.Identifier(role)))
        cursor.execute(sql.SQL('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(sql.Identifier(role)))
    limited=make_url(URL).set(username=role,password=password).render_as_string(hide_password=False)
    marker=uuid4().hex
    code='''import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.auth import log_audit
engine=create_engine(os.environ['S3_LIMITED_URL'])
for number in range(50):
    with Session(engine) as db:
        log_audit(db,accion='S3 process '+os.environ['S3_MARKER'],usuario='synthetic',detalle=str(number))
'''
    processes=[]
    try:
        env={**os.environ,'S3_LIMITED_URL':limited,'S3_MARKER':marker}
        processes=[subprocess.Popen([sys.executable,'-c',code],cwd=BACKEND,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
        for process in processes:
            stdout,stderr=process.communicate(timeout=60)
            assert process.returncode==0,stderr.decode(errors='replace')
        with db.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM audit_logs WHERE accion=%s',('S3 process '+marker,))
            assert cursor.fetchone()[0]==100
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.auth import verify_audit_log_chain
        with Session(create_engine(URL)) as session:
            assert verify_audit_log_chain(session)['integro']
        for command in ('UPDATE audit_logs SET usuario=usuario','DELETE FROM audit_logs'):
            with psycopg2.connect(limited.replace('postgresql+psycopg2://','postgresql://',1)) as limited_db:
                with limited_db.cursor() as cursor:
                    cursor.execute("SET LOCAL theogen.allow_audit_purge='on'")
                    with pytest.raises(psycopg2.Error):cursor.execute(command)
                limited_db.rollback()
    finally:
        for process in processes:
            if process.poll() is None:process.kill();process.wait()
        with db.cursor() as cursor:
            cursor.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
            cursor.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
        db.close()

def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

def test_two_http_workers_share_redis_and_fail_closed_during_outage():
    container=os.environ.get('S3_REDIS_CONTAINER','')
    if not container:raise RuntimeError('S3_REDIS_CONTAINER must identify the disposable Redis service')
    inspected=subprocess.check_output(['docker','inspect','--format','{{index .Config.Labels "theogen.task"}}',container]).decode().strip()
    assert inspected=='sprint3-local' or os.environ.get('CI')=='true'
    env={**os.environ,'ENVIRONMENT':'production','REDIS_URL':os.environ['REDIS_URL'].rsplit('/',1)[0]+'/13'}
    processes=[];clients=[];stopped=False
    try:
        import redis
        cache=redis.Redis.from_url(env['REDIS_URL'])
        cache.delete('rl:127.0.0.1')
        for _ in range(2):
            port=free_port()
            processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port',str(port)],
                cwd=BACKEND,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
            client=httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=5,trust_env=False)
            clients.append(client)
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                try:
                    if client.get('/api/health').status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.1)
            else:raise AssertionError('Synthetic worker failed readiness')
        payload={'email':'nonexistent-s3@example.org','password':'incorrect-password'}
        statuses=[clients[index % 2].post('/api/auth/login',json=payload).status_code for index in range(10)]
        assert statuses==[401]*10
        assert cache.zcard('rl:127.0.0.1')==10
        assert clients[1].post('/api/auth/login',json=payload).status_code==429
        subprocess.run(['docker','stop','--time','2',container],check=True,capture_output=True);stopped=True
        for client in clients:
            assert client.post('/api/auth/login',json=payload).status_code==503
    finally:
        if stopped:subprocess.run(['docker','start',container],check=True,capture_output=True)
        for client in clients:client.close()
        for process in processes:
            if process.poll() is None:process.terminate();process.wait(timeout=10)
