"""Create an auxiliary disposable election solely for interruption/error tests.

Server-generated credentials/key here are deliberately a weak fixture, not the
independent credential/threshold configuration already demonstrated in H2.
"""
import json
from pathlib import Path
import subprocess
import time
import setup_h2 as lab

lab.STATE = json.loads(lab.STATE_PATH.read_text())
lab.TRACE = json.loads(lab.TRACE_PATH.read_text())
target = lab.PRIVATE / 'faults.json'
if target.exists():
    raise SystemExit('Existing fault fixture; reconcile before recreating')
api = lab.API(18001)
api.token = api.call('POST', 'login/demo', {'username': 'poc-admin'})['token']
account = api.call('GET', 'account')
draft = {'version': 1, 'owners': [account['id']], 'booth': 2, 'group': 'Ed25519', 'languages': ['en'],
         'authentication': ['Configured', 'email'],
         'questions': {'name': 'Fixture descartable de fallos', 'description': 'Solo pruebas de interrupcion, configuracion debil intencional.',
                       'administrator': 'Operador ficticio', 'credential_authority': 'server',
                       'questions': [{'question': 'Prueba', 'answers': ['A', 'B'], 'min': 1, 'max': 1}]}}
uuid = api.call('POST', 'elections', draft, match=True)
fixture = {'uuid': uuid, 'token': api.token, 'phase': 'draft'}
target.write_text(json.dumps(fixture))
base = 'elections/' + uuid
voters = [f'aux{i:02d}@ejemplo.test' for i in range(1, 11)]
api.call('PUT', base + '/draft/voters', voters, match=True)
api.call('POST', base + '/draft/credentials/public', [])
for _ in range(30):
    if api.call('GET', base + '/draft/status')['credentials_ready']:
        break
    time.sleep(1)
else:
    raise RuntimeError('Credential generation incomplete')
creds = api.call('GET', base + '/draft/credentials/private')
fixture['credentials'] = creds
target.write_text(json.dumps(fixture))
api.call('POST', base + '/draft', 'ValidateElection', match=True)
api.call('POST', base, 'Open', match=True)
directory = lab.PRIVATE / uuid / 'faults'
directory.mkdir(parents=True, exist_ok=True)
result = subprocess.run(['docker', 'run', '--rm', '--network', 'theogen-belenios33-poc_ballot-a', '--entrypoint', lab.TOOL,
                         lab.IMAGE, 'archive', 'pull', '--url', 'http://revote:8001/', '--uuid', uuid], capture_output=True)
if result.returncode:
    raise RuntimeError('Could not collect public auxiliary archive')
(directory / (uuid + '.bel')).write_bytes(result.stdout)
(directory / 'credential.txt').write_text(creds[voters[0]] + '\n')
(directory / 'choice.json').write_text('[[1,0]]\n')
fixture['ballots'] = []
for i in range(3):
    raw = lab.tool(directory, 'election', 'generate-ballot', '--privcred', 'credential.txt', '--choice', 'choice.json').rstrip(b'\n')
    ballot_path = directory / f'ballot-{i}.json'
    ballot_path.write_bytes(raw)
    fixture['ballots'].append(str(ballot_path))
fixture['phase'] = 'ready'
target.write_text(json.dumps(fixture, indent=2))
print('Auxiliary synthetic fault fixture ready; no production identities or independent-security claim.')
