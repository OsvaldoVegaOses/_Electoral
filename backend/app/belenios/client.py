import base64
import hashlib
import http.client
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import urllib.error
import urllib.parse
import urllib.request

from fastapi import HTTPException
from app.config import settings
from app.belenios.deployment import require_enabled, https_destination, confirm_manifest

COMMIT = "337887bd1862c7cd057080b530fd80941bfc3c69"


class ProviderError(Exception):
    """No response bodies, URLs containing capabilities, or secrets in public errors."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BeleniosClient:
    def __init__(self, policy):
        require_enabled()
        if policy not in ("R1", "R2"):
            raise HTTPException(422, "Seleccione explícitamente R1 o R2.")
        self.policy = policy
        self.base = getattr(settings, f"BELENIOS_{policy}_URL").rstrip("/")
        parsed = urllib.parse.urlsplit(self.base)
        expected_port = 18001 if policy == "R1" else 18002
        if settings.BELENIOS_MODE == 'pilot':
            self.base = https_destination(self.base)
        elif parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != expected_port or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise HTTPException(503, "Destino de laboratorio Belenios inválido.")
        self.token = getattr(settings, f"BELENIOS_{policy}_ADMIN_TOKEN").get_secret_value()
        if not self.token:
            raise HTTPException(503, "Falta la credencial administrativa del servidor seleccionado.")
        import ssl
        context=ssl.create_default_context(cafile=settings.BELENIOS_CA_FILE or None)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=context))

    def call(self, method, route, payload=None, match=False, raw=False):
        if not re.fullmatch(r"[a-zA-Z0-9/_-]+", route):
            raise ProviderError("Ruta de proveedor inválida")
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + self.token}
        if match:
            current = self.call("GET", route, raw=True)
            headers["If-Match"] = base64.b64encode(hashlib.sha256(current).digest()).decode().rstrip("=")
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        request = urllib.request.Request(self.base + "/api/" + route, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=15) as response:
                data = response.read(8 * 1024 * 1024 + 1)
                if len(data) > 8 * 1024 * 1024:
                    raise ProviderError("Respuesta del proveedor demasiado grande")
            return data if raw else json.loads(data)
        except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError):
            raise ProviderError("No se pudo confirmar la operación del proveedor; no se reintentó") from None

    def check(self):
        config = self.call("GET", "configuration")
        if config.get("belenios_version") != "3.3.0" or config.get("api_version") != 6:
            raise ProviderError("Versión Belenios/API no admitida")
        if settings.BELENIOS_MODE == 'pilot':
            confirm_manifest(self.policy,self.base)
            return
        # API 6 does not expose deny-revote. Inspect the fixed laboratory runtime.
        container = "theogen-belenios33-poc-" + ("revote" if self.policy == "R1" else "single") + "-1"
        try:
            inspected = json.loads(subprocess.check_output(["docker", "inspect", container], stderr=subprocess.DEVNULL, timeout=10))[0]
            conf = subprocess.check_output(["docker", "exec", container, "cat", "/tmp/ocsigenserver-poc.conf.in"], stderr=subprocess.DEVNULL, timeout=10)
            denied = bool(list(ET.fromstring(conf).iter("deny-revote")))
            if inspected['State']['Status'] != 'running' or inspected['Config']['Labels']['org.opencontainers.image.revision'] != COMMIT or denied != (self.policy == "R2"):
                raise ValueError("Runtime mismatch")
        except (subprocess.SubprocessError, OSError, ValueError, KeyError, ET.ParseError):
            raise ProviderError("No se confirmó versión/política del runtime de laboratorio") from None


def legacy_guard(db, election_id):
    from app.models import BeleniosBinding
    if db.query(BeleniosBinding.id).filter(BeleniosBinding.election_id == election_id).first():
        raise HTTPException(409, "Elección gestionada en Belenios. Use sus operaciones y resultados verificados; el motor MVP está bloqueado.")
