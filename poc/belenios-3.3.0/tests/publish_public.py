"""Copy only verified synthetic public archives, rejecting known laboratory secrets."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parents[1] / 'doc/poc-belenios/evidencias'
PRIVATE = ROOT / '.runtime/private'
state = json.loads((PRIVATE / 'h2-state.json').read_text())
report_path = DOCS / 'h2-resultados.json'
report = json.loads(report_path.read_text())
secrets = []
for election in state['elections'].values():
    secrets.append(election['admin_token'].encode())
    secrets.extend(value.encode() for value in json.loads(Path(election['private_credentials_file']).read_text()).values())
    for trustee in election['trustees']:
        secrets.append(trustee['token'].encode())
        secrets.append((Path(trustee['directory']) / (trustee['key_id'] + '.key')).read_bytes().strip())
for mode in ('revote', 'single'):
    election = report['elections'][mode]
    source = ROOT / '.runtime/public' / mode / 'final' / (election['uuid'] + '.bel')
    data = source.read_bytes()
    assert hashlib.sha256(data).hexdigest() == election['public_archive_sha256']
    assert b'@ejemplo.test' not in data
    assert not any(secret and secret in data for secret in secrets)
    destination = DOCS / 'h2-publico' / mode / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    election['public_archive_repository_path'] = destination.relative_to(ROOT.parents[1]).as_posix()
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('PASS: two public synthetic archives copied; hashes match and no known credential, admin/trustee capability or synthetic email is present.')
