"""Validate operator-provided release configuration; never generate demo identities."""
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET


class InvalidConfiguration(Exception): pass


def validate(raw, environment):
    if len(raw) > 256*1024 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise InvalidConfiguration("invalid_xml")
    try: root = ET.fromstring(raw)
    except ET.ParseError: raise InvalidConfiguration("invalid_xml") from None
    if root.tag != "ocsigen" or any("{" in node.tag for node in root.iter()):
        raise InvalidConfiguration("unsupported_xml_namespace")
    if any(node.tag in ("dummy", "debug") for node in root.iter()):
        raise InvalidConfiguration("laboratory_authentication_forbidden")
    if not environment.get("BELENIOS_DEPLOY_APPROVAL"):
        raise InvalidConfiguration("deployment_approval_required")
    policy = environment.get("BELENIOS_POLICY")
    if policy not in ("R1", "R2"): raise InvalidConfiguration("explicit_policy_required")
    servers = list(root.iter("server"))
    # The configuration also contains an email <server/> inside eliom.
    servers = [node for node in servers if node.find("host") is not None]
    applications = [node for node in root.iter("eliom") if node.get("name") == "belenios"]
    if len(servers) != 1 or len(applications) != 1: raise InvalidConfiguration("one_provider_required")
    app = applications[0]
    public = app.findall("public-url")
    expected = environment.get("BELENIOS_PUBLIC_URL", "").rstrip("/")
    parsed = urlsplit(expected)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.port not in (None,443)
            or "%" in parsed.path or any(part in (".","..") for part in parsed.path.split("/"))):
        raise InvalidConfiguration("public_https_required")
    if len(public) != 1 or public[0].get("prefix", "").rstrip("/") != expected:
        raise InvalidConfiguration("public_origin_mismatch")
    terms = app.findall("tos")
    if len(terms) != 1 or not terms[0].get("uri", "").startswith("https://"):
        raise InvalidConfiguration("pilot_scope_uri_required")
    if len(app.findall("restricted")) != 1: raise InvalidConfiguration("restricted_mode_required")
    if len(app.findall("deny-revote")) != (1 if policy == "R2" else 0):
        raise InvalidConfiguration("revote_policy_mismatch")
    for node in root.iter("static"):
        if node.get("dir") != "_SHAREDIR_/static": raise InvalidConfiguration("private_data_must_not_be_served")
    storage = app.findall("storage")
    if len(storage) != 1 or storage[0].get("backend") != "filesystem":
        raise InvalidConfiguration("persistent_filesystem_required")
    for tag, path in (("spool","_VARDIR_/spool"),("accounts","_VARDIR_/accounts")):
        nodes = storage[0].findall(tag)
        if len(nodes) != 1 or nodes[0].get("dir") != path:
            raise InvalidConfiguration("private_storage_layout_required")
    auth = app.findall("auth")
    if not auth: raise InvalidConfiguration("operator_authentication_required")
    maps = {node.get("from"):node.get("to") for node in storage[0].findall("map")}
    for provider in auth:
        methods = list(provider)
        # Native restricted mode permits password administrators and email voters.
        if len(methods) != 1 or methods[0].tag != "password":
            raise InvalidConfiguration("unsupported_operator_authentication")
        method = methods[0]
        if "allowsignups" in method.attrib:
            raise InvalidConfiguration("public_signups_forbidden")
        allowlist = maps.get(method.get("allowlist"), "")
        if not re.fullmatch(r"_VARDIR_/private/[A-Za-z0-9_-]+", allowlist):
            raise InvalidConfiguration("private_operator_allowlist_required")
        database = maps.get(method.get("db"), "")
        if not re.fullmatch(r"_VARDIR_/private/[A-Za-z0-9_-]+", database):
            raise InvalidConfiguration("private_operator_password_database_required")
    mailer = environment.get("BELENIOS_SENDMAIL", "")
    if (not mailer.startswith("/") or any(word in mailer.lower() for word in ("fake", "demo", "poc", "static"))
            or re.search(r"\s", mailer)):
        raise InvalidConfiguration("approved_mail_transport_required")
    vardir = environment.get("BELENIOS_VARDIR", "")
    rundir = environment.get("BELENIOS_RUNDIR", "")
    if vardir != "/var/lib/belenios" or rundir != "/tmp/belenios":
        raise InvalidConfiguration("private_runtime_layout_required")
    return {"policy":policy,"public_url":expected,"operator_private_files":list({
        maps[method.get(key)] for provider in auth for method in provider for key in ("allowlist","db")})}


def main():
    try:
        config = Path(os.environ["BELENIOS_CONFIG"])
        if Path(str(config)+".preload").exists(): raise InvalidConfiguration("shell_preload_forbidden")
        result = validate(config.read_bytes(), os.environ)
        for template in result["operator_private_files"]:
            path = Path(template.replace("_VARDIR_", os.environ["BELENIOS_VARDIR"]))
            if not path.is_file() or not path.read_bytes().strip(): raise InvalidConfiguration("operator_allowlist_not_provisioned")
        if not os.access(os.environ["BELENIOS_SENDMAIL"], os.X_OK):
            raise InvalidConfiguration("mail_transport_not_provisioned")
    except (InvalidConfiguration, OSError, KeyError, ValueError, TypeError):
        print("Belenios release configuration rejected; no server started", file=sys.stderr)
        raise SystemExit(64) from None
    os.umask(0o077)
    os.execv("./demo/run-server.sh", ["./demo/run-server.sh"])


if __name__ == "__main__": main()
