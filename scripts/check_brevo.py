"""Read-only Brevo configuration check. Never prints API keys or account data."""
import argparse
import json
import os
import re
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env.brevo.local")
    args = parser.parse_args()
    key = os.environ.get("BREVO_API_KEY", "")
    if not key:
        path = Path(args.env_file)
        if path.is_file():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if line.startswith("BREVO_API_KEY="):
                    key = line.partition("=")[2].strip()
    if not key:
        raise SystemExit("BREVO_API_KEY no configurada; valor omitido")
    with httpx.Client(base_url="https://api.brevo.com/v3", timeout=20,
                      headers={"api-key": key}, follow_redirects=False,
                      transport=httpx.HTTPTransport(local_address="0.0.0.0"), trust_env=False) as client:
        try:
            account = client.get("/account")
            result = {"authentication_http_status": account.status_code,
                      "email_sent": False}
            if account.status_code != 200:
                try:
                    diagnostic = str(account.json().get("message", "")).replace(key, "[redacted]")
                    result["diagnostic"] = diagnostic[:500]
                    message = diagnostic.lower()
                    result["cause"] = ("ip_authorization_required" if "ip" in message and
                                       any(word in message for word in ("recogn", "author", "allow", "white"))
                                       else "key_not_recognized" if "key" in message and
                                       any(word in message for word in ("not found", "invalid"))
                                       else "authentication_rejected")
                    if result["cause"] == "ip_authorization_required":
                        address = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", message)
                        if address:
                            result["ip_to_authorize"] = address.group(0)
                except (ValueError, AttributeError):
                    result["cause"] = "authentication_rejected"
                print(json.dumps(result))
                raise SystemExit(1)
            senders = client.get("/senders")
            result["senders_http_status"] = senders.status_code
            if senders.status_code == 200:
                result["senders"] = [
                    {"email": sender.get("email"), "active": sender.get("active"),
                     "dkim": sender.get("dkim_status"), "spf": sender.get("spf_status")}
                    for sender in senders.json().get("senders", [])
                ]
            print(json.dumps(result, ensure_ascii=False))
        except httpx.HTTPError:
            raise SystemExit("Brevo no accesible; petición de solo lectura; detalles sensibles omitidos") from None


if __name__ == "__main__":
    main()
