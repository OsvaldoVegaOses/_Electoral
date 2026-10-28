"""Read-only, bounded checks; never publish email, credentials or raw access logs."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parents[1] / 'doc/poc-belenios/evidencias'
def docker(*args):
    return subprocess.check_output(['docker', *args], stderr=subprocess.PIPE)

expected_sender = (ROOT / 'scripts/sendmail-fake.sh').read_bytes().replace(b'\r\n', b'\n')
checks = []
logs = []
for mode, port in (('revote', 18001), ('single', 18002)):
    container = 'theogen-belenios33-poc-' + mode + '-1'
    inspected = json.loads(docker('inspect', container))[0]
    sender = next(value.split('=', 1)[1] for value in inspected['Config']['Env'] if value.startswith('BELENIOS_SENDMAIL='))
    assert sender == '/opt/poc/sendmail-fake.sh'
    live_sender = docker('exec', container, 'cat', sender)
    assert live_sender == expected_sender
    checks.append({'check': mode + '_live_sender_is_private_file_sink', 'passed': True, 'sender_sha256': hashlib.sha256(live_sender).hexdigest()})
    mode_bits = docker('exec', container, 'stat', '-c', '%a', '/home/belenios/poc-data/private/mail.txt').decode().strip()
    assert mode_bits == '600'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        response = opener.open(f'http://127.0.0.1:{port}/static/mail.txt')
        status = response.status
        response.close()
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
    assert status in (400, 404)
    checks.append({'check': mode + '_mail_private_and_not_public', 'passed': True, 'file_mode': mode_bits, 'public_mail_http': status})
    base = '/home/belenios/poc-data/log'
    paths = docker('exec', container, 'find', base, '-maxdepth', '2', '-type', 'f').decode().splitlines()
    for path in paths:
        assert PurePosixPath(path).is_relative_to(base)
        sample = docker('exec', container, 'tail', '-c', '1048576', path)
        size = int(docker('exec', container, 'stat', '-c', '%s', path))
        logs.append({'service': mode, 'log_file': PurePosixPath(path).name, 'total_bytes': size, 'sample_bytes': len(sample),
                     'synthetic_address_marker_present': b'@ejemplo.test' in sample,
                     'auth_state_query_markers': sample.count(b'?state=') + sample.count(b'&state='),
                     'token_query_markers': sample.count(b'?token=') + sample.count(b'&token='),
                     'raw_log_published': False})
browser = json.loads((DOCS / 'h4-navegador.json').read_text())
assert browser['request_allowlist']['observed_hosts'] == ['127.0.0.1'] and browser['request_allowlist']['blocked'] == 0
checks.append({'check': 'observed_family_browser_requests_stayed_on_loopback', 'passed': True, 'requests': browser['request_allowlist']['allowed']})
(DOCS / 'h4-privacidad.json').write_text(json.dumps({'checks': checks, 'bounded_log_metadata_only': logs,
    'limitations': ['No packet-level or host-wide DNS/SMTP capture', 'Cookies observed only at end of browser contexts; not an authentication-cookie audit',
                    'Access logs can correlate IP/time/authentication state even without a plaintext address; retention and independent custody remain unresolved',
                    'Fake mail contains sensitive laboratory OTPs and remains private; delivery to real representatives was not implemented']}, indent=2) + '\n')
print(json.dumps({'H4_privacy_bounded_checks': 'PASS', 'checks': len(checks), 'log_files_sampled': len(logs), 'raw_logs_published': False}))
