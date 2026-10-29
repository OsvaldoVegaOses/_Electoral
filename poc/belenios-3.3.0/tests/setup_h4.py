"""Create one H4 family election; never rerun an uncertain existing preparation."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'adapter'))
from family_registry import FamilyRegistry, RegistryError
import setup_h2 as lab

lab.PRIVATE = lab.ROOT / '.runtime/private/h4'
lab.STATE_PATH = lab.PRIVATE / 'h4-state.json'
lab.TRACE_PATH = lab.ROOT / '.runtime/h4-api-trace.json'
if lab.STATE_PATH.exists():
    raise SystemExit('Existing H4 intent/state: reconcile manually; no automatic repeated creation')
lab.STATE = {'phase': 'h4_creation_intent', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'elections': {}}
lab.TRACE = []
lab.save()
started = time.monotonic()
families = [{'id': f'fam-{i:02d}', 'members': [f'rep{i:02d}a@ejemplo.test', f'rep{i:02d}b@ejemplo.test'] if i <= 2 else [f'rep{i:02d}@ejemplo.test']} for i in range(1, 9)]
registry = FamilyRegistry(families)
checks = []
try:
    registry.freeze()
except RegistryError:
    checks.append({'check': 'unresolved_representatives_block_freeze', 'passed': True})
else:
    raise AssertionError('Unresolved registry accepted')
for index, family in enumerate(families, 1):
    registry.select(family['id'], family['members'][0], f'poc-decision-{index}')
voters = registry.freeze()
assert len(voters) == len(set(voters)) == 8
for person in ('rep01b@ejemplo.test', 'rep02b@ejemplo.test'):
    try:
        registry.identity_for(person)
    except RegistryError:
        checks.append({'check': 'alternate_representative_has_no_second_identity', 'passed': True})
    else:
        raise AssertionError('Alternate representative received another identity')
try:
    registry.select('fam-01', 'rep01b@ejemplo.test', 'poc-decision-9')
except RegistryError:
    checks.append({'check': 'late_representative_change_blocked', 'passed': True})
else:
    raise AssertionError('Frozen representative changed')
assert registry.identity_for('rep01a@ejemplo.test') == voters[0]
(lab.PRIVATE / 'family-registry.json').write_text(json.dumps({'rows': registry.rows, 'frozen': registry.frozen}, indent=2))
lab.setup('single', 18002, voters=voters, title='H4 familiar: ocho unidades sinteticas')
election = lab.STATE['elections']['single']
credentials = json.loads(Path(election['private_credentials_file']).read_text())
assert set(credentials) == set(voters) and len(credentials) == 8
api = lab.API(18002)
api.token = election['admin_token']
assert api.call('GET', f"elections/{election['uuid']}/voters") == voters
checks.append({'check': 'exactly_eight_credentials_and_api_voters_for_ten_people', 'passed': True})
lab.STATE.update(phase='h4_open_no_ballots', family_summary=registry.summary(), family_checks=checks,
                 setup_elapsed_seconds=round(time.monotonic() - started, 3))
lab.save()
print(json.dumps({'H4_setup': 'PASS', **registry.summary(), 'checks': len(checks)}))
