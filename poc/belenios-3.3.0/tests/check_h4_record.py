"""Functional H4 record checks against the real verifier and completed family election."""
import copy
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'adapter'))
from lab_adapter import AdapterError, LabAdapter, DOCS
from technical_record import create_record, render_markdown
from family_registry import FamilyRegistry, RegistryError

report = json.loads((DOCS / 'h4-resultados.json').read_text())
adapter = LabAdapter('http://127.0.0.1:18002')
record = create_record(adapter, report)
assert record['tally']['counted_ballots'] == record['universe']['enabled_units'] == 8
assert record['universe']['synthetic_people'] == 10
assert record['tally']['participation'] == 1.0
assert [row['votes'] for row in record['tally']['options']] == [4, 4]
assert record['tally']['blank']['value'] is None and record['tally']['null']['value'] is None
assert record['signatures'] == [] and record['quorum']['assessed'] is False
checks = [{'check': 'record_counts_and_unapproved_fields_match_verified_family_election', 'passed': True}]
wrong_head = copy.deepcopy(report)
wrong_head['elections']['single']['final_event']['hash'] = '0' * 64
try:
    create_record(adapter, wrong_head)
except AdapterError:
    checks.append({'check': 'unanchored_record_rejected', 'passed': True})
else:
    raise AssertionError('An unanchored record was produced')
wrong_universe = copy.deepcopy(report)
wrong_universe['family_summary']['enabled_family_units'] = 10
try:
    create_record(adapter, wrong_universe)
except AdapterError:
    checks.append({'check': 'person_count_cannot_replace_family_denominator', 'passed': True})
else:
    raise AssertionError('Wrong family denominator was accepted')
try:
    FamilyRegistry([{'id': 'fam-01', 'members': ['rep01a@ejemplo.test']}, {'id': 'fam-02', 'members': ['rep01a@ejemplo.test']}])
except RegistryError:
    checks.append({'check': 'duplicate_representative_across_units_rejected', 'passed': True})
else:
    raise AssertionError('One representative was assigned twice')
(DOCS / 'h4-acta.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(DOCS / 'h4-acta.md').write_text(render_markdown(record), encoding='utf-8')
(DOCS / 'h4-acta-pruebas.json').write_text(json.dumps({'checks': checks}, indent=2) + '\n')
print(json.dumps({'H4_record': 'PASS', 'checks': len(checks), 'counted_family_units': 8, 'legally_valid': False}))
