"""Tally H4 with two external shares and preserve public, independently checked evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import setup_h2 as lab

lab.PRIVATE = lab.ROOT / '.runtime/private/h4'
lab.STATE_PATH = lab.PRIVATE / 'h4-state.json'
lab.TRACE_PATH = lab.ROOT / '.runtime/h4-api-trace.json'
lab.STATE = json.loads(lab.STATE_PATH.read_text())
lab.TRACE = json.loads(lab.TRACE_PATH.read_text())
DOCS = lab.ROOT.parents[1] / 'doc/poc-belenios/evidencias'
lab.IMAGE = json.loads((DOCS / 'h1-resultados.json').read_text())['image_id']
checkpoint = lab.PRIVATE / 'tally-intent.json'
if checkpoint.exists():
    raise SystemExit('Existing H4 tally intent: reconcile; never repeat an uncertain mutation')
ui = json.loads((lab.PRIVATE / 'h2-ui-journal.json').read_text())
assert sum(v['phase'] == 'confirmed' and v['result']['kind'] == 'Ok' for k, v in ui.items() if k.endswith('-initial')) == 8
assert ui['single-0-revote']['result'] == {'kind': 'Error', 'error': 'RevoteNotAllowed'}
checkpoint.write_text(json.dumps({'phase': 'close_intent'}))
started = time.monotonic()
election = lab.STATE['elections']['single']
api = lab.API(18002)
api.token = api.call('POST', 'login/demo', {'username': 'poc-admin'})['token']
election['admin_token'] = api.token
lab.save()
base = 'elections/' + election['uuid']
assert len(api.call('GET', base + '/ballots')) == 8
api.call('POST', base, 'Close', match=True)
api.call('POST', base, 'ComputeEncryptedTally', match=True)
assert api.call('GET', base)['state'] == 'EncryptedTally'
work = lab.ROOT / '.runtime/public/h4'
work.mkdir(parents=True, exist_ok=True)
def collect(directory):
    directory.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(['docker', 'run', '--rm', '--network', 'theogen-belenios33-poc_ballot-b', '--entrypoint', lab.TOOL,
                          lab.IMAGE, 'archive', 'pull', '--url', 'http://single:8001/', '--uuid', election['uuid']], capture_output=True)
    if run.returncode:
        raise RuntimeError('Public archive download failed')
    path = directory / (election['uuid'] + '.bel')
    path.write_bytes(run.stdout)
    return path
encrypted = collect(work / 'encrypted-tally')
partials = api.call('GET', base + '/partial-decryptions')
assert partials['threshold'] == 2
for index in (1, 2):
    trustee = election['trustees'][index - 1]
    custody = Path(trustee['directory'])
    shutil.copyfile(encrypted, custody / encrypted.name)
    output = lab.tool(custody, 'election', 'decrypt-threshold', '--key', trustee['key_id'] + '.key',
                      '--decryption-key', trustee['key_id'] + '.dkey', '--trustee-id', str(index + 1))
    token = next(t['token'] for t in partials['trustees'] if t['address'] == f'trustee{index}@ejemplo.test')
    api.call('POST', base + '/trustee', output.splitlines()[0], token=token)
api.call('POST', base, 'ReleaseTally', match=True)
assert api.call('GET', base)['state'] == 'Tallied'
roots = api.call('GET', base + '/roots')
result = api.call('GET', base + '/objects/' + roots['result'])
assert result['result'] == [['4', '4']] or result['result'] == [[4, 4]]
archive = collect(work / 'final')
verification = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                               '--security-opt', 'no-new-privileges:true', '--mount', f'type=bind,src={archive.parent.resolve()},dst=/audit,readonly',
                               '--entrypoint', lab.TOOL, lab.IMAGE, 'election', 'verify', '--dir', '/audit'], capture_output=True)
assert verification.returncode == 0 and b'all checks passed' in verification.stderr and b'no result to check' not in verification.stderr
data = archive.read_bytes()
private_values = [election['admin_token'].encode(), *[v.encode() for v in json.loads(Path(election['private_credentials_file']).read_text()).values()]]
for trustee in election['trustees']:
    private_values.extend([trustee['token'].encode(), (Path(trustee['directory']) / (trustee['key_id'] + '.key')).read_bytes().strip(),
                           (Path(trustee['directory']) / (trustee['key_id'] + '.dkey')).read_bytes().strip()])
assert b'@ejemplo.test' not in data and not any(v and v in data for v in private_values)
destination = DOCS / 'h4-publico' / archive.name
destination.parent.mkdir(exist_ok=True)
shutil.copyfile(archive, destination)
anchor = {'uuid': election['uuid'], 'state': 'Tallied', 'enabled_synthetic_units': 8, 'active_ballots': 8, 'result': [4, 4], 'expected': [4, 4],
          'final_event': api.call('GET', base + '/last-event'), 'result_object_hash': roots['result'],
          'public_archive_sha256': hashlib.sha256(data).hexdigest(), 'public_archive_bytes': len(data),
          'public_archive_repository_path': destination.relative_to(lab.ROOT.parents[1]).as_posix(),
          'verification': {'exit_code': verification.returncode, 'stdout': verification.stdout.decode(), 'stderr': verification.stderr.decode()},
          'verifier_image_id': lab.IMAGE, 'external_threshold': '2/3', 'mandatory_server_key': True}
report = {'milestone': 'H4', 'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'family_summary': lab.STATE['family_summary'],
          'family_checks': lab.STATE['family_checks'], 'elections': {'single': anchor}, 'setup_elapsed_seconds': lab.STATE['setup_elapsed_seconds'],
          'tally_and_verification_elapsed_seconds': round(time.monotonic() - started, 3),
          'limitations': ['Synthetic representation decisions only; no legal family rule approved', 'Same host/operator; no independent human audit',
                          'Pseudonymous laboratory mailboxes; actual delivery to representatives is not implemented', 'No production TheoGen integration']}
(DOCS / 'h4-resultados.json').write_text(json.dumps(report, indent=2) + '\n')
checkpoint.write_text(json.dumps({'phase': 'complete', 'uuid': election['uuid']}))
lab.STATE['phase'] = 'h4_tallied_and_verified'
lab.save()
print(json.dumps({'H4_tally': 'PASS', 'result': [4, 4], 'counted_family_units': 8, 'verifier_exit': verification.returncode}))
