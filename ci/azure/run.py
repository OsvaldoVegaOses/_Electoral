"""Full CI on the ephemeral ACR host. No production endpoints, data or credentials."""
import base64
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
from uuid import uuid4
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'.runtime'/'azure-ci'
STAGES=[]
GITLEAKS='ghcr.io/gitleaks/gitleaks:v8.28.0'


def command(args,*,cwd=ROOT,data=None,capture=False,timeout=1200):
    result=subprocess.run(args,cwd=cwd,input=data,capture_output=capture,timeout=timeout)
    if capture and result.returncode:
        sys.stdout.buffer.write(result.stdout);sys.stderr.buffer.write(result.stderr)
    result.check_returncode()
    return result.stdout if capture else None


def stage(name,fn):
    started=time.monotonic()
    print('AZURE_CI_STAGE '+name+' started',flush=True)
    try:
        fn()
    except Exception:
        STAGES.append({'name':name,'result':'failed','seconds':round(time.monotonic()-started,2)})
        raise
    STAGES.append({'name':name,'result':'passed','seconds':round(time.monotonic()-started,2)})
    print('AZURE_CI_STAGE '+name+' passed',flush=True)


def archive_files(files):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w') as tar:
        for name,data in files.items():
            member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o644
            tar.addfile(member,io.BytesIO(data))
    return output.getvalue()


