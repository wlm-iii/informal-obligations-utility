"""Real delivery-claim concurrency and migrations; Gmail is always fake here."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from threading import Event
from urllib.parse import parse_qs, urljoin, urlsplit
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_ledger_database import pg as pg
from test_ledger_database import post
from test_reminders import Mailer

from iou.api import app
from iou.auth import get_current_user
from iou.config import Settings
from iou.profiles import Profile
from iou.reminders import gmail, service
from iou.reminders.models import Recipient

pytestmark = pytest.mark.database


@pytest.fixture
def live(pg, monkeypatch):
    email = f"demo-{uuid4()}@example.com"
    config = Settings(
        _env_file=None,
        email_mode="gmail",
        gmail_client_id="fake-id",
        gmail_client_secret="fake-secret",
        gmail_refresh_token="fake-refresh",
        gmail_sender_email=email,
        reminder_signing_key="k" * 32,
        reminder_quiet_hours_enabled=False,
    )
    monkeypatch.setattr(service, "get_settings", lambda: config)
    mail = Mailer()
    monkeypatch.setattr(gmail, "get_mailer", lambda: mail)
    pg.email, pg.mail = email, mail
    return pg


def prepare(pg):
    friend = post(pg, "/friends", {"display_name": "Demo", "email": pg.email}).json()
    now = datetime.now(UTC)
    loan = post(
        pg,
        "/loans",
        {
            "friend_id": friend["id"],
            "kind": "money",
            "description": "Demo",
            "principal_cents": 5000,
            "lent_at": (now - timedelta(days=1)).isoformat(),
            "due_date": (now + timedelta(days=1)).date().isoformat(),
        },
    )
    assert loan.status_code == 201, loan.text
    permission = pg.client.put(
        f"/friends/{friend['id']}/reminder-preferences",
        json={"recipient_email": pg.email, "permission_confirmed": True},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert permission.status_code == 201, permission.text
    row = post(pg, f"/friends/{friend['id']}/reminder-previews", {})
    assert row.status_code == 201, row.text
    return friend, loan.json(), row.json()


def send(pg, row, key=None):
    return post(
        pg, f"/reminders/{row['id']}/send", {"approved": True, "recipient_email": pg.email}, key
    )


def test_same_key_pending_replay_other_send_blocked_and_network_has_no_locks(live, monkeypatch):
    pg = live
    friend, _, row = prepare(pg)
    other = post(pg, f"/friends/{friend['id']}/reminder-previews", {"tone": "playful"}).json()
    entered, release = Event(), Event()
    key = uuid4()

    def pause():
        entered.set()
        assert release.wait(timeout=10)

    pg.mail.on_prepare = pause
    original_send = pg.mail.send

    def submit(token, envelope):
        with Session(pg.engine) as session:
            session.execute(text("SET LOCAL lock_timeout='500ms'"))
            assert session.scalar(select(Profile).where(Profile.id == pg.user.id).with_for_update())
            assert session.scalar(
                select(Recipient)
                .where(Recipient.id == service.address_hash(pg.email))
                .with_for_update()
            )
        return original_send(token, envelope)

    monkeypatch.setattr(pg.mail, "send", submit)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(send, pg, row, key)
        try:
            assert entered.wait(timeout=10)
            replay = send(pg, row, key)
            assert replay.status_code == 202 and replay.json()["status"] == "reserved"
            assert send(pg, other).status_code == 429
            # An independent DB transaction can acquire the normal owner writer lock.
            with Session(pg.engine) as session:
                session.execute(text("SET LOCAL lock_timeout='500ms'"))
                assert session.scalar(
                    select(Profile).where(Profile.id == pg.user.id).with_for_update()
                )
        finally:
            release.set()
        result = future.result(timeout=15)
    assert result.status_code == 202 and result.json()["status"] == "sent"
    assert len(pg.mail.sent) == 1
    assert send(pg, row, key).json()["status"] == "sent"
    assert len(pg.mail.sent) == 1


def test_selected_template_replay_is_immutable_on_postgresql(live):
    pg = live
    friend, _, original = prepare(pg)
    key = uuid4()
    choice = {"tone": "friendly", "template_id": 3}
    result = post(pg, f"/friends/{friend['id']}/reminder-previews", choice, key)
    assert result.status_code == 201, result.text
    assert result.json()["body"] != original["body"]
    assert "$50.00" in result.json()["body"]
    assert (
        post(pg, f"/friends/{friend['id']}/reminder-previews", choice, key).json() == result.json()
    )
    assert (
        post(
            pg,
            f"/friends/{friend['id']}/reminder-previews",
            {"tone": "friendly", "template_id": 2},
            key,
        ).status_code
        == 409
    )
    assert not pg.mail.sent


def test_settlement_during_token_exchange_cancels_before_submit(live):
    pg = live
    _, loan, row = prepare(pg)
    pg.mail.on_prepare = lambda: post(pg, f"/loans/{loan['id']}/repayments", {"amount_cents": 5000})
    result = send(pg, row)
    assert result.status_code == 202 and result.json()["status"] == "cancelled"
    assert not pg.mail.sent


class UnsubscribeForm(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.action = attrs["action"]
        if tag == "input" and attrs.get("name") == "token":
            self.token = attrs["value"]


def unsubscribe_token(row):
    link = row["body"].split("Stop IOU reminders: ")[1]
    return parse_qs(urlsplit(link).query)["token"][0]


def test_public_unsubscribe_form_mount_repeat_and_permission_override(live, monkeypatch):
    pg = live
    service.get_settings().reminder_public_base_url = "https://api.iou.example/api"
    friend, loan, row = prepare(pg)
    token = unsubscribe_token(row)
    link = row["body"].split("Stop IOU reminders: ")[1]
    assert urlsplit(link).path == "/api/reminders/unsubscribe"
    # Check the browser-visible /api prefix, not just direct FastAPI routes.
    mounted = FastAPI()
    mounted.mount("/api", app)
    auth = app.dependency_overrides.pop(get_current_user)
    try:
        with TestClient(mounted) as anonymous:
            assert anonymous.get("/api/reminders").status_code == 401
            page = anonymous.get("/api/reminders/unsubscribe", params={"token": token})
            assert page.status_code == 200
            assert page.headers["cache-control"] == "no-store"
            assert page.headers["referrer-policy"] == "no-referrer"
            assert "form-action 'self'" in page.headers["content-security-policy"]
            assert pg.email not in page.text
            form = UnsubscribeForm()
            form.feed(page.text)
            assert form.token == token
            post_url = urljoin(str(page.url), form.action)
            assert urlsplit(post_url).path == "/api/reminders/unsubscribe"
            assert not urlsplit(post_url).query
            with Session(pg.engine) as session:
                assert session.get(Recipient, service.address_hash(pg.email)).opted_out_at is None
            assert anonymous.post(post_url, data={"token": form.token}).status_code == 200
            with Session(pg.engine) as session:
                first = session.get(Recipient, service.address_hash(pg.email)).opted_out_at
                assert first is not None
            assert anonymous.post(post_url, data={"token": form.token}).status_code == 200
            with Session(pg.engine) as session:
                assert session.get(Recipient, service.address_hash(pg.email)).opted_out_at == first
    finally:
        app.dependency_overrides[get_current_user] = auth
    assert send(pg, row).status_code == 409
    # A lender cannot undo the recipient's opt-out, even by confirming again.
    response = pg.client.put(
        f"/friends/{friend['id']}/reminder-preferences",
        json={"recipient_email": pg.email, "permission_confirmed": True},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 201 and response.json()["opted_out"]
    from iou.ledger import service as ledger

    now = ledger.now_utc()
    monkeypatch.setattr(ledger, "now_utc", lambda: now + timedelta(days=2))
    assert post(pg, f"/friends/{friend['id']}/reminder-previews", {}).status_code == 409
    assert pg.client.get(f"/loans/{loan['id']}").json()["outstanding_cents"] == 5000
    assert not pg.mail.sent


def test_forged_unsubscribe_cannot_suppress_another_address(live):
    pg = live
    _, _, row = prepare(pg)
    original = unsubscribe_token(row)
    changed_signature = original[:-1] + ("0" if original[-1] != "0" else "1")
    changed_address = "v1." + "0" * 64 + "." + original.rsplit(".", 1)[1]
    for token in (changed_signature, changed_address):
        result = pg.client.post("/reminders/unsubscribe", data={"token": token})
        assert result.status_code == 400
    with Session(pg.engine) as session:
        assert session.get(Recipient, service.address_hash(pg.email)).opted_out_at is None
        assert session.get(Recipient, "0" * 64) is None
    assert send(pg, row).json()["status"] == "sent"
    assert len(pg.mail.sent) == 1


def test_unsubscribe_during_token_exchange_blocks_submission(live):
    pg = live
    _, _, row = prepare(pg)

    def opt_out():
        result = pg.client.post("/reminders/unsubscribe", data={"token": unsubscribe_token(row)})
        assert result.status_code == 200

    pg.mail.on_prepare = opt_out
    key = uuid4()
    result = send(pg, row, key)
    assert result.status_code == 202 and result.json()["status"] == "cancelled"
    assert send(pg, row, key).json()["status"] == "cancelled"
    assert not pg.mail.sent


def test_cross_owner_global_cooldown_and_guarded_downgrade(live):
    pg = live
    _, _, first = prepare(pg)
    assert send(pg, first).json()["status"] == "sent"
    pg.user = pg.users[1]
    _, _, second = prepare(pg)
    assert send(pg, second).status_code == 429
    assert not pg.client.get("/reminders").json()["items"][0]["id"] == first["id"]
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with pytest.raises(DBAPIError):
        command.downgrade(config, "0006_event_action_width")
    assert pg.client.get(f"/reminders/{second['id']}").status_code == 200
