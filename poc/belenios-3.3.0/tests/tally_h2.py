"""Close, threshold-tally and independently verify the two synthetic elections."""
from datetime import datetime, timezone
import hashlib
import base64
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import urllib.request
import setup_h2 as lab

lab.STATE = json.loads(lab.STATE_PATH.read_text())
lab.TRACE = json.loads(lab.TRACE_PATH.read_text())
JOURNAL = lab.PRIVATE / 'h2-tally-journal.json'
REPORT_PATH = lab.ROOT.parents[1] / 'doc/poc-belenios/evidencias/h2-resultados.json'
reports = json.loads(REPORT_PATH.read_text()) if REPORT_PATH.exists() else {'milestone': 'H2', 'elections': {}}
progress = json.loads(JOURNAL.read_text()) if JOURNAL.exists() else {}

def save_progress():
    JOURNAL.write_text(json.dumps(progress, indent=2) + '\n')
    REPORT_PATH.write_text(json.dumps(reports, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

def docker(*args):
    return subprocess.check_output(['docker', *args], stderr=subprocess.PIPE)

def collect(mode, election, directory):
    directory.mkdir(parents=True, exist_ok=True)
    data = docker('run', '--rm', '--network', 'theogen-belenios33-poc_ballot-' + ('a' if mode == 'revote' else 'b'),
                  '--entrypoint', lab.TOOL, lab.IMAGE, 'archive', 'pull', '--url', f'http://{mode}:8001/', '--uuid', election['uuid'])
    archive = directory / (election['uuid'] + '.bel')
    archive.write_bytes(data)
    return archive

def verify(directory):
    result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--read-only',
                             '--mount', f'type=bind,src={directory.resolve()},dst=/audit,readonly',
                             '--entrypoint', lab.TOOL, lab.IMAGE, 'election', 'verify', '--dir', '/audit'], capture_output=True)
    return {'exit_code': result.returncode, 'stdout': result.stdout.decode(errors='replace'), 'stderr': result.stderr.decode(errors='replace')}

