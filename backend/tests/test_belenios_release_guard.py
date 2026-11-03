"""Reject laboratory/provider misconfiguration before starting the native server."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release_entrypoint", ROOT / "deploy/belenios-release/entrypoint.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

CONFIG = b'''<ocsigen><server><host><site path="static"><static dir="_SHAREDIR_/static"/></site>
<eliom name="belenios"><public-url prefix="https://ballot.example.invalid"/>
<tos uri="https://ballot.example.invalid/_pilot/alcance.html"/>
<restricted/><deny-revote/>
<auth name="operators"><password db="passwords" allowlist="operators"/></auth>
<storage backend="filesystem"><spool dir="_VARDIR_/spool"/><accounts dir="_VARDIR_/accounts"/>
<map from="operators" to="_VARDIR_/private/operators"/>
<map from="passwords" to="_VARDIR_/private/passwords"/></storage>
</eliom></host></server></ocsigen>'''


def environment():
    return {"BELENIOS_DEPLOY_APPROVAL": "synthetic-review-reference", "BELENIOS_POLICY": "R2",
            "BELENIOS_PUBLIC_URL": "https://ballot.example.invalid", "BELENIOS_SENDMAIL": "/usr/local/bin/approved-mailer",
            "BELENIOS_VARDIR": "/var/lib/belenios", "BELENIOS_RUNDIR": "/tmp/belenios"}


@pytest.mark.parametrize("policy", ["R1", "R2"])
def test_release_accepts_explicit_policy_and_private_operator_allowlist(policy):
    env = environment(); env["BELENIOS_POLICY"] = policy
    config = CONFIG.replace(b"<deny-revote/>", b"") if policy == "R1" else CONFIG
    result = release.validate(config, env)
    assert result["policy"] == policy
    assert set(result["operator_private_files"]) == {"_VARDIR_/private/operators", "_VARDIR_/private/passwords"}


@pytest.mark.parametrize("before,after", [
    (b"<restricted/>", b""), (b"<deny-revote/>", b""),
    (b'<tos uri="https://ballot.example.invalid/_pilot/alcance.html"/>', b''),
    (b'<password db="passwords" allowlist="operators"/>', b"<dummy/>"),
    (b'<password db="passwords" allowlist="operators"/>', b'<password allowsignups="true" db="passwords" allowlist="operators"/>'),
    (b'<password db="passwords" allowlist="operators"/>', b'<password allowsignups="false" db="passwords" allowlist="operators"/>'),
    (b'<password db="passwords" allowlist="operators"/>', b"<email/>"),
    (b'<password db="passwords" allowlist="operators"/>', b'<password allowlist="operators"/>'),
    (b'_VARDIR_/private/operators', b'demo/operators'),
    (b'_SHAREDIR_/static', b'_VARDIR_/spool'),
    (b'https://ballot.example.invalid', b'http://ballot.example.invalid'),
    (b'_VARDIR_/spool', b'/tmp/public-spool'),
])
def test_release_rejects_unsafe_operator_configuration(before, after):
    with pytest.raises(release.InvalidConfiguration):
        release.validate(CONFIG.replace(before, after), environment())


@pytest.mark.parametrize("key,value", [
    ("BELENIOS_DEPLOY_APPROVAL", ""), ("BELENIOS_POLICY", "automatic"),
    ("BELENIOS_SENDMAIL", "/opt/fake-mailer"), ("BELENIOS_VARDIR", "/tmp/public"),
    ("BELENIOS_PUBLIC_URL", "https://operator:secret@ballot.example.invalid"),
])
def test_release_requires_explicit_external_configuration(key, value):
    env = environment(); env[key] = value
    with pytest.raises(release.InvalidConfiguration): release.validate(CONFIG, env)


def test_release_rejects_xml_entities():
    with pytest.raises(release.InvalidConfiguration):
        release.validate(b'<!DOCTYPE ocsigen [<!ENTITY private SYSTEM "file:///private">]>' + CONFIG, environment())
