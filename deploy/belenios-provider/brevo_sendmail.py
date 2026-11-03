#!/usr/bin/python3
"""Bounded sendmail bridge for native authentication mail; never generates credentials."""
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from uuid import uuid4

LIMIT = 1024 * 1024


class MailUnavailable(Exception): pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args): return None


def payload(raw, config):
    if not raw or len(raw) > LIMIT: raise MailUnavailable("message_size")
    message = BytesParser(policy=policy.default).parsebytes(raw)
    if message.defects or any(part.get_content_disposition() == "attachment" for part in message.walk()):
        raise MailUnavailable("unsupported_message")
    recipients = {address.lower() for _, address in getaddresses(
        [str(value) for name in ("To", "Cc", "Bcc") for value in message.get_all(name, [])])}
    if len(recipients) != 1: raise MailUnavailable("one_recipient_required")
    recipient = recipients.pop()
    recipient = config.get("aliases", {}).get(recipient, recipient)
    if recipient not in config["allowed_recipients"]: raise MailUnavailable("recipient_not_authorized")
    subject = str(message.get("Subject", ""))
    if not subject or len(subject) > 250 or any(c in subject for c in "\r\n"):
        raise MailUnavailable("invalid_subject")
    body = {"sender": {"email": config["sender"], "name": config["sender_name"]},
            "to": [{"email": recipient}], "subject": subject, "tags": ["belenios-pilot-auth"]}
    for content_type, name in (("plain", "textContent"), ("html", "htmlContent")):
        part = message.get_body(preferencelist=(content_type,))
        if part is not None: body[name] = part.get_content()
    if not body.get("textContent") and not body.get("htmlContent"):
        raise MailUnavailable("body_required")
    return body


def transport(body, key):
    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request("https://api.brevo.com/v3/smtp/email", data=json.dumps(body).encode(),
        method="POST", headers={"content-type": "application/json", "api-key": key})
    with opener.open(request, timeout=15) as response:
        if response.status != 201: raise MailUnavailable("provider_status")
        result = json.loads(response.read(8192))
    identifier = result.get("messageId")
    if not isinstance(identifier, str) or not identifier or len(identifier) > 512:
        raise MailUnavailable("acceptance_not_confirmed")
    return identifier


def deliver(raw, config, key, journal, sender=transport):
    body = payload(raw, config)
    digest = hashlib.sha256(raw).hexdigest()
    if not key or len(key) < 32: raise MailUnavailable("key_not_configured")
    connection = sqlite3.connect(journal, timeout=5)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS deliveries (digest TEXT PRIMARY KEY, operation TEXT, state TEXT, message_id TEXT)")
        operation = uuid4().hex
        try:
            connection.execute("INSERT INTO deliveries VALUES (?,?,?,NULL)", (digest, operation, "INTENT")); connection.commit()
        except sqlite3.IntegrityError:
            connection.rollback()
            row = connection.execute("SELECT state FROM deliveries WHERE digest=?", (digest,)).fetchone()
            if row and row[0] == "ACCEPTED": return "already_accepted"
            raise MailUnavailable("existing_intent_requires_reconciliation") from None
        try:
            message_id = sender(body, key)
        except Exception as error:
            state = "REJECTED" if isinstance(error, HTTPError) and 400 <= error.code < 500 else "UNKNOWN"
            connection.execute("UPDATE deliveries SET state=? WHERE digest=?", (state, digest)); connection.commit()
            raise MailUnavailable("delivery_not_confirmed") from None
        connection.execute("UPDATE deliveries SET state='ACCEPTED', message_id=? WHERE digest=?", (message_id, digest)); connection.commit()
        return "accepted"
    finally: connection.close()


def main():
    os.umask(0o077)
    try:
        config = json.loads(Path(os.environ["BELENIOS_MAIL_CONFIG"]).read_text())
        key = Path(os.environ["BREVO_API_KEY_FILE"]).read_text().strip()
        deliver(sys.stdin.buffer.read(LIMIT + 1), config, key, os.environ["BELENIOS_MAIL_JOURNAL"])
    except (MailUnavailable, OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        print("Native authentication mail not confirmed; inspect private delivery state", file=sys.stderr)
        raise SystemExit(75) from None


if __name__ == "__main__": main()