def secrets():
    command(['docker','pull',GITLEAKS])
    for mode in ('dir','git'):
        files={'.gitleaks.toml':(ROOT/'.gitleaks.toml').read_bytes()}
        if mode=='dir':
            names=command(['git','ls-files','-z'],capture=True).decode().split('\0')
            files.update({name:(ROOT/name).read_bytes() for name in names if name})
        else:
            files.update({str(path.relative_to(ROOT)).replace('\\','/'):path.read_bytes()
                          for path in (ROOT/'.git').rglob('*') if path.is_file()})
        output=command(['docker','run','--rm','-i','--network','none','--entrypoint','/bin/sh',GITLEAKS,
            '-c','mkdir /scan && tar -xf - -C /scan && git config --global --add safe.directory /scan && '
                 'exec gitleaks '+mode+' /scan --config /scan/.gitleaks.toml --redact=100 --no-banner'],
            data=archive_files(files),capture=True)
        (OUTPUT/('gitleaks-'+mode+'.txt')).write_bytes(output)
    print('Secret scanning passed for tracked files and committed history',flush=True)


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    sha=command(['git','rev-parse','HEAD'],capture=True).decode().strip()
    if sha!=os.environ['EXPECTED_SHA'] or not re.fullmatch('[0-9a-f]{40}',sha):
        raise RuntimeError('The uploaded commit does not match the requested SHA')
    if command(['git','status','--porcelain'],capture=True).strip():
        raise RuntimeError('Remote source must be clean')
    run_id=os.environ['AZURE_CI_RUN_ID']
    if not re.fullmatch('[a-zA-Z0-9_-]+',run_id):raise RuntimeError('Invalid run ID')
    prefix='electoral-ci-'+run_id.lower()+'-'+uuid4().hex[:8]
    pg,redis=prefix+'-pg',prefix+'-redis'
    owned=[]
    os.environ.update(ENVIRONMENT='test',SEED_DEMO_DATA='false',BELENIOS_MODE='off',
        BREVO_DELIVERY_ENABLED='false',BREVO_API_KEY='',PYTHONUTF8='1',
        SECRET_KEY='s3_azure_ci_jwt_'+'a'*40,VOTE_HMAC_KEY='s3_azure_ci_vote_'+'b'*40,
        ENTITLEMENT_HMAC_KEY='s3_azure_ci_unit_'+'c'*40)
    try:
        def services():
            for name,image,port,extra in [(pg,'postgres:16','5432',['-e','POSTGRES_PASSWORD=s3_synthetic_only']),
                                         (redis,'redis:7-alpine','6379',[])]:
                command(['docker','run','-d','--name',name,'--label','theogen.task=sprint3-local',
                    '--label','theogen.ci.source='+sha,'-p','127.0.0.1::'+port,*extra,image])
                owned.append(name)
            deadline=time.monotonic()+90
            for name,probe in [(pg,['pg_isready','-U','postgres']),(redis,['redis-cli','ping'])]:
                while subprocess.run(['docker','exec',name,*probe],capture_output=True).returncode:
                    if time.monotonic()>deadline:raise RuntimeError('Synthetic service readiness failed')
                    time.sleep(1)
        stage('synthetic-services',services)
        stage('backend-migrations-concurrency-restore',lambda:command([sys.executable,'scripts/verify_s3_local.py',
            '--postgres-container',pg,'--redis-container',redis,'--output','.runtime/s3-integration.json']))
        stage('frontend-lint',lambda:command(['npm','run','lint'],cwd=ROOT/'frontend'))
        stage('frontend-build',lambda:command(['npm','run','build'],cwd=ROOT/'frontend'))
        stage('e2e-real-http-postgresql',lambda:command([sys.executable,'scripts/verify_s3_e2e.py','--postgres-container',pg]))
        stage('belenios-ui-api-doubles',lambda:command(['npx','playwright','test','--config','playwright.belenios.config.js'],cwd=ROOT/'frontend'))
        stage('python-dependency-audit',lambda:command([sys.executable,'-m','pip_audit','--local','--strict',
            '--progress-spinner','off','--format','json','--output',str(OUTPUT/'pip-audit.json')]))
        stage('npm-dependency-audit',lambda:(OUTPUT/'npm-audit.json').write_bytes(command(['npm','audit','--audit-level=low','--json'],cwd=ROOT/'frontend',capture=True)))
        stage('secrets-current-and-history',secrets)
        def operations():
            command(['docker','compose','config','--quiet'])
            command(['docker','run','--rm','-i','--network','none','--add-host','backend:127.0.0.1',
                '--entrypoint','/bin/sh','nginx:alpine','-c',
                'cat > /etc/nginx/conf.d/default.conf && exec nginx -t'],data=(ROOT/'frontend/nginx.conf').read_bytes())
        stage('compose-nginx',operations)
        backend=json.loads((ROOT/'.runtime/s3-integration.json').read_text())
        if backend['head']!=sha or backend['working_tree'] or backend['skipped'] or backend['failures']:
            raise RuntimeError('Backend evidence does not match the clean source SHA')
        junit=ROOT/'frontend/test-results/junit.xml'
        cases=list(ET.parse(junit).getroot().iter('testcase'))
        if not cases or any(case.find(tag) is not None for case in cases for tag in ('failure','error','skipped')):
            raise RuntimeError('E2E cannot pass with failures or omissions')
        summary={'source_sha':sha,'run_id':run_id,'recorded_at_utc':datetime.now(timezone.utc).isoformat(),
            'provider':'Azure Container Registry Tasks','result':'passed','stages':STAGES,
            'backend':backend,'e2e_tests':len(cases),'belenios_ui_tests':5,'belenios_provider':'API doubles',
            'versions':{'python':platform.python_version(),'node':command(['node','--version'],capture=True).decode().strip(),
                        'docker_server':command(['docker','version','--format','{{.Server.Version}}'],capture=True).decode().strip()},
            'production_services_modified':False,'email_sent':False,'pilot_activated':False,
            'evidence_image':os.environ['EVIDENCE_IMAGE']}
        exports={'summary.json':json.dumps(summary,indent=2).encode(),
            'backend-junit.xml':(ROOT/'.runtime/s3-integration.xml').read_bytes(),'e2e-junit.xml':junit.read_bytes(),
            'pip-audit.json':(OUTPUT/'pip-audit.json').read_bytes(),'npm-audit.json':(OUTPUT/'npm-audit.json').read_bytes()}
        exports['checksums.json']=json.dumps({name:hashlib.sha256(data).hexdigest() for name,data in exports.items()},indent=2).encode()
        exports['Dockerfile']=(f'FROM scratch\nLABEL org.opencontainers.image.revision="{sha}"\nCOPY . /evidence/\n').encode()
        command(['docker','build','-t',os.environ['EVIDENCE_IMAGE'],'-'],data=archive_files(exports))
        print('AZURE_CI_SUMMARY '+base64.b64encode(exports['summary.json']).decode(),flush=True)
    finally:
        for name in reversed(owned):
            label=command(['docker','inspect','--format','{{index .Config.Labels "theogen.ci.source"}}',name],capture=True).decode().strip()
            if label!=sha:raise RuntimeError('Refusing cleanup of a container not owned by this CI run')
            command(['docker','rm','-f',name])


if __name__=='__main__':main()
