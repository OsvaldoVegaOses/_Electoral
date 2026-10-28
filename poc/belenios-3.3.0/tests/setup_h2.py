"""Prepare two synthetic H2 elections using the pinned public API and official CLI.

This is a laboratory protocol test, not a TheoGen integration adapter.
Private artifacts and all capabilities stay under the ignored .runtime directory.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.runtime/private'
STATE_PATH = PRIVATE / 'h2-state.json'
TRACE_PATH = ROOT / '.runtime/h2-api-trace.json'
IMAGE = 'theogen-belenios-poc:3.3.0-337887bd'
TOOL = '/home/belenios/belenios/_run/usr/bin/belenios-tool'
STATE = {'phase': 'preparing', 'elections': {}}
TRACE = []
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def save():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(STATE, indent=2) + '\n', encoding='utf-8')
    TRACE_PATH.write_text(json.dumps(TRACE, indent=2) + '\n', encoding='utf-8')

class API:
    def __init__(self, port):
        self.port = port
        self.token = None

    def call(self, method, path, body=None, token=None, raw=False, match=False, expected=200, if_match=None):
        headers = {'Content-Type': 'application/json'}
        credential = self.token if token is None else token
        if credential:
            headers['Authorization'] = 'Bearer ' + credential
        if match:
            current = self.call('GET', path, token=token, raw=True)
            headers['If-Match'] = base64.b64encode(hashlib.sha256(current).digest()).decode().rstrip('=')
        if if_match is not None:
            headers['If-Match'] = if_match
        payload = body if isinstance(body, bytes) else None if body is None else json.dumps(body, separators=(',', ':')).encode()
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}/api/{path}', data=payload, headers=headers, method=method)
        try:
            with OPENER.open(req, timeout=15) as response:
                code, content = response.status, response.read()
        except urllib.error.HTTPError as error:
            code, content = error.code, error.read()
        except (OSError, urllib.error.URLError) as error:
            STATE['phase'] = 'UNKNOWN_HTTP_OUTCOME_DO_NOT_RETRY'
            save()
            raise RuntimeError('Unknown HTTP outcome; reconcile state before any repeated mutation') from error
        TRACE.append({'port': self.port, 'method': method, 'path': path, 'status': code,
                      'response_sha256': hashlib.sha256(content).hexdigest(), 'if_match': bool(match or if_match)})
        save()
        if code != expected:
            # Error variants may be diagnostic; capabilities are never printed.
            try:
                safe_error = json.loads(content).get('error', 'unexpected response')
            except (ValueError, AttributeError):
                safe_error = 'unexpected response'
            raise RuntimeError(f'{method} {path}: expected {expected}, observed {code}; {safe_error}')
        if raw:
            return content
        return json.loads(content)

def tool(directory, *args, stdin=None):
    directory.mkdir(parents=True, exist_ok=True)
    command = ['docker', 'run', '--rm', '--network', 'none', '--entrypoint', TOOL,
               '--mount', f'type=bind,src={directory.resolve()},dst=/work', '--workdir', '/work']
    if stdin is not None:
        command.append('-i')
    result = subprocess.run(command + [IMAGE, *args], input=stdin, capture_output=True)
    if result.returncode:
        raise RuntimeError('Official CLI failed in ' + args[0] + '/' + args[1] + '; exit ' + str(result.returncode))
    return result.stdout

def write_json(path, value):
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n', encoding='utf-8')

def setup(mode, port):
    api = API(port)
    login = api.call('POST', 'login/demo', {'username': 'poc-admin'})
    api.token = login['token']
    account = api.call('GET', 'account')
    draft = {
        'version': 1, 'owners': [account['id']], 'booth': 2, 'group': 'Ed25519',
        'languages': ['en'], 'authentication': ['Configured', 'email'],
        'questions': {'name': 'Eleccion ficticia ' + mode, 'description': 'Diez unidades sinteticas. Sin validez oficial.',
                      'administrator': 'Comision ficticia', 'credential_authority': 'Autoridad externa simulada',
                      'questions': [{'question': 'Elija una lista', 'answers': ['Lista A', 'Lista B'], 'min': 1, 'max': 1}]},
    }
    uuid = api.call('POST', 'elections', draft, match=True)
    election = {'uuid': uuid, 'port': port, 'admin_token': api.token, 'phase': 'draft', 'trustees': []}
    STATE['elections'][mode] = election
    save()
    path = f'elections/{uuid}'
    voters = [f'votante{i:02d}@ejemplo.test' for i in range(1, 11)]
    api.call('PUT', path + '/draft/voters', voters, match=True)
    authority = PRIVATE / uuid / 'authority'
    authority.mkdir(parents=True, exist_ok=True)
    (authority / 'voters.txt').write_text('\n'.join(voters) + '\n', encoding='ascii')
    tool(authority, 'setup', 'generate-credentials', '--uuid', uuid, '--group', 'Ed25519', '--file', 'voters.txt')
    public = json.loads(next(authority.glob('*.pubcreds')).read_text())
    credentials = json.loads(next(authority.glob('*.privcreds')).read_text())
    assert len(public) == len(credentials) == 10
    election['private_credentials_file'] = str(next(authority.glob('*.privcreds')))
    election['voters'] = voters
    cap_raw = api.call('GET', path + '/draft/credentials/token', raw=True).decode()
    try:
        cap = json.loads(cap_raw)
    except ValueError:
        cap = cap_raw
    api.call('POST', path + '/draft/credentials/public', public, token=cap)
    api.call('PUT', path + '/draft/voters', voters, expected=403, match=True)
    election['phase'] = 'credentials_uploaded'
    save()

    api.call('POST', path + '/draft/trustees', ['SetThreshold', 0], match=True)
    for i in range(1, 4):
        api.call('POST', path + '/draft/trustees', ['Add', {'address': f'trustee{i}@ejemplo.test', 'name': f'Custodia ficticia {i}'}], match=True)
    api.call('POST', path + '/draft/trustees', ['SetThreshold', 2], match=True)
    trustees = api.call('GET', path + '/draft/trustees')[1]['trustees']
    for i, trustee in enumerate(trustees, 1):
        custody = PRIVATE / uuid / f'trustee-{i}'
        key_id = tool(custody, 'setup', 'generate-trustee-key-threshold', '--group', 'Ed25519', '--threshold-context', f'{i}/2/3', '--step', '1').decode().strip()
        election['trustees'].append({'index': i, 'directory': str(custody), 'key_id': key_id, 'token': trustee['token']})
        certificate = (custody / (key_id + '.cert')).read_bytes()
        api.call('POST', path + '/draft/trustee', certificate, token=trustee['token'])
    save()
    for trustee in election['trustees']:
        status = api.call('GET', path + '/draft/trustee', token=trustee['token'])
        pedersen = status[1][1]
        assert pedersen['step'] == 3
        custody = Path(trustee['directory'])
        (custody / 'certs.jsons').write_text(''.join(json.dumps(c, separators=(',', ':')) + '\n' for c in pedersen['certs']), encoding='utf-8')
        polynomial = tool(custody, 'setup', 'generate-trustee-key-threshold', '--group', 'Ed25519', '--certs', 'certs.jsons', '--key', trustee['key_id'] + '.key', '--step', '3')
        api.call('POST', path + '/draft/trustee', polynomial, token=trustee['token'])
    for trustee in election['trustees']:
        status = api.call('GET', path + '/draft/trustee', token=trustee['token'])
        pedersen = status[1][1]
        assert pedersen['step'] == 5
        custody = Path(trustee['directory'])
        output = tool(custody, 'setup', 'generate-trustee-key-threshold', '--group', 'Ed25519', '--certs', 'certs.jsons', '--key', trustee['key_id'] + '.key', '--step', '5', stdin=json.dumps(pedersen['vinput']).encode() + b'\n')
        write_json(custody / 'voutput.json', json.loads(output))
        (custody / (trustee['key_id'] + '.dkey')).write_text(json.loads(output)['private_key'] + '\n', encoding='ascii')
        api.call('POST', path + '/draft/trustee', output, token=trustee['token'])
    status = api.call('GET', path + '/draft/status')
    assert status['num_voters'] == 10 and status['credentials_ready'] and status['trustees_ready']
    api.call('POST', path + '/draft', 'ValidateElection', match=True)
    assert api.call('GET', path)['state'] == 'Closed'
    api.call('POST', path, 'Open', match=True)
    assert api.call('GET', path)['state'] == 'Open'
    election['phase'] = 'open_no_ballots'
    save()
    print(json.dumps({'mode': mode, 'uuid': uuid, 'phase': election['phase'], 'synthetic_voters': 10, 'external_threshold': '2/3'}), flush=True)

def main():
    if STATE_PATH.exists():
        raise SystemExit('Existing H2 state: reconcile/resume explicitly; never create duplicate elections by retrying this script')
    PRIVATE.mkdir(parents=True, exist_ok=True)
    STATE['started_at_utc'] = datetime.now(timezone.utc).isoformat()
    save()
    setup('revote', 18001)
    setup('single', 18002)
    STATE['phase'] = 'both_open_no_ballots'
    save()

if __name__ == '__main__':
    main()
