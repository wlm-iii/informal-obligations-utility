"""Bounded Gmail REST protocol and MIME encoding; no network."""

import base64
import json
from email import policy
from email.parser import BytesParser
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pytest
from pydantic import ValidationError

from iou.config import Settings
from iou.reminders import gmail
from iou.reminders.service import Envelope


def settings(**changes):
    values = dict(
        email_mode="gmail",
        gmail_client_id="private-client-id",
        gmail_client_secret="private-client-secret",
        gmail_refresh_token="private-refresh",
        gmail_sender_email="sender@example.com",
        reminder_signing_key="x" * 32,
    )
    return Settings(_env_file=None, **{**values, **changes})


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, limit):
        return self.body[:limit]


class Opener:
    def __init__(self, response=b"{}", error=None):
        self.response, self.error, self.calls = response, error, []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return Response(self.response)


@pytest.fixture
def envelope():
    return Envelope(
        uuid4(),
        "friend@example.com",
        "A friendly IOU reminder",
        "Hello friend. Please return the hoodie.\nStop: https://example.com/unsubscribe",
    )


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://iou@remote.example/iou",
        "postgresql+psycopg://iou@127.0.0.1/iou?host=remote.example",
        "sqlite://",
    ],
)
def test_demo_rejects_nonlocal_or_override_urls_before_any_work(monkeypatch, url):
    import sys

    from iou.reminders import demo

    monkeypatch.setattr(sys, "argv", ["demo", "--database-url", url])
    with pytest.raises(SystemExit) as error:
        demo.main()
    assert error.value.code == 2


def test_oauth_uses_form_post_and_never_places_credentials_in_url(monkeypatch):
    opener = Opener(b'{"access_token":"private-access"}')
    monkeypatch.setattr(gmail, "build_opener", lambda *_: opener)
    assert gmail.Gmail(settings()).prepare() == "private-access"
    request, timeout = opener.calls[0]
    assert request.full_url == "https://oauth2.googleapis.com/token" and timeout == 10
    assert b"refresh_token=private-refresh" in request.data
    assert b"grant_type=refresh_token" in request.data
    assert "private" not in request.full_url


def test_send_mime_is_plain_text_exact_recipient_and_no_inbox_access(monkeypatch, envelope):
    opener = Opener(b'{"id":"provider-id"}')
    monkeypatch.setattr(gmail, "build_opener", lambda *_: opener)
    assert gmail.Gmail(settings()).send("private-access", envelope) == "provider-id"
    request, _ = opener.calls[0]
    assert request.full_url == "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    assert request.get_header("Authorization") == "Bearer private-access"
    raw = base64.urlsafe_b64decode(json.loads(request.data)["raw"])
    mime = BytesParser(policy=policy.default).parsebytes(raw)
    assert mime["To"] == envelope.recipient_email
    assert mime["From"] == "IOU <sender@example.com>"
    assert mime.get_content_type() == "text/plain"
    assert mime.get_content().strip() == envelope.body
    assert len(opener.calls) == 1


@pytest.mark.parametrize(
    "code,exception",
    [
        (400, gmail.Rejected),
        (401, gmail.Rejected),
        (403, gmail.Rejected),
        (429, gmail.Rejected),
        (408, gmail.Uncertain),
        (500, gmail.Uncertain),
        (503, gmail.Uncertain),
        (302, gmail.Uncertain),
    ],
)
def test_send_failure_classification_and_no_retry(monkeypatch, envelope, code, exception):
    opener = Opener(
        error=HTTPError("https://gmail.googleapis.com", code, "private details", {}, None)
    )
    monkeypatch.setattr(gmail, "build_opener", lambda *_: opener)
    with pytest.raises(exception) as error:
        gmail.Gmail(settings()).send("private-access", envelope)
    assert len(opener.calls) == 1 and "private" not in str(error.value)


@pytest.mark.parametrize(
    "body",
    [b"[]", b"not json", b"{}", b'{"id":123}', b"x" * 70000],
    ids=["json-array", "invalid-json", "missing-id", "non-string-id", "oversized-response"],
)
def test_malformed_acceptance_is_uncertain(monkeypatch, envelope, body, request):
    # Pytest exports this ID via PYTEST_CURRENT_TEST. A raw 70KB parameter exceeds
    # Windows' environment-variable limit before the actual test can run.
    assert len(request.node.callspec.id) < 64
    opener = Opener(body)
    monkeypatch.setattr(gmail, "build_opener", lambda *_: opener)
    with pytest.raises(gmail.Uncertain):
        gmail.Gmail(settings()).send("private-access", envelope)


def test_network_failure_is_uncertain_but_refresh_failure_is_safe(monkeypatch, envelope):
    opener = Opener(error=URLError("private details"))
    monkeypatch.setattr(gmail, "build_opener", lambda *_: opener)
    mailer = gmail.Gmail(settings())
    with pytest.raises(gmail.Uncertain):
        mailer.send("private-access", envelope)
    with pytest.raises(gmail.PreparationFailed):
        mailer.prepare()


@pytest.mark.parametrize(
    "change",
    [
        dict(gmail_client_id=""),
        dict(gmail_client_secret=""),
        dict(gmail_refresh_token=""),
        dict(gmail_sender_email=None),
        dict(reminder_signing_key=None),
        dict(reminder_signing_key="short"),
        dict(reminder_public_base_url="http://remote.example"),
        dict(reminder_public_base_url="https://user:password@example.com"),
        dict(reminder_public_base_url="https://example.com?secret=yes"),
    ],
)
def test_live_configuration_fails_closed_without_leaking_secrets(change):
    with pytest.raises(ValidationError) as error:
        settings(**change)
    assert "private-client-secret" not in str(error.value)
    assert "private-refresh" not in str(error.value)
