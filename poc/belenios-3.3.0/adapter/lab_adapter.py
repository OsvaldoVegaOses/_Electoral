"""Experimental local-only adapter. No TheoGen database, vote routes or real identities."""
import argparse
import base64
import hashlib
import io
import http.client
import json
from pathlib import Path
import re
import subprocess
import tarfile
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parents[1] / 'doc/poc-belenios/evidencias'
COMMIT = '337887bd1862c7cd057080b530fd80941bfc3c69'
TOOL = '/home/belenios/belenios/_run/usr/bin/belenios-tool'

class AdapterError(RuntimeError):
    pass

class UnknownMutationOutcome(AdapterError):
    pass

class LabAdapter:
    def __init__(self, base_url):
        url = urllib.parse.urlsplit(base_url)
        if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.port not in (18001, 18002) or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
            raise AdapterError('Only the two approved local laboratory endpoints are supported')
        self.base = base_url.rstrip('/')
        self.mode = 'revote' if url.port == 18001 else 'single'
        self.token = None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(self, method, route, payload=None, if_match=False):
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        if if_match:
            current = self.call('GET', route)
            headers['If-Match'] = base64.b64encode(hashlib.sha256(current).digest()).decode().rstrip('=')
        data = None if payload is None else json.dumps(payload, separators=(',', ':')).encode()
        request = urllib.request.Request(self.base + '/api/' + route, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=15) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            # Bodies/capabilities are deliberately not included in public errors.
            raise AdapterError(f'{method} operation rejected with HTTP {error.code}') from None
        except (OSError, urllib.error.URLError, http.client.HTTPException) as error:
            if method in ('POST', 'PUT', 'DELETE'):
                raise UnknownMutationOutcome('Unknown mutation outcome: do not retry; reconcile server state') from None
            raise AdapterError('Read failed; no mutation retried') from error

    def configuration(self):
        data = json.loads(self.call('GET', 'configuration'))
        if data.get('belenios_version') != '3.3.0' or data.get('api_version') != 6:
            raise AdapterError('Unexpected Belenios/API version')
        return data

    @staticmethod
    def synthetic_id(value):
        if not re.fullmatch(r'poc-[a-zA-Z0-9_-]{1,64}', value):
            raise AdapterError('TheoGen identifier must be an explicit synthetic poc-* identifier')
        return value

    def provision_synthetic(self, theogen_id):
        self.synthetic_id(theogen_id)
        mapping_path = ROOT / '.runtime/adapter' / theogen_id / 'mapping.json'
        if mapping_path.exists():
            raise AdapterError('Mapping already exists; reconcile instead of creating another election')
        self.configuration()
        self.token = json.loads(self.call('POST', 'login/demo', {'username': 'poc-admin'}))['token']
        account = json.loads(self.call('GET', 'account'))
        draft = {'version': 1, 'owners': [account['id']], 'booth': 2, 'group': 'Ed25519', 'languages': ['en'],
                 'authentication': ['Configured', 'email'],
                 'questions': {'name': 'Adaptador ' + theogen_id, 'description': 'Borrador sintetico sin votacion ni validez oficial',
                               'administrator': 'Comision ficticia', 'credential_authority': 'Autoridad externa simulada',
                               'questions': [{'question': 'Lista', 'answers': ['A', 'B'], 'min': 1, 'max': 1}]}}
        # Reserve before the request: a lost creation response must also block repetition.
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        intent = {'theogen_election_id': theogen_id, 'phase': 'creation_intent_requires_reconciliation', 'lab_only': True}
        try:
            with mapping_path.open('x', encoding='utf-8') as checkpoint:
                checkpoint.write(json.dumps(intent, indent=2) + '\n')
        except FileExistsError:
            raise AdapterError('Mapping already exists; reconcile instead of creating another election') from None
        uuid = json.loads(self.call('POST', 'elections', draft, if_match=True))
        mapping = {'theogen_election_id': theogen_id, 'belenios_uuid': uuid, 'phase': 'draft_created', 'lab_only': True}
        mapping_path.write_text(json.dumps(mapping, indent=2) + '\n')
        draft['questions']['description'] = 'Contrato API 6 comprobado; intervencion humana para credenciales y trustees'
        self.call('PUT', f'elections/{uuid}/draft', draft, if_match=True)
        voters = [f'adapter{i:02d}@ejemplo.test' for i in range(1, 11)]
        self.call('PUT', f'elections/{uuid}/draft/voters', voters, if_match=True)
        readback = json.loads(self.call('GET', f'elections/{uuid}/draft/voters'))
        if readback != voters:
            raise AdapterError('Voter readback mismatch; do not repeat creation')
        mapping.update(phase='draft_with_10_synthetic_units', enabled_units=10)
        mapping_path.write_text(json.dumps(mapping, indent=2) + '\n')
        return mapping

    def verified_evidence(self, theogen_id, uuid, anchor):
        self.synthetic_id(theogen_id)
        if not re.fullmatch(r'[a-zA-Z0-9]{14}', uuid):
            raise AdapterError('Unexpected laboratory election identifier')
        self.configuration()
        status = json.loads(self.call('GET', f'elections/{uuid}'))
        if status.get('state') != 'Tallied':
            raise AdapterError('A complete tallied election is required')
        if anchor.get('uuid') != uuid or anchor.get('state') != 'Tallied':
            raise AdapterError('Approved public anchor does not identify this completed election')
        head = json.loads(self.call('GET', f'elections/{uuid}/last-event'))
        if head != anchor['final_event']:
            raise AdapterError('Event head differs from approved final anchor')
        roots = json.loads(self.call('GET', f'elections/{uuid}/roots'))
        result_hash = roots.get('result')
        if result_hash != anchor['result_object_hash'] or not re.fullmatch('[0-9a-f]{64}', result_hash or ''):
            raise AdapterError('Missing/unexpected result object')
        raw_result = self.call('GET', f'elections/{uuid}/objects/{result_hash}')
        if hashlib.sha256(raw_result).hexdigest() != result_hash:
            raise AdapterError('API result object hash mismatch')
        result = json.loads(raw_result)
        active = json.loads(self.call('GET', f'elections/{uuid}/ballots'))
        if any(int(weight) != 1 for weight in active.values()):
            raise AdapterError('This prototype only supports unit weights')
        if len(result['result']) != 1 or len(result['result'][0]) != 2:
            raise AdapterError('This prototype only supports one two-option homomorphic question')
        counts = [int(value) for value in result['result'][0]]
        enabled = anchor['enabled_synthetic_units']
        if any(value < 0 for value in counts) or sum(counts) != len(active) or len(active) > enabled:
            raise AdapterError('Result/participation mismatch')
        image_manifest = json.loads((DOCS / 'h1-resultados.json').read_text())
        image = image_manifest['image_id']
        inspected = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
        if inspected['Id'] != image or inspected['Config']['Labels']['org.opencontainers.image.revision'] != COMMIT:
            raise AdapterError('Verifier image provenance mismatch')
        directory = ROOT / '.runtime/adapter' / theogen_id / 'public'
        directory.mkdir(parents=True, exist_ok=True)
        collected = subprocess.run(['docker', 'run', '--rm', '--network', 'theogen-belenios33-poc_ballot-' + ('a' if self.mode == 'revote' else 'b'),
                                    '--entrypoint', TOOL, image, 'archive', 'pull', '--url', f'http://{self.mode}:8001/', '--uuid', uuid], capture_output=True)
        if collected.returncode:
            raise AdapterError('Public archive download failed')
        archive = collected.stdout
        archive_hash = hashlib.sha256(archive).hexdigest()
        if archive_hash != anchor['public_archive_sha256']:
            raise AdapterError('Public archive differs from approved final anchor')
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            member = next((m for m in tar.getmembers() if result_hash in m.name and m.isfile()), None)
            if member is None or tar.extractfile(member).read() != raw_result:
                raise AdapterError('Archive/API result mismatch')
        (directory / (uuid + '.bel')).write_bytes(archive)
        verification = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop', 'ALL',
                                       '--security-opt', 'no-new-privileges:true',
                                       '--mount', f'type=bind,src={directory.resolve()},dst=/audit,readonly',
                                       '--entrypoint', TOOL, image, 'election', 'verify', '--dir', '/audit'], capture_output=True)
        if verification.returncode or b'all checks passed' not in verification.stderr or b'no result to check' in verification.stderr:
            raise AdapterError('Independent process verification did not confirm a complete result')
        return {'schema': 'theogen-belenios-lab-evidence/v1', 'lab_only': True,
                'theogen_election_id': theogen_id, 'belenios_uuid': uuid, 'belenios_version': '3.3.0', 'upstream_commit': COMMIT,
                'state': 'Tallied', 'counts': counts, 'enabled_units': enabled, 'counted_ballots': len(active),
                'participation': len(active) / enabled, 'public_archive_sha256': archive_hash,
                'final_event_hash': head['hash'], 'result_object_hash': result_hash,
                'verifier_image_id': image, 'verification_exit_code': 0,
                'legal_status': 'Experimental evidence schema; not a legally valid signed election record'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--theogen-id', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('provision-synthetic')
    evidence = commands.add_parser('verified-evidence')
    evidence.add_argument('--uuid', required=True)
    evidence.add_argument('--anchors', type=Path, default=DOCS / 'h2-resultados.json')
    args = parser.parse_args()
    adapter = LabAdapter(args.base_url)
    if args.command == 'provision-synthetic':
        mapping_path = ROOT / '.runtime/adapter' / args.theogen_id / 'mapping.json'
        if mapping_path.exists():
            raise AdapterError('Mapping already exists; reconcile it instead of creating another election')
        result = adapter.provision_synthetic(args.theogen_id)
    else:
        anchor = json.loads(args.anchors.read_text())['elections'][adapter.mode]
        result = adapter.verified_evidence(args.theogen_id, args.uuid, anchor)
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except AdapterError as error:
        raise SystemExit(str(error))
