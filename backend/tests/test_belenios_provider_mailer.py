import importlib.util
from pathlib import Path
import sqlite3
from urllib.error import HTTPError, URLError
import pytest

spec=importlib.util.spec_from_file_location("provider_mailer",Path(__file__).resolve().parents[2]/"deploy/belenios-provider/brevo_sendmail.py")
mailer=importlib.util.module_from_spec(spec);spec.loader.exec_module(mailer)
RAW=b"From: native@example.invalid\r\nTo: operator@example.invalid\r\nSubject: Native login\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nSynthetic login code\r\n"
CONFIG={"sender":"verified@example.invalid","sender_name":"Synthetic sender","allowed_recipients":["operator@example.invalid"]}


def test_authenticated_message_does_not_use_untrusted_from():
    body=mailer.payload(RAW,CONFIG)
    assert body["sender"]["email"]=="verified@example.invalid"
    assert body["textContent"].strip()=="Synthetic login code"


@pytest.mark.parametrize("raw",[b"",RAW.replace(b"operator@example.invalid",b"unauthorized@example.invalid"),
    RAW.replace(b"To: operator@example.invalid",b"To: operator@example.invalid, other@example.invalid"),
    RAW.replace(b"Content-Type: text/plain",b"Content-Disposition: attachment\r\nContent-Type: text/plain")])
def test_invalid_message_never_reaches_provider(tmp_path,raw):
    def forbidden(*args):pytest.fail("Unauthorized message sent")
    with pytest.raises(mailer.MailUnavailable):mailer.deliver(raw,CONFIG,"synthetic-"+"k"*32,tmp_path/"mail.sqlite",forbidden)


def test_accepted_message_is_not_sent_twice(tmp_path):
    journal=tmp_path/"mail.sqlite";calls=[]
    def sender(*args):calls.append(1);return "<synthetic-accepted-id>"
    assert mailer.deliver(RAW,CONFIG,"synthetic-"+"k"*32,journal,sender)=="accepted"
    assert mailer.deliver(RAW,CONFIG,"synthetic-"+"k"*32,journal,sender)=="already_accepted"
    assert calls==[1]
    assert b"Synthetic login code" not in journal.read_bytes()


@pytest.mark.parametrize("error,state",[(URLError("synthetic"),"UNKNOWN"),(HTTPError("https://api.brevo.com",401,"synthetic",{},None),"REJECTED")])
def test_uncertain_or_rejected_send_requires_reconciliation_without_retry(tmp_path,error,state):
    journal=tmp_path/"mail.sqlite";calls=[]
    def sender(*args):calls.append(1);raise error
    with pytest.raises(mailer.MailUnavailable):mailer.deliver(RAW,CONFIG,"synthetic-"+"k"*32,journal,sender)
    with pytest.raises(mailer.MailUnavailable):mailer.deliver(RAW,CONFIG,"synthetic-"+"k"*32,journal,sender)
    assert calls==[1]
    with sqlite3.connect(journal) as connection:assert connection.execute("SELECT state FROM deliveries").fetchone()[0]==state
