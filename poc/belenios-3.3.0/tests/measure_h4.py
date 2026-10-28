"""Read-only measurements of this laboratory; no cloud prices or capacity estimates."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parents[1] / 'doc/poc-belenios/evidencias'
def docker(*args):
    return subprocess.check_output(['docker', *args], stderr=subprocess.PIPE)

services = ('revote', 'single', 'ingress-a', 'ingress-b')
containers = ['theogen-belenios33-poc-' + service + '-1' for service in services]
samples = []
for _ in range(3):
    started = datetime.now(timezone.utc).isoformat()
    lines = docker('stats', '--no-stream', '--format', '{{json .}}', *containers).decode().splitlines()
    samples.append({'at_utc': started, 'containers': [json.loads(line) for line in lines]})
    time.sleep(1)
volumes = {}
for service in ('revote', 'single'):
    volumes[service] = int(docker('exec', 'theogen-belenios33-poc-' + service + '-1', 'du', '-sb', '/home/belenios/poc-data').split()[0])
image_id = json.loads((DOCS / 'h1-resultados.json').read_text())['image_id']
image = json.loads(docker('image', 'inspect', image_id))[0]
networks = {suffix: json.loads(docker('network', 'inspect', 'theogen-belenios33-poc_ballot-' + suffix))[0]['Internal'] for suffix in ('a', 'b')}
data = {'measured_at_utc': datetime.now(timezone.utc).isoformat(), 'samples': samples, 'volume_apparent_bytes_all_synthetic_elections': volumes,
        'shared_image_id': image_id, 'shared_image_size_bytes': image['Size'], 'internal_ballot_networks': networks,
        'limits_per_urn': {'memory_bytes': 768 * 1024 * 1024, 'cpu': 2}, 'limits_per_ingress': {'memory_bytes': 128 * 1024 * 1024},
        'scope': 'Three idle/light laboratory snapshots, one shared image and current volumes; not a load benchmark or hosting quote',
        'not_measured': ['Human assistance/trustee work hours', 'Real email/SMS cost', 'Independent administrative domains', 'Production RPO/RTO and peak capacity', 'Host-wide DNS/SMTP capture']}
(DOCS / 'h4-recursos.json').write_text(json.dumps(data, indent=2) + '\n')
print(json.dumps({'H4_resource_samples': len(samples), 'urn_volumes_bytes': volumes, 'shared_image_bytes': image['Size']}))
