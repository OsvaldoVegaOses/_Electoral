"""Pilot transport must reject incomplete/misbound external verification replies."""
import hashlib
import httpx
from pydantic import SecretStr
import pytest
from app.config import settings
from app.belenios.client import COMMIT, ProviderError
from app.belenios.verification import public_archive


@pytest.mark.parametrize("failure", [None,"missing_commit","wrong_image","missing_final","wrong_digest","empty"])
def test_pilot_requires_bound_complete_verifier_reply(monkeypatch, failure):
    monkeypatch.setattr(settings,"BELENIOS_MODE","pilot")
    monkeypatch.setattr(settings,"BELENIOS_VERIFIER_URL","https://verifier.example.invalid")
    monkeypatch.setattr(settings,"BELENIOS_ALLOWED_HOSTS","verifier.example.invalid")
    monkeypatch.setattr(settings,"BELENIOS_VERIFIER_TOKEN",SecretStr("synthetic-" + "t"*32))
    monkeypatch.setattr(settings,"BELENIOS_VERIFIER_IMAGE","sha256:" + "a"*64)
    data=b"synthetic-public-archive"
    headers={"X-Belenios-Archive-SHA256":hashlib.sha256(data).hexdigest(),
             "X-Belenios-Upstream-Commit":COMMIT,"X-Belenios-Tool-Image":settings.BELENIOS_VERIFIER_IMAGE,
             "X-Belenios-Final-Result":"verified"}
    if failure=="missing_commit":headers.pop("X-Belenios-Upstream-Commit")
    if failure=="wrong_image":headers["X-Belenios-Tool-Image"]="sha256:"+"b"*64
    if failure=="missing_final":headers.pop("X-Belenios-Final-Result")
    if failure=="wrong_digest":headers["X-Belenios-Archive-SHA256"]="0"*64
    if failure=="empty":data=b""
    def provider(request):
        assert str(request.url)=="https://verifier.example.invalid/verify"
        assert request.headers["Authorization"].startswith("Bearer synthetic-")
        assert b"R2" in request.content and b"CvnVFmybmHMb19" in request.content
        return httpx.Response(200,content=data,headers=headers)
    original=httpx.Client
    monkeypatch.setattr(httpx,"Client",lambda **kwargs:original(transport=httpx.MockTransport(provider),**kwargs))
    if failure is None:assert public_archive("R2","CvnVFmybmHMb19")==data
    else:
        with pytest.raises(ProviderError):public_archive("R2","CvnVFmybmHMb19")
