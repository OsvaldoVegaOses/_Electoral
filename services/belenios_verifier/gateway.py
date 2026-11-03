"""Authenticated archive collector; never runs the cryptographic verification job."""
from dataclasses import dataclass
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import ssl
import tempfile
import time
from uuid import uuid4

from .common import (COMMIT, TOOL, MAX_ARCHIVE, VerificationFailure, archive_digest,
                     atomic_json, identity, immutable_image, provider_url, read_regular, run_bounded)


@dataclass(frozen=True)
class Settings:
    inbox: Path
    outbox: Path
    token: str
    providers: dict
    tool_image: str
    wait_seconds: float = 35
    max_retained_jobs: int = 32

    def __post_init__(self):
        if len(self.token) < 32 or not self.token.isascii() or any(c.isspace() for c in self.token):
            raise VerificationFailure("invalid_service_token")
        if not self.providers or set(self.providers) - {"R1", "R2"}:
            raise VerificationFailure("invalid_profiles")
        for value in self.providers.values(): provider_url(value)
        immutable_image(self.tool_image)
        if not 0 < self.wait_seconds <= 40 or not 1 <= self.max_retained_jobs <= 32:
            raise VerificationFailure("invalid_limits")
        for directory in (self.inbox, self.outbox):
            if not directory.is_dir() or directory.is_symlink(): raise VerificationFailure("invalid_spool")


def collect(base, uuid):
    with tempfile.TemporaryDirectory(prefix="belenios-collect-") as directory:
        code, archive, _ = run_bounded([TOOL, "archive", "pull", "--url", provider_url(base) + "/", "--uuid", uuid],
                                      cwd=Path(directory), timeout=15, stdout_limit=MAX_ARCHIVE)
    if code: raise VerificationFailure("collection_failed")
    return archive


class Gateway:
    def __init__(self, settings, collector=collect):
        self.settings, self.collector = settings, collector

    def verify(self, request):
        if not isinstance(request, dict) or set(request) != {"policy", "uuid"}:
            raise VerificationFailure("invalid_request")
        policy, uuid = request["policy"], request["uuid"]
        identity(policy, uuid)
        config = self.settings
        if policy not in config.providers: raise VerificationFailure("unsupported_profile")
        lock = config.inbox / ".busy"
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise VerificationFailure("busy_or_pending_reconciliation") from None
        job_id = uuid4().hex
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"job_id": job_id, "policy": policy, "uuid": uuid, "started_at": time.time()}, stream)
            stream.flush(); os.fsync(stream.fileno())
        submitted, completed = False, False
        try:
            retained = sum(1 for path in config.inbox.iterdir() if path.is_dir())
            if retained >= config.max_retained_jobs: raise VerificationFailure("retention_capacity")
            archive = self.collector(config.providers[policy], uuid)
            digest = archive_digest(archive, uuid)
            directory = config.inbox / job_id
            directory.mkdir(mode=0o700)
            with (directory / "archive.bel").open("xb") as stream:
                stream.write(archive); stream.flush(); os.fsync(stream.fileno())
            atomic_json(directory / "request.json", {"policy": policy, "uuid": uuid, "archive_sha256": digest})
            submitted = True
            deadline = time.monotonic() + config.wait_seconds
            result_path = config.outbox / (job_id + ".json")
            while not result_path.exists():
                if time.monotonic() >= deadline: raise VerificationFailure("worker_timeout_requires_reconciliation")
                time.sleep(0.02)
            result = json.loads(read_regular(result_path, 8192))
            completed = True
            expected = {"job_id": job_id, "policy": policy, "uuid": uuid, "archive_sha256": digest,
                        "status": "verified", "upstream_commit": COMMIT, "tool_image": config.tool_image,
                        "verification_exit_code": 0, "final_result_checked": True}
            if (any(result.get(key) != value for key, value in expected.items())
                    or result.get("final_result_checked") is not True
                    or type(result.get("verification_exit_code")) is not int):
                raise VerificationFailure("worker_rejected_or_mismatched")
            # Recheck the exact bytes served, not only the collector's in-memory digest.
            served = read_regular(directory / "archive.bel", MAX_ARCHIVE)
            if archive_digest(served, uuid) != digest: raise VerificationFailure("archive_changed")
            return served, expected
        finally:
            # A lost/timed-out worker is not retried or silently replaced.
            if not submitted or completed: lock.unlink()


def create_server(address, settings, collector=collect):
    gateway = Gateway(settings, collector)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args): pass  # Never record Authorization or request contents.

        def reply(self, status, body, content_type="application/json", headers=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            for name, value in (headers or {}).items(): self.send_header(name, value)
            self.end_headers(); self.wfile.write(body); self.close_connection = True

        def do_GET(self):
            if self.path != "/health": return self.reply(404, b'{"error":"not_found"}')
            try:
                heartbeat = json.loads(read_regular(settings.outbox / "heartbeat.json", 1024))
                ready = heartbeat.get("upstream_commit") == COMMIT and 0 <= time.time() - heartbeat["observed_at"] < 10
            except (OSError, ValueError, KeyError, TypeError, VerificationFailure): ready = False
            self.reply(200 if ready else 503, json.dumps({"worker_available": ready}).encode())

        def do_POST(self):
            self.connection.settimeout(10)
            if self.path != "/verify": return self.reply(404, b'{"error":"not_found"}')
            expected = ("Bearer " + settings.token).encode()
            if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), expected):
                return self.reply(401, b'{"error":"unauthorized"}')
            try:
                length = int(self.headers.get("Content-Length", "-1"))
                if not 0 < length <= 1024 or self.headers.get("Transfer-Encoding"):
                    return self.reply(413, b'{"error":"request_size"}')
                request = json.loads(self.rfile.read(length))
                archive, result = gateway.verify(request)
                self.reply(200, archive, "application/octet-stream", {
                    "X-Belenios-Archive-SHA256": result["archive_sha256"],
                    "X-Belenios-Upstream-Commit": COMMIT,
                    "X-Belenios-Tool-Image": settings.tool_image,
                    "X-Belenios-Final-Result": "verified"})
            except VerificationFailure as error:
                status = 400 if str(error) in ("invalid_identity", "invalid_request", "unsupported_profile") else 503
                self.reply(status, json.dumps({"error": str(error)}).encode())
            except (ValueError, OSError, TypeError):
                self.reply(503, b'{"error":"verification_unavailable"}')

    server = ThreadingHTTPServer(address, Handler)
    server.daemon_threads = True
    return server


def main():
    config = Settings(Path(os.environ["VERIFIER_INBOX"]), Path(os.environ["VERIFIER_OUTBOX"]),
        read_regular(Path(os.environ["VERIFIER_TOKEN_FILE"]), 512).decode().strip(),
        json.loads(os.environ["VERIFIER_PROVIDERS"]), os.environ["VERIFIER_TOOL_IMAGE"])
    address = os.environ.get("VERIFIER_BIND", "127.0.0.1")
    server = create_server((address, int(os.environ.get("VERIFIER_PORT", "8443"))), config)
    certificate, key = os.environ.get("VERIFIER_TLS_CERT_FILE"), os.environ.get("VERIFIER_TLS_KEY_FILE")
    if certificate and key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certificate, key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    elif address not in ("127.0.0.1", "::1"):
        raise VerificationFailure("tls_required")
    server.serve_forever()


if __name__ == "__main__": main()