def ready(port):
    for _ in range(45):
        try:
            with lab.OPENER.open(f'http://127.0.0.1:{port}/api/configuration', timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError('Restart readiness failed')

def tally(mode, election):
    if progress.get(mode) == 'complete':
        return
    if mode in progress:
        raise RuntimeError('Existing tally phase must be reconciled explicitly before resume')
    api = lab.API(election['port'])
    api.token = election['admin_token']
    path = 'elections/' + election['uuid']
    ui = json.loads((lab.PRIVATE / 'h2-ui-journal.json').read_text())
    api_votes = json.loads((lab.PRIVATE / 'h2-api-votes.json').read_text())
    assert all(ui[f'{mode}-{i}-initial']['phase'] == 'confirmed' for i in range(10))
    assert ui[f'{mode}-0-revote']['phase'] == 'confirmed' and api_votes[mode]['phase'] == 'confirmed'
    active_before = api.call('GET', path + '/ballots')
    assert len(active_before) == 10
    event_before = api.call('GET', path + '/last-event')
    progress[mode] = 'restart_before_tally'
    save_progress()
    subprocess.check_output(['docker', 'compose', '-f', str(lab.ROOT / 'docker-compose.poc.yml'), 'restart', mode], stderr=subprocess.STDOUT)
    ready(election['port'])
    api.call('GET', 'elections', expected=401)
    api.token = api.call('POST', 'login/demo', {'username': 'poc-admin'})['token']
    election['admin_token'] = api.token
    lab.save()
    assert api.call('GET', path + '/ballots') == active_before
    assert api.call('GET', path + '/last-event') == event_before
    api.call('POST', path, 'Close', expected=412, if_match='obsolete-hash')
    assert api.call('GET', path)['state'] == 'Open'
    api.call('POST', path, 'Close', match=True)
    assert api.call('GET', path)['state'] == 'Closed'
    progress[mode] = 'closed'
    save_progress()
    api.call('POST', path, 'ComputeEncryptedTally', match=True)
    assert api.call('GET', path)['state'] == 'EncryptedTally'
    public = lab.ROOT / '.runtime/public' / mode
    tally_archive = collect(mode, election, public / 'encrypted-tally')
    partials = api.call('GET', path + '/partial-decryptions')
    assert partials['threshold'] == 2
    chosen = [1, 2] if mode == 'revote' else [1, 3]
    for count, index in enumerate(chosen, 1):
        trustee = election['trustees'][index - 1]
        custody = Path(trustee['directory'])
        shutil.copyfile(tally_archive, custody / tally_archive.name)
        output = lab.tool(custody, 'election', 'decrypt-threshold', '--key', trustee['key_id'] + '.key',
                          '--decryption-key', trustee['key_id'] + '.dkey', '--trustee-id', str(index + 1))
        partial = output.splitlines()[0]
        json.loads(partial)
        token = next(t['token'] for t in partials['trustees'] if t['address'] == f'trustee{index}@ejemplo.test')
        api.call('POST', path + '/trustee', partial, token=token)
        progress[mode] = f'partial_{count}'
        save_progress()
        if count == 1:
            api.call('POST', path + '/trustee', partial, token=token, expected=409)
            api.call('POST', path, 'ReleaseTally', match=True, expected=500)
            assert api.call('GET', path)['state'] == 'EncryptedTally'
            assert api.call('GET', path + '/roots').get('result') is None
    api.call('POST', path, 'ReleaseTally', match=True)
    assert api.call('GET', path)['state'] == 'Tallied'
    progress[mode] = 'tallied'
    save_progress()
    roots = api.call('GET', path + '/roots')
    result = api.call('GET', path + '/objects/' + roots['result'])
    observed = [int(value) for value in result['result'][0]]
    expected = [5, 5] if mode == 'revote' else [6, 4]
    assert observed == expected and sum(observed) == 10
    archive = collect(mode, election, public / 'final')
    assert b'@ejemplo.test' not in archive.read_bytes()
    verification = verify(archive.parent)
    assert verification['exit_code'] == 0 and 'all checks passed' in verification['stderr']
    assert 'no result to check' not in verification['stderr']

    # Alter a result payload byte, preserving its TAR structure and referenced name.
    tampered_dir = public / 'tampered'
    tampered_dir.mkdir(exist_ok=True)
    data = bytearray(archive.read_bytes())
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        member = next(m for m in tar.getmembers() if roots['result'] in m.name and m.isfile())
        payload = tar.extractfile(member).read()
        marker = payload.index(b'"result"')
        position = next(i for i in range(marker + len(b'"result"'), len(payload)) if payload[i:i+1] in b'0123456789')
        data[member.offset_data + position] = ord('9') if payload[position] != ord('9') else ord('8')
    (tampered_dir / archive.name).write_bytes(data)
    tamper_verification = verify(tampered_dir)
    assert tamper_verification['exit_code'] != 0
    prefix_verification = verify(public / 'before-tally')
    assert prefix_verification['exit_code'] == 0 and 'no result to check' in prefix_verification['stderr']
    active = api.call('GET', path + '/ballots')
    original = ui[f'{mode}-0-initial']['result']['hash']
    assert (original in active) == (mode == 'single')
    reports['elections'][mode] = {
        'uuid': election['uuid'], 'state': 'Tallied', 'enabled_synthetic_units': 10, 'active_ballots': len(active),
        'result': observed, 'expected': expected, 'browser_initial_votes': 10,
        'browser_revote': ui[f'{mode}-0-revote']['result']['kind'],
        'api_revote': api_votes[mode]['final']['kind'],
        'rejection_error': api_votes[mode]['final'].get('error'),
        'active_ballot_hashes_hex_unlinked': sorted(active),
        'trackers_base64_unlinked': sorted(base64.b64encode(bytes.fromhex(h)).decode().rstrip('=') for h in active),
        'restart_preserved_ballots_and_event_head': True, 'old_admin_token_after_restart_http': 401,
        'obsolete_if_match_http': 412, 'duplicate_partial_decryption_http': 409,
        'one_external_share_release_http': 500, 'one_share_did_not_publish': True,
        'external_threshold': '2/3', 'contributing_external_indices': chosen,
        'mandatory_server_key': True,
        'final_event': api.call('GET', path + '/last-event'), 'result_object_hash': roots['result'],
        'public_archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'public_archive_bytes': archive.stat().st_size,
        'verification_network': 'none', 'verification_mount': 'public archive only, readonly',
        'verification': verification, 'tamper_test': tamper_verification,
        'valid_prefix_without_result': prefix_verification,
        'public_archive_has_synthetic_email_strings': False,
    }
    progress[mode] = 'complete'
    save_progress()
    print(json.dumps({'mode': mode, 'state': 'Tallied', 'result': observed, 'verification_exit': verification['exit_code'], 'tamper_exit': tamper_verification['exit_code']}), flush=True)

if __name__ == '__main__':
    for mode, election in lab.STATE['elections'].items():
        tally(mode, election)
    reports['recorded_at_utc'] = datetime.now(timezone.utc).isoformat()
    reports['limitations'] = ['Same host and operator: custodial separation is simulated', 'Manual external credential generation tested; new operator/server protocol not exercised', 'Verifier is a separate networkless container, not an independent human or physical machine', 'Complete failure matrix and binding-election readiness are not certified']
    lab.STATE['phase'] = 'both_tallied_and_verified'
    lab.save()
    save_progress()
