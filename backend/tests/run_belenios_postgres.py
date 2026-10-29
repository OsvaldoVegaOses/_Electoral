"""Create and remove only a uniquely named disposable PostgreSQL 16 test container."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]
PRIVATE=ROOT/'.runtime/pg-tests'; PRIVATE.mkdir(parents=True,exist_ok=True)
name='theogen-adr001-pg-'+uuid4().hex[:10]
password=secrets.token_urlsafe(32)
env_file=PRIVATE/(name+'.env')
env_file.write_text('POSTGRES_USER=adr_runner\nPOSTGRES_DB=adr001_tests\nPOSTGRES_PASSWORD='+password+'\n')
def run(args,**kw): return subprocess.run(args,capture_output=True,**kw)
image=json.loads(subprocess.check_output(['docker','image','inspect','postgres:16.10-alpine']))[0]
created=False
try:
    started=run(['docker','run','--rm','-d','--name',name,'--label','org.theogen.scope=adr001-disposable-test','--env-file',str(env_file),'-p','127.0.0.1:55441:5432',image['Id']])
    if started.returncode: raise RuntimeError('Disposable PostgreSQL did not start; no existing resource was changed')
    created=True
    for _ in range(50):
        if run(['docker','exec',name,'pg_isready','-U','adr_runner','-d','adr001_tests']).returncode==0: break
        time.sleep(.5)
    else: raise RuntimeError('PostgreSQL readiness timeout')
    environment=dict(os.environ)
    url='postgresql+psycopg2://adr_runner:'+password+'@127.0.0.1:55441/adr001_tests'
    environment.update(DATABASE_URL=url,ADR001_TEST_PG_URL=url)
    commands=[['-m','alembic','upgrade','head'],['-m','alembic','downgrade','f6a7b8c9d0e1'],['-m','alembic','upgrade','head'],
              ['-m','pytest','tests/test_belenios_postgres.py','-q','--tb=short','--disable-warnings']]
    results=[]
    for command in commands:
        result=run([sys.executable,*command],cwd=ROOT/'backend',env=environment)
        if result.returncode:
            (PRIVATE/(name+'-failure.txt')).write_bytes(result.stdout+result.stderr)
            raise RuntimeError('PostgreSQL test failed; inspect ignored private diagnostic file')
        results.append({'command':'python '+' '.join(command),'exit_code':result.returncode})
        if '-m' in command and 'pytest' in command:
            print(result.stdout.decode(errors='replace').splitlines()[-1],flush=True)
    blocked=run([sys.executable,'-m','alembic','downgrade','f6a7b8c9d0e1'],cwd=ROOT/'backend',env=environment)
    assert blocked.returncode!=0 and b'Hay vinculaciones Belenios' in blocked.stderr
    version=subprocess.check_output(['docker','exec',name,'postgres','--version']).decode().strip()
    report={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'postgres_version':version,'image_id':image['Id'],
            'image_digests':image['RepoDigests'],'commands':results,'populated_downgrade_refused':True,
            'scope':'Dedicated ephemeral container; synthetic data only; no operational database or Sprint 2 worktree altered'}
    directory=ROOT/'doc/motor/evidencias'; directory.mkdir(parents=True,exist_ok=True)
    (directory/'adr001-postgres.json').write_text(json.dumps(report,indent=2)+'\n')
finally:
    if created:
        inspected=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
        assert inspected['Config']['Labels']['org.theogen.scope']=='adr001-disposable-test'
        subprocess.run(['docker','rm','-f',name],check=True,capture_output=True)
    env_file.unlink(missing_ok=True)
