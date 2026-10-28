"""Controlled failure checks: no network, containers, credentials or new elections."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'adapter'))
import lab_adapter as lab


class LostCreationResponse(lab.LabAdapter):
    creations = 0

    def configuration(self):
        return {}

    def call(self, method, route, *args, **kwargs):
        if route == 'login/demo':
            return b'{"token":"synthetic-not-a-real-capability"}'
        if route == 'account':
            return b'{"id":1}'
        if method == 'POST' and route == 'elections':
            self.creations += 1
            raise lab.UnknownMutationOutcome('Simulated lost response after server accepted creation')
        raise AssertionError('Unexpected call')


with tempfile.TemporaryDirectory(prefix='belenios-adapter-failure-') as directory:
    with patch.object(lab, 'ROOT', Path(directory)):
        adapter = LostCreationResponse('http://127.0.0.1:18001')
        try:
            adapter.provision_synthetic('poc-lost-response')
        except lab.UnknownMutationOutcome:
            pass
        else:
            raise AssertionError('Lost response was not reported')
        checkpoint = Path(directory) / '.runtime/adapter/poc-lost-response/mapping.json'
        assert json.loads(checkpoint.read_text())['phase'] == 'creation_intent_requires_reconciliation'
        try:
            adapter.provision_synthetic('poc-lost-response')
        except lab.AdapterError:
            pass
        else:
            raise AssertionError('Unknown creation was retried')
        assert adapter.creations == 1

adapter = lab.LabAdapter('http://127.0.0.1:18001')
with patch.object(adapter.opener, 'open', side_effect=http.client.IncompleteRead(b'', 1)) as opened:
    try:
        adapter.call('POST', 'elections', {})
    except lab.UnknownMutationOutcome:
        pass
    else:
        raise AssertionError('Incomplete mutation response was not classified as unknown')
    assert opened.call_count == 1

print(json.dumps({'H3_controlled_failures': 'PASS', 'checks': 2, 'new_elections': 0}))
