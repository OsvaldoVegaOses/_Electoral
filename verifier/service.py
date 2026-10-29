"""Public-data collector + networkless worker. Neither accepts credentials or arbitrary commands.

Run collector behind TLS on a private network. Run worker in a distinct container with
network_mode:none, read_only:true and only the public job volume mounted.
"""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4

LIMIT=8*1024*1024
ROOT=Path(os.environ.get('VERIFIER_JOBS','/jobs'))
TOOL=os.environ.get('BELENIOS_TOOL','/home/belenios/belenios/_run/usr/bin/belenios-tool')

def verify_public(directory,tool=TOOL):
    """Called only by the container that has no network or private mounts."""
    archive=list(directory.glob('*.bel'))
    if len(archive)!=1 or archive[0].is_symlink() or archive[0].stat().st_size>LIMIT:
        return {'ok':False}
    digest=hashlib.sha256(archive[0].read_bytes()).hexdigest()
    try:
        result=subprocess.run([tool,'election','verify','--dir',str(directory)],capture_output=True,timeout=45)
        ok=result.returncode==0 and b'all checks passed' in result.stderr and b'no result to check' not in result.stderr
        return {'ok':ok,'archive_sha256':digest,'exit_code':result.returncode}
    except (OSError,subprocess.SubprocessError):
        return {'ok':False}

def worker_once(root=ROOT,tool=TOOL):
    for job in root.iterdir():
        if not re.fullmatch(r'[a-f0-9]{32}',job.name) or job.is_symlink() or not job.is_dir():
            continue
        if not (job/'ready').is_file() or (job/'result.json').exists():
            continue
        result=verify_public(job/'public',tool)
        temporary=job/'result.tmp'
        temporary.write_text(json.dumps(result),encoding='utf-8')
        temporary.replace(job/'result.json')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass  # No request headers, bodies or public/private correspondence in access logs.

    def do_POST(self):
        secret=os.environ.get('VERIFIER_TOKEN','')
        if len(secret)<32 or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+secret):
            self.send_error(401);return
        if self.path!='/verify':
            self.send_error(404);return
        job=None
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=1024:
                raise ValueError
            body=json.loads(self.rfile.read(length))
            if set(body)!={'policy','uuid'} or body['policy'] not in ('R1','R2') or not re.fullmatch(r'[A-Za-z0-9]{14}',body['uuid']):
                raise ValueError
            base=os.environ['COLLECTOR_'+body['policy']+'_URL']
            if not base.startswith(('https://','http://')) or any(char in base for char in ('?','#','@')):
                raise ValueError
            job=ROOT/uuid4().hex
            public=job/'public';public.mkdir(parents=True)
            archive=public/(body['uuid']+'.bel')
            with archive.open('wb') as output:
                collected=subprocess.run([TOOL,'archive','pull','--url',base,'--uuid',body['uuid']],stdout=output,stderr=subprocess.DEVNULL,timeout=45)
            if collected.returncode or not 0<archive.stat().st_size<=LIMIT:
                raise ValueError
            (job/'ready').touch()
            deadline=time.monotonic()+50
            while time.monotonic()<deadline and not (job/'result.json').exists():
                time.sleep(.1)
            result=json.loads((job/'result.json').read_text(encoding='utf-8'))
            data=archive.read_bytes()
            if not result.get('ok') or result.get('archive_sha256')!=hashlib.sha256(data).hexdigest():
                raise ValueError
        except (KeyError,ValueError,OSError,subprocess.SubprocessError):
            self.send_error(503,'Public archive verification not confirmed');return
        self.send_response(200)
        self.send_header('Content-Type','application/octet-stream')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers();self.wfile.write(data)

if __name__=='__main__':
    ROOT.mkdir(exist_ok=True,parents=True)
    if len(sys.argv)!=2 or sys.argv[1] not in ('collector','worker'):
        raise SystemExit('Select collector or worker')
    if sys.argv[1]=='collector':
        ThreadingHTTPServer(('0.0.0.0',8081),Handler).serve_forever()
    else:
        while True:
            worker_once()
            time.sleep(.2)
