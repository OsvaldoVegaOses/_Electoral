"""Run inside a networkless, read-only container with only public-data mounts."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import time
from .common import (COMMIT, TOOL, MAX_ARCHIVE, MAX_OUTPUT, VerificationFailure,
                     archive_digest, atomic_json, identity, immutable_image, read_regular, run_bounded)


def process_job(inbox, outbox, job_id, image, *, tool=TOOL, timeout=30, runner=run_bounded):
    if not re.fullmatch(r"[0-9a-f]{32}", job_id): raise VerificationFailure("invalid_job_id")
    image = immutable_image(image)
    inbox, outbox = Path(inbox), Path(outbox)
    result_path = outbox / (job_id + ".json")
    if result_path.exists(): return False
    try:
        descriptor = os.open(outbox / (job_id + ".claim"), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError: return False
    os.close(descriptor)
    result = {"job_id": job_id, "status": "rejected", "upstream_commit": COMMIT, "tool_image": image}
    try:
        directory = inbox / job_id
        if directory.is_symlink(): raise VerificationFailure("unsafe_job_directory")
        request = json.loads(read_regular(directory / "request.json", 2048))
        if set(request) != {"policy", "uuid", "archive_sha256"}: raise VerificationFailure("invalid_job_request")
        identity(request["policy"], request["uuid"])
        data = read_regular(directory / "archive.bel", MAX_ARCHIVE)
        digest = archive_digest(data, request["uuid"])
        if digest != request["archive_sha256"]: raise VerificationFailure("archive_binding_mismatch")
        result.update(policy=request["policy"], uuid=request["uuid"], archive_sha256=digest)
        with tempfile.TemporaryDirectory(prefix="belenios-public-") as temporary:
            work = Path(temporary)
            (work / (request["uuid"] + ".bel")).write_bytes(data)
            code, version, diagnostic = runner([tool, "--version"], cwd=work, timeout=5, stdout_limit=MAX_OUTPUT)
            if code or not re.search(rb"(?<![0-9])3\.3\.0(?![0-9.~])", version + diagnostic):
                raise VerificationFailure("wrong_tool_version")
            code, _, diagnostic = runner([tool, "election", "verify", "--dir", str(work)],
                                          cwd=work, timeout=timeout, stdout_limit=MAX_OUTPUT)
            if code or b"all checks passed" not in diagnostic or b"no result to check" in diagnostic:
                raise VerificationFailure("incomplete_or_invalid_election")
        result.update(status="verified", verification_exit_code=0, final_result_checked=True)
    except (VerificationFailure, OSError, ValueError, KeyError, TypeError):
        result["reason"] = "public_archive_verification_failed"
    atomic_json(result_path, result)
    return True


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--once", action="store_true"); args = parser.parse_args()
    inbox = Path(os.environ.get("VERIFIER_INBOX", "/spool/inbox"))
    outbox = Path(os.environ.get("VERIFIER_OUTBOX", "/spool/outbox"))
    image = immutable_image(os.environ.get("VERIFIER_TOOL_IMAGE", ""))
    while True:
        atomic_json(outbox / "heartbeat.json", {"observed_at": time.time(), "upstream_commit": COMMIT})
        for directory in sorted(inbox.iterdir()):
            if re.fullmatch(r"[0-9a-f]{32}", directory.name) and (directory / "request.json").exists():
                process_job(inbox, outbox, directory.name, image)
        if args.once: return
        time.sleep(0.5)


if __name__ == "__main__": main()
