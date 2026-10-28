"""Networkless verifier process; no Docker socket is exposed to browser or containerized API."""
import hashlib
import io
import json
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path

from fastapi import HTTPException
from app.config import settings
from app.models import Election
from app.belenios.client import COMMIT, ProviderError, require_enabled

TOOL = "/home/belenios/belenios/_run/usr/bin/belenios-tool"


def public_archive(policy, uuid):
    image = settings.BELENIOS_VERIFIER_IMAGE
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise ProviderError("Falta imagen verificadora inmutable")
    try:
        inspected = json.loads(subprocess.check_output(["docker", "image", "inspect", image], stderr=subprocess.DEVNULL, timeout=10))[0]
        if inspected['Id'] != image or inspected['Config']['Labels']['org.opencontainers.image.revision'] != COMMIT:
            raise ValueError("Image mismatch")
        service, network = ("revote", "a") if policy == "R1" else ("single", "b")
        collected = subprocess.run(["docker", "run", "--rm", "--network", "theogen-belenios33-poc_ballot-" + network,
                                    "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--entrypoint", TOOL,
                                    image, "archive", "pull", "--url", f"http://{service}:8001/", "--uuid", uuid], capture_output=True, timeout=45)
        if collected.returncode or len(collected.stdout) > 8 * 1024 * 1024:
            raise ValueError("Archive download failed")
        archive = collected.stdout
        with tempfile.TemporaryDirectory(prefix="theogen-public-verification-") as directory:
            Path(directory, uuid + ".bel").write_bytes(archive)
            verified = subprocess.run(["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
                                       "--security-opt", "no-new-privileges:true", "--mount", f"type=bind,src={directory},dst=/audit,readonly",
                                       "--entrypoint", TOOL, image, "election", "verify", "--dir", "/audit"], capture_output=True, timeout=45)
        if verified.returncode or b"all checks passed" not in verified.stderr or b"no result to check" in verified.stderr:
            raise ValueError("Incomplete/invalid archive")
        return archive
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        raise ProviderError("No se confirmó la verificación externa completa") from None


def verify_result(db, binding, body, client, archive_runner=public_archive):
    require_enabled()
    if binding.phase not in ("Tallied", "Verified") or binding.inflight or not binding.remote_uuid:
        raise HTTPException(409, "Se requiere un escrutinio completo confirmado, sin operaciones pendientes.")
    route = "elections/" + binding.remote_uuid
    client.check()
    if client.call("GET", route)["state"] != "Tallied":
        raise HTTPException(409, "El proveedor no tiene resultado final.")
    head = client.call("GET", route + "/last-event")
    roots = client.call("GET", route + "/roots")
    if head.get("hash") != body.final_event_hash or roots.get("result") != body.result_object_hash:
        raise HTTPException(409, "El resultado no coincide con el anclaje revisado.")
    raw = client.call("GET", route + "/objects/" + body.result_object_hash, raw=True)
    if hashlib.sha256(raw).hexdigest() != body.result_object_hash:
        raise HTTPException(409, "Huella de resultado inválida.")
    public_election = client.call("GET", route + "/election")
    expected = json.loads(binding.draft_json)["questions"]
    if public_election.get("questions") != expected["questions"] or public_election.get("name") != expected["name"] or public_election.get("description") != expected["description"]:
        raise HTTPException(409, "La papeleta pública no coincide con la configuración aprobada.")
    result = json.loads(raw)["result"]
    active = client.call("GET", route + "/ballots")
    if len(result) != 1 or len(result[0]) != len(expected["questions"][0]["answers"]) or any(str(weight) != "1" for weight in active.values()):
        raise HTTPException(409, "Formato/ponderación no soportado por esta integración.")
    if any(not re.fullmatch(r"[0-9]+", str(value)) for value in result[0]):
        raise HTTPException(409, "Conteos inválidos.")
    counts = [int(value) for value in result[0]]
    if sum(counts) != len(active) or len(active) > binding.total_units:
        raise HTTPException(409, "Conteos o denominador inconsistentes.")
    archive = archive_runner(binding.policy, binding.remote_uuid)
    if hashlib.sha256(archive).hexdigest() != body.archive_sha256:
        raise HTTPException(409, "El archivo público no coincide con el anclaje revisado.")
    try:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            member = next((m for m in tar.getmembers() if m.isfile() and body.result_object_hash in m.name), None)
            if member is None or tar.extractfile(member).read() != raw:
                raise ValueError("Archive/API mismatch")
    except (tarfile.TarError, ValueError):
        raise HTTPException(409, "El archivo verificado y el API difieren.") from None
    evidence = {"schema": "theogen-belenios-result/v1", "experimental": True, "uuid": binding.remote_uuid,
                "policy": binding.policy, "total_people": binding.total_people, "enabled_units": binding.total_units,
                "counted_ballots": len(active), "participation": len(active) / binding.total_units,
                "options": [{"label": label, "votes": count} for label, count in zip(expected["questions"][0]["answers"], counts)],
                "blank": None, "null": None, "ballot_mode": "mandatory_single_choice_no_blank_no_null",
                "archive_sha256": body.archive_sha256, "final_event_hash": body.final_event_hash, "result_object_hash": body.result_object_hash,
                "verifier_image": settings.BELENIOS_VERIFIER_IMAGE, "upstream_commit": COMMIT, "verification_exit_code": 0,
                "anchor_reference": body.anchor_reference, "independent_custody_confirmed": False,
                "legal_status": "PROTOTIPO_SIN_VALIDEZ_JURIDICA", "quorum_assessed": False, "signatures": []}
    binding.verified_result, binding.phase = json.dumps(evidence, separators=(",", ":")), "Verified"
    db.get(Election, binding.election_id).estado = "Finalizada"
    db.commit()
    return evidence
