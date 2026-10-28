"""Functional contract checks against the live local laboratory and real verifier."""
import copy
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'adapter'))
from lab_adapter import AdapterError, DOCS, ROOT, LabAdapter

anchors = json.loads((DOCS / 'h2-resultados.json').read_text())
checks = []
exports = {}
for mode, port in [('revote', 18001), ('single', 18002)]:
    adapter = LabAdapter(f'http://127.0.0.1:{port}')
    anchor = anchors['elections'][mode]
    evidence = adapter.verified_evidence('poc-h3-' + mode, anchor['uuid'], anchor)
    assert evidence['counts'] == anchor['expected'] and evidence['counted_ballots'] == 10
    exports[mode] = evidence
    checks.append({'check': mode + '_verified_export', 'passed': True})
    wrong = copy.deepcopy(anchor)
    wrong['final_event']['hash'] = '0' * 64
    try:
        adapter.verified_evidence('poc-negative-' + mode, anchor['uuid'], wrong)
    except AdapterError:
        checks.append({'check': mode + '_wrong_anchor_rejected', 'passed': True})
    else:
        raise AssertionError('Incorrect final anchor accepted')

adapter = LabAdapter('http://127.0.0.1:18001')
mapping_file = ROOT / '.runtime/adapter/poc-h3-contract/mapping.json'
if mapping_file.exists():
    mapping = json.loads(mapping_file.read_text())
    assert mapping['phase'] == 'draft_with_10_synthetic_units'
    adapter.token = json.loads(adapter.call('POST', 'login/demo', {'username': 'poc-admin'}))['token']
    assert len(json.loads(adapter.call('GET', 'elections/' + mapping['belenios_uuid'] + '/draft/voters'))) == 10
else:
    mapping = adapter.provision_synthetic('poc-h3-contract')
assert mapping['enabled_units'] == 10
checks.append({'check': 'create_edit_and_voter_readback_with_if_match', 'passed': True})
try:
    adapter.provision_synthetic('poc-h3-contract')
except AdapterError:
    checks.append({'check': 'repeated_creation_blocked_by_mapping_checkpoint', 'passed': True})
else:
    raise AssertionError('Repeated creation was not blocked')
try:
    adapter.verified_evidence('poc-negative-draft', mapping['belenios_uuid'], anchors['elections']['revote'])
except AdapterError:
    checks.append({'check': 'unfinished_election_rejected', 'passed': True})
else:
    raise AssertionError('Draft accepted as verified final result')
try:
    LabAdapter('https://vote.belenios.org')
except AdapterError:
    checks.append({'check': 'non_laboratory_destination_rejected', 'passed': True})
else:
    raise AssertionError('External destination accepted')
(DOCS / 'h3-resultados.json').write_text(json.dumps({'milestone': 'H3', 'checks': checks, 'exports': exports, 'mapping': mapping}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'H3': 'PASS', 'functional_checks': len(checks), 'scope': 'local experimental adapter only'}))
