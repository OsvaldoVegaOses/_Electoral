"""Functional H1 checks on the two local synthetic laboratory instances."""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'theogen-belenios-poc:3.3.0-337887bd'
COMPOSE = ['docker', 'compose', '-f', str(ROOT / 'docker-compose.poc.yml')]
OBSERVATIONS = []
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def docker(*command, data=None):
    result = subprocess.run(['docker', *command], input=data, capture_output=True)
    if result.returncode:
        raise RuntimeError('Docker operation failed: ' + ' '.join(command[:3]) + '; ' + result.stderr.decode(errors='replace')[:800])
    return result.stdout

def compose(*command):
    return subprocess.check_output(COMPOSE + list(command), stderr=subprocess.STDOUT)

def request(port, method, path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    payload = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=payload, headers=headers, method=method)
    try:
        with opener.open(req, timeout=2) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()

def record(label, condition, detail):
    OBSERVATIONS.append({'check': label, 'passed': bool(condition), 'observed': detail})
    if not condition:
        raise AssertionError(label)

def wait_ready(port):
    for _ in range(30):
        try:
            code, raw = request(port, 'GET', '/api/configuration')
            if code == 200:
                return json.loads(raw)
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(1)
    raise RuntimeError('Server did not become ready')

def main():
    started = time.monotonic()
    config = json.loads(compose('config', '--format', 'json'))
    for name, port in [('revote', 18001), ('single', 18002)]:
        ingress = 'ingress-a' if name == 'revote' else 'ingress-b'
        record(name + '_compose_loopback', all(p['host_ip'] == '127.0.0.1' for p in config['services'][ingress]['ports']), port)
        cid = compose('ps', '-q', name).decode().strip()
        if not cid:
            raise RuntimeError('Missing lab service ' + name)
        inspect = json.loads(docker('inspect', cid))[0]
        proxy_id = compose('ps', '-q', ingress).decode().strip()
        proxy = json.loads(docker('inspect', proxy_id))[0]
        bindings = proxy['NetworkSettings']['Ports']['8000/tcp']
        record(name + '_actual_loopback', bool(bindings) and all(p['HostIp'] == '127.0.0.1' for p in bindings), bindings)
        record(name + '_urn_not_published', not inspect['HostConfig']['PortBindings'], 'Only fixed-destination ingress is published')
        networks = inspect['NetworkSettings']['Networks']
        for net in networks:
            info = json.loads(docker('network', 'inspect', net))[0]
            record(name + '_network_internal', info['Internal'], {'name': net, 'internal': info['Internal']})
        cfg = wait_ready(port)
        record(name + '_version', cfg['belenios_version'] == '3.3.0' and cfg['api_version'] == 6,
               {key: cfg[key] for key in ('belenios_version', 'belenios_build', 'api_version')})
        for route, expected in [('/api/elections', {401}), ('/api/no-such-route', {404}), ('/static/mail.txt', {400, 404})]:
            code, _ = request(port, 'GET', route)
            record(name + '_' + route, code in expected, {'http': code})
        docker('exec', cid, 'sh', '-c', 'test ! -e _run/usr/share/belenios-server/static/mail.txt')
        record(name + '_no_public_mail_file', True, 'The fake mail sink is outside the served static tree')
        raw_config = docker('exec', cid, 'cat', '/tmp/ocsigenserver-poc.conf.in').decode()
        record(name + '_revote_configuration', ('<deny-revote/>' in raw_config) == (name == 'single'), {'deny_revote': name == 'single'})
        routes = docker('exec', cid, 'cat', '/proc/net/route').decode().splitlines()[1:]
        default_route = any(line.split()[1] == '00000000' for line in routes)
        record(name + '_no_default_route', not default_route, {'default_route': default_route})
        probe = docker('exec', cid, 'sh', '-c', 'wget --no-proxy --timeout=2 --tries=1 -q -O /dev/null https://198.51.100.1; code=$?; test "$code" -eq 4')
        record(name + '_outbound_negative_probe', probe == b'', 'TEST-NET-2 destination unreachable; no election data transmitted')

    # State persistence with a laboratory marker; no voter data in this check.
    cid = compose('ps', '-q', 'single').decode().strip()
    marker = b'h1-synthetic-persistence-marker\n'
    docker('exec', '-i', cid, 'sh', '-c', 'cat > /home/belenios/poc-data/private/h1-marker', data=marker)
    compose('restart', 'single')
    wait_ready(18002)
    observed = docker('exec', cid, 'cat', '/home/belenios/poc-data/private/h1-marker')
    record('restart_persistence', observed == marker, {'marker_sha256': hashlib.sha256(observed).hexdigest()})
    # A stopped service must be unresponsive. Restore a complete state backup into a new lab volume.
    compose('stop', 'single')
    try:
        code, _ = request(18002, 'GET', '/api/configuration')
    except (OSError, urllib.error.URLError):
        code = None
    record('stopped_service_unresponsive', code in (None, 502), {'http': code, 'meaning': 'Upstream unavailable: explicit 502 or bounded client timeout'})
    backup_dir = ROOT / '.runtime/private'
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / 'h1-single-backup.tar'
    volume = 'theogen-belenios33-poc_single-data'
    data = docker('run', '--rm', '--network', 'none', '--entrypoint', 'tar', '--mount', f'type=volume,src={volume},dst=/state,readonly', IMAGE, '-cpf', '-', '-C', '/state', '.')
    backup_path.write_bytes(data)
    restore_volume = 'theogen-belenios33-poc_h1-restore'
    docker('volume', 'create', restore_volume)
    docker('run', '--rm', '-i', '--network', 'none', '--user', '0', '--entrypoint', 'tar', '--mount', f'type=volume,src={restore_volume},dst=/restore', IMAGE, '-xpf', '-', '-C', '/restore', data=data)
    restored = docker('run', '--rm', '--network', 'none', '--entrypoint', 'cat', '--mount', f'type=volume,src={restore_volume},dst=/restore,readonly', IMAGE, '/restore/private/h1-marker')
    record('backup_restore_marker', restored == marker, {'backup_sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
    docker('run', '-d', '--name', 'theogen-belenios33-h1-restore', '--network', 'theogen-belenios33-poc_ballot-b',
           '--network-alias', 'single', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
           '--env', 'POC_PUBLIC_URL=http://127.0.0.1:18002', '--env', 'POC_DENY_REVOTE=true',
           '--mount', f'type=volume,src={restore_volume},dst=/home/belenios/poc-data', IMAGE)
    record('restored_server_ready', wait_ready(18002)['api_version'] == 6, 'Restored full volume starts with original version/configuration')
    docker('stop', 'theogen-belenios33-h1-restore')
    docker('rm', 'theogen-belenios33-h1-restore')
    docker('volume', 'rm', restore_volume)
    compose('start', 'single')
    wait_ready(18002)
    record('temporary_restore_removed', restore_volume not in docker('volume', 'ls', '-q').decode().splitlines(), 'Only H1 restore volume removed; original two volumes retained')
    stats = docker('stats', '--no-stream', '--format', '{{json .}}', *[compose('ps', '-q', s).decode().strip() for s in ('revote', 'single')]).decode().splitlines()
    image = json.loads(docker('image', 'inspect', IMAGE))[0]
    result = {'milestone': 'H1', 'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
              'upstream_commit': image['Config']['Labels']['org.opencontainers.image.revision'],
              'image_id': image['Id'], 'image_size_bytes': image['Size'],
              'elapsed_checks_seconds': round(time.monotonic() - started, 2),
              'checks': OBSERVATIONS, 'stats_single_sample': [json.loads(s) for s in stats],
              'limitations': ['Debug laboratory build, not production', 'Logical volume removal does not prove physical erasure', 'No election, independent authorities or egress packet capture proven by H1']}
    target = ROOT.parents[1] / 'doc/poc-belenios/evidencias/h1-resultados.json'
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'H1': 'PASS', 'checks': len(OBSERVATIONS), 'image_id': image['Id'], 'report': str(target)}))

if __name__ == '__main__':
    try:
        main()
    finally:
        compose('start', 'single')
