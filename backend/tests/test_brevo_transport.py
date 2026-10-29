import json
from uuid import uuid4

import httpx
from pydantic import SecretStr
import pytest

from app.brevo import send_credential, DeliveryRejected, DeliveryUnknown
from app.config import settings


@pytest.fixture(autouse=True)
def brevo_config(monkeypatch):
    monkeypatch.setattr(settings, "BREVO_API_KEY", SecretStr("synthetic-brevo-test-key"))
    monkeypatch.setattr(settings, "BREVO_SENDER_EMAIL", "sender@example.invalid")
    monkeypatch.setattr(settings, "BREVO_DELIVERY_ENABLED", True)
    monkeypatch.setattr(settings, "PUBLIC_VOTING_URL", "https://example.invalid/votar")


def test_brevo_acceptance_uses_opaque_operation_and_no_token_in_url(caplog):
    operation = str(uuid4())
    def provider(request):
        assert str(request.url) == "https://api.brevo.com/v3/smtp/email"
        assert request.headers["api-key"] == "synthetic-brevo-test-key"
        payload = json.loads(request.content)
        assert payload["headers"]["idempotencyKey"] == operation
        assert "synthetic-vote-token" in payload["textContent"]
        assert "?token=" not in payload["textContent"]
        return httpx.Response(201, json={"messageId": "synthetic-message-id"})
    result = send_credential("recipient@example.invalid", "synthetic-vote-token", operation,
                             transport=httpx.MockTransport(provider))
    assert result.status == "accepted"
    assert "synthetic-vote-token" not in caplog.text
    assert "synthetic-brevo-test-key" not in caplog.text


@pytest.mark.parametrize("code", [401, 403, 429])
def test_explicit_rejection_never_exposes_body_or_secret(code):
    with pytest.raises(DeliveryRejected) as error:
        send_credential("recipient@example.invalid", "synthetic-vote-token", str(uuid4()),
                        transport=httpx.MockTransport(lambda request: httpx.Response(code, json={"message": "synthetic-vote-token"})))
    assert "synthetic-vote-token" not in str(error.value)


@pytest.mark.parametrize("kind", ["timeout", "server-error", "duplicate", "missing-id"])
def test_indeterminate_send_is_not_retried(kind):
    calls = []
    def provider(request):
        calls.append(request)
        if kind == "timeout":
            raise httpx.ReadTimeout("sensitive-data-must-not-propagate")
        if kind == "server-error":
            return httpx.Response(503)
        if kind == "duplicate":
            return httpx.Response(400, json={"code": "duplicate_parameter"})
        return httpx.Response(201, json={})
    with pytest.raises(DeliveryUnknown):
        send_credential("recipient@example.invalid", "synthetic-vote-token", str(uuid4()),
                        transport=httpx.MockTransport(provider))
    assert len(calls) == 1


def test_disabled_channel_never_contacts_provider(monkeypatch):
    monkeypatch.setattr(settings, "BREVO_DELIVERY_ENABLED", False)
    def provider(request):
        pytest.fail("Disabled channel performed a network request")
    with pytest.raises(DeliveryRejected):
        send_credential("recipient@example.invalid", "synthetic-vote-token", str(uuid4()),
                        transport=httpx.MockTransport(provider))
