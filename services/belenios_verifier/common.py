import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import subprocess
import tarfile
import tempfile
import time
from urllib.parse import urlsplit

COMMIT = "337887bd1862c7cd057080b530fd80941bfc3c69"
TOOL = "/home/belenios/belenios/_run/usr/bin/belenios-tool"
MAX_ARCHIVE = 8 * 1024 * 1024
MAX_OUTPUT = 64 * 1024


class VerificationFailure(Exception):
    """Fixed diagnostics only; no tool output, request body or secret."""


def identity(policy, uuid):
    if policy not in ("R1", "R2") or not isinstance(uuid, str) or not re.fullmatch(r"[A-Za-z0-9]{14}", uuid):
        raise VerificationFailure("invalid_identity")


def provider_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.query or parsed.fragment
            or "%" in parsed.path or "\\" in value
            or any(part in (".", "..") for part in parsed.path.split("/"))):
        raise VerificationFailure("invalid_provider")
    return value.rstrip("/")


def immutable_image(value):
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise VerificationFailure("immutable_tool_image_required")
    return value


def read_regular(path, limit):
    path = Path(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(descriptor, "rb") as stream:
        if path.is_symlink() or not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise VerificationFailure("non_regular_file")
        data = stream.read(limit + 1)
    if len(data) > limit: raise VerificationFailure("file_too_large")
    return data


def atomic_json(path, body):
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(body, stream, separators=(",", ":")); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


def archive_digest(data, expected_uuid=None):
    if not data or len(data) > MAX_ARCHIVE: raise VerificationFailure("archive_size")
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
            count, total, names = 0, 0, set()
            for member in archive:
                name = PurePosixPath(member.name)
                count += 1; total += member.size
                if (not member.isfile() or name.is_absolute() or ".." in name.parts
                        or "\\" in member.name or ":" in member.name or member.name in names
                        or len(member.name) > 180 or count > 20000 or total > 16 * 1024 * 1024):
                    raise VerificationFailure("unsafe_archive")
                names.add(member.name)
            if "BELENIOS" not in names: raise VerificationFailure("missing_archive_header")
            if expected_uuid is not None:
                # The BELENIOS header contains format/timestamp, not election identity.
                # Bind the UUID through the unique hashed Setup event and its payload.
                setups = []
                for member in archive.getmembers():
                    if not member.name.endswith(".event.json"): continue
                    raw = archive.extractfile(member).read()
                    if hashlib.sha256(raw).hexdigest() + ".event.json" != member.name:
                        raise VerificationFailure("event_hash_mismatch")
                    event = json.loads(raw)
                    if isinstance(event, dict) and event.get("type") == "Setup": setups.append(event)
                if len(setups) != 1 or setups[0].get("height") != 0:
                    raise VerificationFailure("invalid_setup")
                def object_json(digest):
                    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                        raise VerificationFailure("invalid_object_reference")
                    raw = archive.extractfile(digest + ".data.json").read()
                    if hashlib.sha256(raw).hexdigest() != digest:
                        raise VerificationFailure("object_hash_mismatch")
                    return json.loads(raw)
                setup = object_json(setups[0]["payload"])
                election = object_json(setup["election"])
                if not isinstance(election, dict) or election.get("uuid") != expected_uuid:
                    raise VerificationFailure("archive_election_mismatch")
    except (tarfile.TarError, ValueError, OSError, KeyError, TypeError, AttributeError):
        raise VerificationFailure("invalid_archive") from None
    return hashlib.sha256(data).hexdigest()


def run_bounded(command, *, cwd, timeout, stdout_limit):
    """Bound elapsed time/output; never inherit gateway tokens or private keys."""
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(cwd), "LANG": "C.UTF-8"},
            start_new_session=os.name != "nt")
        started = time.monotonic()
        while process.poll() is None:
            reason = None
            if time.monotonic() - started > timeout: reason = "tool_timeout"
            if os.fstat(stdout.fileno()).st_size > stdout_limit or os.fstat(stderr.fileno()).st_size > MAX_OUTPUT:
                reason = "tool_output_limit"
            if reason:
                if os.name == "nt": process.kill()
                else: os.killpg(process.pid, signal.SIGKILL)
                process.wait(); raise VerificationFailure(reason)
            time.sleep(0.02)
        stdout.seek(0); stderr.seek(0)
        output, diagnostic = stdout.read(stdout_limit + 1), stderr.read(MAX_OUTPUT + 1)
        if len(output) > stdout_limit or len(diagnostic) > MAX_OUTPUT:
            raise VerificationFailure("tool_output_limit")
        return process.returncode, output, diagnostic
