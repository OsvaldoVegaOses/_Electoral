"""Required integration, isolated databases and exact restoration on synthetic services only."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4
import xml.etree.ElementTree as ET
import psycopg2
from psycopg2 import sql

ROOT=Path(__file__).resolve().parents[1]
BACKEND=ROOT/'backend'

def run(args,env=None,cwd=BACKEND,input_bytes=None):
    result=subprocess.run(args,cwd=cwd,env=env,input=input_bytes,capture_output=True)
    if result.returncode:
        sys.stdout.buffer.write(result.stdout)
        sys.stderr.buffer.write(result.stderr)
        raise RuntimeError('Synthetic verification failed: '+str(args[:3]))
    return result.stdout

def labelled_port(container,internal):
    label=run(['docker','inspect','--format','{{index .Config.Labels "theogen.task"}}',container]).decode().strip()
    if label!='sprint3-local':
        raise RuntimeError('Refusing services not labelled sprint3-local')
    mapping=run(['docker','port',container,str(internal)]).decode().strip()
    host,port=mapping.split(':')
    if host!='127.0.0.1':raise RuntimeError('Loopback-only service required')
    return int(port)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--postgres-container')
    parser.add_argument('--redis-container')
    parser.add_argument('--ci',action='store_true')
    parser.add_argument('--output',default='.runtime/s3-integration.json')
    args=parser.parse_args()
    prefix='s3_'+uuid4().hex[:10]
    if args.ci:
        admin_url=os.environ['S3_ADMIN_DATABASE_URL']
        redis_url=os.environ['REDIS_URL']
    else:
        pg=labelled_port(args.postgres_container,5432)
        redis=labelled_port(args.redis_container,6379)
        admin_url=f'postgresql://postgres:s3_synthetic_only@127.0.0.1:{pg}/postgres'
        redis_url=f'redis://127.0.0.1:{redis}/0'
    names={name:prefix+'_'+name for name in ('main','concurrency','empty','populated','privacy','restored','adr','upgrade_paths')}
    connection=psycopg2.connect(admin_url);connection.autocommit=True
    with connection.cursor() as cursor:
        cursor.execute('SHOW server_version_num')
        if int(cursor.fetchone()[0])//10000!=16:raise RuntimeError('PostgreSQL16 required')
        for name in names.values():cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    connection.close()
    from sqlalchemy.engine import make_url
    def url(name):
        return make_url(admin_url).set(drivername='postgresql+psycopg2',database=names[name]).render_as_string(hide_password=False)
    env=dict(os.environ)
    if not args.ci:
        env['S3_REDIS_CONTAINER']=args.redis_container
    env.update(ENVIRONMENT='test',DATABASE_URL=url('main'),REDIS_URL=redis_url,
        SECRET_KEY='s3_synthetic_jwt_'+'a'*40,VOTE_HMAC_KEY='s3_synthetic_vote_'+'b'*40,
        ENTITLEMENT_HMAC_KEY='s3_synthetic_unit_'+'c'*40,SEED_DEMO_DATA='false',PYTHONUTF8='1',
        REQUIRE_S2_SERVICES='1',BREVO_DELIVERY_ENABLED='false',BREVO_API_KEY='',BELENIOS_MODE='off',
        S2_CONCURRENCY_DATABASE_URL=url('concurrency'),S2_EMPTY_MIGRATION_DATABASE_URL=url('empty'),
        S2_MIGRATION_DATABASE_URL=url('populated'),S2_PRIVACY_DATABASE_URL=url('privacy'),ADR001_TEST_PG_URL=url('adr'),
        S3_UPGRADE_DATABASE_URL=url('upgrade_paths'))
    for kind in ('main','adr'):
        run([sys.executable,'-m','alembic','upgrade','head'],{**env,'DATABASE_URL':url(kind)})
    populated={**env,'DATABASE_URL':url('populated')}
    run([sys.executable,'-m','alembic','upgrade','e5f6a7b8c9d0'],populated)
    run([sys.executable,'tests/prepare_s2_migration_data.py'],env)
    run([sys.executable,'-m','alembic','upgrade','head'],populated)
    output=(ROOT/args.output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    junit=output.with_suffix('.xml')
    temporary=ROOT/'.runtime'/('pytest-'+uuid4().hex)
    started=time.monotonic()
    result=run([sys.executable,'-m','pytest','tests','-q','-rs','--disable-warnings','--tb=short',
                '-p','no:cacheprovider','--basetemp',str(temporary),'--junitxml',str(junit)],env)
    sys.stdout.buffer.write(result)
    cases=list(ET.parse(junit).getroot().iter('testcase'))
    if any(case.find('skipped') is not None for case in cases):raise RuntimeError('Required test skipped')
    # Restore must exercise nonempty management/delivery tables as well as historical votes.
    seed='''from app.database import SessionLocal
from app.models import Election,User,Voter,BeleniosBinding,BeleniosUnit,BeleniosOperation,CredentialDelivery
from uuid import uuid4
with SessionLocal() as db:
    db.add(User(id=1,nombre='Synthetic Restore Operator',email='s3-restore@example.org',rol='Administrador General',password_hash='unused'))
    election=Election(id=4,nombre='Synthetic Restore Binding',school_id=1,motor='belenios',estado='Borrador')
    db.add(election);db.flush()
    voter=Voter(nombre='Synthetic Restore Representative',rut='S3-RESTORE',election_id=4,estado='Pendiente')
    db.add(voter);db.flush()
    binding=BeleniosBinding(election_id=4,reference=uuid4().hex,policy='R2',phase='UNKNOWN',approval_ref='synthetic',draft_json='{}',total_people=1,total_units=1)
    db.add(binding);db.flush()
    key=str(uuid4());binding.inflight=key
    db.add(BeleniosUnit(binding_id=binding.id,representative_id=voter.id,alias='synthetic@ejemplo.test'))
    db.add(BeleniosOperation(id=key,binding_id=binding.id,operator_id=1,kind='Prepare',phase='UNKNOWN'))
    db.add(CredentialDelivery(id=str(uuid4()),voter_id=1,proposed_hash='synthetic-hash',status='UNKNOWN',active_slot='1'))
    db.commit()
'''
    run([sys.executable,'-c',seed],populated)
    def snapshot(kind):
        with psycopg2.connect(url(kind).replace('postgresql+psycopg2://','postgresql://',1)) as db:
            with db.cursor() as cursor:
                result={}
                for table in ('schools','users','elections','voters','candidates','voting_entitlements','votes','audit_logs','audit_chain_heads',
                              'belenios_bindings','belenios_units','belenios_operations','credential_deliveries'):
                    cursor.execute(sql.SQL('SELECT row_to_json(t)::text FROM (SELECT * FROM {} ORDER BY id) t').format(sql.Identifier(table)))
                    result[table]=cursor.fetchall()
                return result
    if args.ci:
        pg_env={**env,'PGPASSWORD':make_url(admin_url).password}
        address=make_url(admin_url)
        dump=run(['pg_dump','-h',address.host,'-p',str(address.port or 5432),'-U',address.username,'--no-owner','--clean','--if-exists',names['populated']],pg_env)
        run(['psql','-h',address.host,'-p',str(address.port or 5432),'-U',address.username,'-d',names['restored'],'-v','ON_ERROR_STOP=1'],pg_env,input_bytes=dump)
    else:
        dump=run(['docker','exec',args.postgres_container,'pg_dump','-U','postgres','--no-owner','--clean','--if-exists',names['populated']])
        run(['docker','exec','-i',args.postgres_container,'psql','-U','postgres','-d',names['restored'],'-v','ON_ERROR_STOP=1'],input_bytes=dump)
    if snapshot('populated')!=snapshot('restored'):raise RuntimeError('Restore changed records')
    report={'scope':'synthetic PostgreSQL16/Redis7; no operational data or email sent',
        'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'head':run(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'working_tree':bool(run(['git','status','--porcelain'],cwd=ROOT).strip()),'test_cases':len(cases),'failures':0,'skipped':0,
        'junit_sha256':hashlib.sha256(junit.read_bytes()).hexdigest(),'restored_exactly':True,
        'backup_sha256':hashlib.sha256(dump).hexdigest(),'duration_seconds':round(time.monotonic()-started,2),
        'restore_nonempty_management_tables':True,
        'independent_custody':False,'external_delivery_proven':False}
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
