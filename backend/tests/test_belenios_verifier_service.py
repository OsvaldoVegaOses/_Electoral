"""Boundary tests use synthetic tool results; actual crypto is exercised separately."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import threading
import time

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.belenios_verifier.common import (COMMIT, VerificationFailure, archive_digest,
                                              atomic_json, provider_url, run_bounded)
from services.belenios_verifier.gateway import Gateway, Settings, create_server
from services.belenios_verifier.worker import process_job

UUID = "CvnVFmybmHMb19"
IMAGE = "sha256:" + "a" * 64
TOKEN = "synthetic-service-" + "x" * 32


def archive(entries=None):
    output = io.BytesIO()
    if entries is None:
        election=json.dumps({"uuid":UUID,"questions":[]}).encode()
        election_hash=hashlib.sha256(election).hexdigest()
        setup=json.dumps({"election":election_hash}).encode()
        setup_hash=hashlib.sha256(setup).hexdigest()
        event=json.dumps({"type":"Setup","height":0,"payload":setup_hash}).encode()
        entries=[("BELENIOS",b'{"version":1,"timestamp":"0"}'),
                 (election_hash+".data.json",election),(setup_hash+".data.json",setup),
                 (hashlib.sha256(event).hexdigest()+".event.json",event)]
    with tarfile.open(fileobj=output, mode="w") as bundle:
        for name, data in entries:
            member = tarfile.TarInfo(name); member.size = len(data)
            bundle.addfile(member, io.BytesIO(data))
    return output.getvalue()


@pytest.fixture
def config(tmp_path):
    inbox, outbox = tmp_path / "inbox", tmp_path / "outbox"
    inbox.mkdir(); outbox.mkdir()
    return Settings(inbox, outbox, TOKEN, {"R2": "https://urna.example.invalid"}, IMAGE, wait_seconds=1)


def job(config, data=None, digest=None):
    job_id = "f" * 32
    directory = config.inbox / job_id; directory.mkdir()
    data = data or archive()
    (directory / "archive.bel").write_bytes(data)
    atomic_json(directory / "request.json", {"policy": "R2", "uuid": UUID,
                "archive_sha256": digest or hashlib.sha256(data).hexdigest()})
    return job_id


def synthetic_runner(command, **kwargs):
    if command[-1] == "--version": return 0, b"3.3.0\n", b""
    return 0, b"", b"all checks passed\n"


@pytest.mark.parametrize("url", ["http://urna.example", "https://user@urna.example", "https://urna.example:8443",
                                     "https://urna.example/?token=x", "https://urna.example/#a",
                                     "https://urna.example/%2e%2e", "https://urna.example/../admin"])
def test_untrusted_operator_destinations_rejected(url):
    with pytest.raises(VerificationFailure): provider_url(url)


@pytest.mark.parametrize("name", ["../outside", "/outside", "a/../../outside", "C:secret", "a\\secret"])
def test_archive_paths_cannot_escape(name):
    with pytest.raises(VerificationFailure): archive_digest(archive([("BELENIOS", b"x"), (name, b"x")]))


def test_archive_rejects_links_and_duplicates():
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as bundle:
        link = tarfile.TarInfo("BELENIOS"); link.type = tarfile.SYMTYPE; link.linkname = "/private/key"
        bundle.addfile(link)
    with pytest.raises(VerificationFailure): archive_digest(output.getvalue())
    with pytest.raises(VerificationFailure): archive_digest(archive([("BELENIOS", b"a"), ("BELENIOS", b"b")]))


def test_valid_archive_for_another_election_cannot_be_replayed():
    with pytest.raises(VerificationFailure, match="election_mismatch"):
        archive_digest(archive(), "FvmMAXJvurGXN9")


def test_worker_rejects_content_digest_change_before_running_tool(config):
    identifier = job(config, digest="0" * 64)
    def forbidden(*args, **kwargs): pytest.fail("Tool ran before archive binding was checked")
    process_job(config.inbox, config.outbox, identifier, IMAGE, runner=forbidden)
    assert json.loads((config.outbox / (identifier + ".json")).read_text())["status"] == "rejected"


@pytest.mark.parametrize("code,diagnostic", [(0, b"all checks passed\nno result to check"),
                                           (124, b"all checks passed"), (0, b"prefix validated")])
def test_worker_requires_complete_success_not_a_valid_prefix(config, code, diagnostic):
    identifier = job(config)
    def runner(command, **kwargs):
        return (0, b"3.3.0", b"") if command[-1] == "--version" else (code, b"", diagnostic)
    process_job(config.inbox, config.outbox, identifier, IMAGE, runner=runner)
    result = json.loads((config.outbox / (identifier + ".json")).read_text())
    assert result["status"] == "rejected" and "diagnostic" not in result


def test_completed_job_is_bound_and_is_not_run_twice(config):
    identifier = job(config)
    assert process_job(config.inbox, config.outbox, identifier, IMAGE, runner=synthetic_runner)
    assert not process_job(config.inbox, config.outbox, identifier, IMAGE, runner=synthetic_runner)
    result = json.loads((config.outbox / (identifier + ".json")).read_text())
    assert result["status"] == "verified" and result["final_result_checked"] is True
    assert result["uuid"] == UUID and result["tool_image"] == IMAGE


def test_worker_claim_survives_interrupted_attempt(config):
    identifier = job(config)
    (config.outbox / (identifier + ".claim")).write_text("")
    assert not process_job(config.inbox, config.outbox, identifier, IMAGE, runner=synthetic_runner)


def test_gateway_timeout_retains_intent_and_rejects_another_job(config):
    gateway = Gateway(config, lambda *a: archive())
    with pytest.raises(VerificationFailure, match="worker_timeout"):
        gateway.verify({"policy": "R2", "uuid": UUID})
    with pytest.raises(VerificationFailure, match="busy_or_pending"):
        gateway.verify({"policy": "R2", "uuid": UUID})


def complete_pending(config, mutate=None):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        jobs = list(config.inbox.glob("*/request.json"))
        if jobs:
            identifier = jobs[0].parent.name
            staged = config.outbox / "worker-private"; staged.mkdir()
            process_job(config.inbox, staged, identifier, IMAGE, runner=synthetic_runner)
            path = staged / (identifier + ".json")
            data = json.loads(path.read_text())
            if mutate:
                mutate(data)
            atomic_json(config.outbox / (identifier + ".json"), data)
            return
        time.sleep(0.01)


@pytest.mark.parametrize("field", ["job_id", "uuid", "policy", "archive_sha256", "tool_image", "upstream_commit", "final_result_checked"])
def test_gateway_never_accepts_a_mismatched_worker_reply(config, field):
    thread = threading.Thread(target=complete_pending, args=(config, lambda r:r.update({field: "different"})))
    thread.start()
    with pytest.raises(VerificationFailure, match="mismatched"):
        Gateway(config, lambda *a: archive()).verify({"policy": "R2", "uuid": UUID})
    thread.join()


def test_http_authentication_and_public_archive_response(config):
    calls = []
    def collector(*args): calls.append(args); return archive()
    server = create_server(("127.0.0.1", 0), config, collector)
    thread = threading.Thread(target=server.serve_forever); thread.start()
    try:
        url = "http://127.0.0.1:" + str(server.server_port)
        with httpx.Client(base_url=url, trust_env=False) as client:
            assert client.post("/verify", json={"policy":"R2","uuid":UUID}).status_code == 401
            assert calls == []
            headers = {"Authorization":"Bearer " + TOKEN}
            assert client.post("/verify", json={"policy":"R2","uuid":UUID,"url":"https://attacker.invalid"}, headers=headers).status_code == 400
            worker = threading.Thread(target=complete_pending, args=(config,)); worker.start()
            response = client.post("/verify", json={"policy":"R2","uuid":UUID}, headers=headers)
            worker.join()
            assert response.status_code == 200 and response.content == archive()
            assert response.headers["X-Belenios-Upstream-Commit"] == COMMIT
            assert response.headers["X-Belenios-Archive-SHA256"] == hashlib.sha256(response.content).hexdigest()
            assert response.headers["Cache-Control"] == "no-store"
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_native_process_is_bounded_without_leaking_output(tmp_path):
    with pytest.raises(VerificationFailure, match="tool_timeout"):
        run_bounded([sys.executable, "-c", "import time; time.sleep(3)"], cwd=tmp_path, timeout=0.1, stdout_limit=1024)
    with pytest.raises(VerificationFailure, match="tool_output_limit"):
        run_bounded([sys.executable, "-c", "print('x'*4000)"], cwd=tmp_path, timeout=2, stdout_limit=128)
