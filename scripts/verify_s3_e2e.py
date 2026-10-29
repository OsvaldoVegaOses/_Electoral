"""Run browser tests on a fresh synthetic database; never reuse an application server."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from uuid import uuid4

import psycopg2
from psycopg2 import sql

ROOT=Path(__file__).resolve().parents[1]

def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]

def run(command,env,cwd):
    subprocess.run(command,env=env,cwd=cwd,check=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--postgres-container',required=True)
    args=parser.parse_args()
    label=subprocess.check_output(['docker','inspect','--format','{{index .Config.Labels "theogen.task"}}',args.postgres_container]).decode().strip()
    if label!='sprint3-local':raise RuntimeError('Refusing a non-synthetic database')
    host,mapping=subprocess.check_output(['docker','port',args.postgres_container,'5432']).decode().strip().split(':')
    if host!='127.0.0.1':raise RuntimeError('Loopback-only service required')
    name='s3_e2e_'+uuid4().hex[:10]
    connection=psycopg2.connect(host=host,port=int(mapping),user='postgres',password='s3_synthetic_only',dbname='postgres')
    try:
        connection.autocommit=True
        with connection.cursor() as cursor:cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    finally:
        connection.close()
    api,ui=port(),port()
    env={**os.environ,'ENVIRONMENT':'test','SEED_DEMO_DATA':'false','BELENIOS_MODE':'off',
         'DATABASE_URL':f'postgresql+psycopg2://postgres:s3_synthetic_only@127.0.0.1:{mapping}/{name}',
         'SECRET_KEY':'s3_e2e_jwt_'+'a'*40,'VOTE_HMAC_KEY':'s3_e2e_vote_'+'b'*40,
         'ENTITLEMENT_HMAC_KEY':'s3_e2e_unit_'+'c'*40,'REDIS_URL':'','PYTHONUTF8':'1',
         'E2E_ADMIN_EMAIL':'s3-admin@example.org','E2E_ADMIN_PASSWORD':secrets.token_urlsafe(24),
         'S3_E2E_FIXTURES_FILE':str(ROOT/'.runtime'/'e2e-fixtures.json'),
         'S3_API_PORT':str(api),'S3_UI_PORT':str(ui),'API_PROXY_TARGET':f'http://127.0.0.1:{api}',
         'PLAYWRIGHT_BASE_URL':f'http://127.0.0.1:{ui}',
         'PATH':str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH']}
    run([sys.executable,'-m','alembic','upgrade','head'],env,ROOT/'backend')
    run([sys.executable,str(ROOT/'scripts'/'prepare_s3_e2e.py')],env,ROOT/'backend')
    npm='npm.cmd' if os.name=='nt' else 'npm'
    run([npm,'run','test:e2e'],env,ROOT/'frontend')
    report={'scope':'real HTTP and browser; synthetic PostgreSQL; Belenios disabled; no mail',
            'fresh_database':True,'server_reused':False,'automatic_retry':False}
    (ROOT/'.runtime'/'s3-e2e.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
