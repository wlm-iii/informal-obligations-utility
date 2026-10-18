"""Manual-only reminder contract. No Google requests or actual email in this suite."""

from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session
from test_ledger import NOW, new_friend, new_loan, post
from test_ledger import api as api

from iou.auth import Identity, get_current_user
from iou.config import Settings
from iou.reminders import gmail, service
from iou.reminders.models import Reminder


class Mailer:
    def __init__(self):
        self.sent = []
        self.on_prepare = lambda: None
        self.failure = None

    def prepare(self):
        self.on_prepare()
        if self.failure == "prepare":
            raise gmail.PreparationFailed
        return "fake-access-token"

    def send(self, token, envelope):
        assert token == "fake-access-token"
        self.sent.append(envelope)
        if self.failure == "reject":
            raise gmail.Rejected
        if self.failure == "uncertain":
            raise gmail.Uncertain
        return "fake-message-id"


@pytest.fixture
def mail(api, monkeypatch):
    settings = Settings(
        _env_file=None,
        email_mode="gmail",
        gmail_client_id="fake-id",
        gmail_client_secret="fake-secret",
        gmail_refresh_token="fake-refresh",
        gmail_sender_email="iou@example.com",
        reminder_signing_key="k" * 32,
        gmail_recipient_allowlist=["friend@example.com"],
        reminder_public_base_url="https://api.iou.example/api",
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    mock = Mailer()
    monkeypatch.setattr(gmail, "get_mailer", lambda: mock)
    api.settings = settings
    api.mail = mock
    return mock


def setup(api, kind="money", **changes):
    friend = new_friend(api, email="friend@example.com")
    loan = new_loan(api, friend["id"], kind, **changes)
    result = api.client.put(
        f"/friends/{friend['id']}/reminder-preferences",
        json={"recipient_email": friend["email"], "permission_confirmed": True},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 201, result.text
    return friend, loan


def preview(api, friend, **body):
    result = post(api, f"/friends/{friend['id']}/reminder-previews", body)
    assert result.status_code == 201, result.text
    return result.json()


def send(api, row, key=None, **changes):
    return post(
        api,
        f"/reminders/{row['id']}/send",
        {"approved": True, "recipient_email": row["recipient_email"], **changes},
        key,
    )


def token(row):
    link = row["body"].split("Stop IOU reminders: ")[1]
    return parse_qs(urlsplit(link).query)["token"][0]


@pytest.mark.parametrize("tone", ["friendly", "playful", "direct"])
def test_preview_presets_are_short_approved_exact_messages(api, mail, tone):
    friend, _ = setup(api)
    row = preview(api, friend, tone=tone)
    assert row["status"] == "preview" and "$50.00" in row["body"]
    assert "fake" not in row["body"] and "credit" not in row["body"]
    assert row["recipient_email"] == friend["email"] and not mail.sent
    result = send(api, row)
    assert result.status_code == 202, result.text
    assert (
        result.json()["status"] == "sent"
        and result.json()["provider_message_id"] == "fake-message-id"
    )
    assert len(mail.sent) == 1 and mail.sent[0].body == row["body"]
    assert api.client.get(f"/reminders/{row['id']}").json()["status"] == "sent"
    assert api.client.get("/reminders").json()["items"][0]["id"] == row["id"]


def test_retries_do_not_duplicate_and_keys_bind_preview(api, mail):
    friend, _ = setup(api)
    row, other = preview(api, friend), preview(api, friend, tone="playful")
    key = uuid4()
    assert send(api, row, key).json()["status"] == "sent"
    assert send(api, row, key).json()["status"] == "sent"
    assert send(api, other, key).status_code == 409
    assert send(api, row).status_code == 409
    assert len(mail.sent) == 1
    assert send(api, other).status_code == 429


def test_preview_receipt_replays_without_another_record(api, mail):
    friend, _ = setup(api)
    key = uuid4()
    a = post(api, f"/friends/{friend['id']}/reminder-previews", {"tone": "direct"}, key)
    b = post(api, f"/friends/{friend['id']}/reminder-previews", {"tone": "direct"}, key)
    assert a.json() == b.json() and b.headers["idempotency-replayed"] == "true"
    assert len(api.client.get("/reminders").json()["items"]) == 1


@pytest.mark.parametrize("kind", ["money", "item"])
def test_settled_friend_is_not_eligible(api, mail, kind):
    friend, loan = setup(api, kind)
    path = "repayments" if kind == "money" else "return"
    assert (
        post(
            api, f"/loans/{loan['id']}/{path}", {"amount_cents": 5000} if kind == "money" else None
        ).status_code
        == 201
    )
    assert post(api, f"/friends/{friend['id']}/reminder-previews", {}).status_code == 409
    assert not mail.sent


def test_zero_cash_item_and_returned_item_with_fees_are_eligible(api, mail):
    friend, loan = setup(api, "item", due_date="2026-01-09", late_fee_cents=200)
    row = preview(api, friend)
    assert "1 borrowed item" in row["body"] and "$2.00" in row["body"]
    post(api, f"/loans/{loan['id']}/return")
    assert send(api, row).status_code == 409
    current = preview(api, friend)
    assert "borrowed item" not in current["body"] and "$2.00" in current["body"]
    assert send(api, current).json()["status"] == "sent"


def test_stale_balances_expiry_wrong_approval_and_quiet_hours(api, mail, monkeypatch):
    from iou.ledger import service as ledger

    friend, loan = setup(api)
    row = preview(api, friend)
    assert send(api, row, approved=False).status_code == 422
    assert send(api, row, approved=1).status_code == 422
    assert send(api, row, recipient_email="else@example.com").status_code == 409
    post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 100})
    assert send(api, row).status_code == 409
    current = preview(api, friend)
    monkeypatch.setattr(ledger, "now_utc", lambda: NOW + timedelta(minutes=10))
    assert send(api, current).status_code == 409
    monkeypatch.setattr(ledger, "now_utc", lambda: NOW.replace(hour=20))
    late = preview(api, friend)
    assert send(api, late).status_code == 409
    assert not mail.sent


def test_permission_missing_changed_address_and_archival_block(api, mail):
    friend = new_friend(api, email="friend@example.com")
    new_loan(api, friend["id"])
    assert post(api, f"/friends/{friend['id']}/reminder-previews", {}).status_code == 409
    pref = api.client.get(f"/friends/{friend['id']}/reminder-preferences").json()
    assert not pref["permission_confirmed"]
    api.client.put(
        f"/friends/{friend['id']}/reminder-preferences",
        json={"recipient_email": friend["email"], "permission_confirmed": True},
        headers={"Idempotency-Key": str(uuid4())},
    )
    api.client.patch(f"/friends/{friend['id']}", json={"email": "changed@example.com"})
    assert post(api, f"/friends/{friend['id']}/reminder-previews", {}).status_code == 409
    api.client.post(f"/friends/{friend['id']}/archive")
    assert post(api, f"/friends/{friend['id']}/reminder-previews", {}).status_code == 409


def test_final_recheck_after_token_exchange_cancels_without_email(api, mail):
    friend, loan = setup(api)
    row = preview(api, friend)
    mail.on_prepare = lambda: post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 5000})
    result = send(api, row)
    assert result.status_code == 202 and result.json()["status"] == "cancelled"
    assert not mail.sent


@pytest.mark.parametrize(
    "failure,status", [("prepare", "failed"), ("reject", "failed"), ("uncertain", "uncertain")]
)
def test_provider_failures_record_safe_status_without_resending(api, mail, failure, status):
    friend, _ = setup(api)
    row = preview(api, friend)
    mail.failure = failure
    key = uuid4()
    result = send(api, row, key)
    assert result.status_code == 202 and result.json()["status"] == status
    count = len(mail.sent)
    assert send(api, row, key).json()["status"] == status and len(mail.sent) == count
    assert "fake-secret" not in result.text and "fake-refresh" not in result.text
    if status == "uncertain":
        assert send(api, preview(api, friend)).status_code == 429
    else:
        mail.failure = None
        assert send(api, preview(api, friend)).json()["status"] == "sent"


def test_optout_get_is_safe_post_is_global_and_cannot_be_overridden(api, mail):
    friend, _ = setup(api)
    row = preview(api, friend)
    link_token = token(row)
    assert api.client.get("/reminders/unsubscribe", params={"token": link_token}).status_code == 200
    assert not api.client.get(f"/friends/{friend['id']}/reminder-preferences").json()["opted_out"]
    for _ in range(2):
        assert (
            api.client.post("/reminders/unsubscribe", data={"token": link_token}).status_code == 200
        )
    assert send(api, row).status_code == 409
    api.user = Identity(uuid4(), None, "Other owner")
    another, _ = setup(api)  # Same email, another owner's contact.
    assert post(api, f"/friends/{another['id']}/reminder-previews", {}).status_code == 409
    assert not mail.sent


def test_unsubscribe_during_prepare_is_rechecked(api, mail):
    friend, _ = setup(api)
    row = preview(api, friend)
    mail.on_prepare = lambda: api.client.post("/reminders/unsubscribe", data={"token": token(row)})
    assert send(api, row).json()["status"] == "cancelled"
    assert not mail.sent


def test_disabled_and_demo_allowlist_fail_closed(api, mail):
    friend, _ = setup(api)
    row = preview(api, friend)
    api.settings.email_mode = "disabled"
    assert send(api, row).status_code == 503
    api.settings.email_mode = "gmail"
    api.settings.gmail_recipient_allowlist = []
    assert send(api, row).status_code == 403
    assert not mail.sent


def test_owner_isolation(api, mail):
    friend, _ = setup(api)
    row = preview(api, friend)
    api.user = Identity(uuid4(), None, "Other")
    assert api.client.get(f"/reminders/{row['id']}").status_code == 404
    assert send(api, row).status_code == 404
    assert post(api, f"/friends/{friend['id']}/reminder-previews", {}).status_code == 404
    assert api.client.get(f"/friends/{friend['id']}/reminder-preferences").status_code == 404
    assert api.client.get("/reminders").json()["items"] == []


def test_global_cooldown_covers_duplicate_contacts(api, mail):
    friend, _ = setup(api)
    assert send(api, preview(api, friend)).json()["status"] == "sent"
    duplicate, _ = setup(api)
    assert send(api, preview(api, duplicate)).status_code == 429


def test_history_pages_and_invalid_input(api, mail):
    friend, _ = setup(api)
    for tone in ("friendly", "playful", "direct"):
        preview(api, friend, tone=tone)
    assert len(api.client.get("/reminders?limit=1&offset=1").json()["items"]) == 1
    assert api.client.get("/reminders?limit=1").json()["has_more"]
    assert api.client.get("/reminders?offset=100001").status_code == 422
    assert api.client.get("/reminders?limit=101").status_code == 422
    for body in ({"tone": "threatening"}, {"tone": "friendly", "body": "arbitrary spam"}):
        assert post(api, f"/friends/{friend['id']}/reminder-previews", body).status_code == 422
    for bad in ("bad", "v1." + "0" * 64 + "." + "0" * 64, "v1." + "0" * 64 + "." + "漢" * 64):
        assert api.client.post("/reminders/unsubscribe", data={"token": bad}).status_code == 400


def test_zero_cash_unreturned_item_is_eligible(api, mail):
    friend, _ = setup(api, "item")
    row = preview(api, friend)
    assert "1 borrowed item" in row["body"] and "$" not in row["body"]
    assert send(api, row).json()["status"] == "sent"


def test_unsubscribe_configuration_and_lender_name_changes_need_new_approval(api, mail):
    friend, _ = setup(api)
    row = preview(api, friend)
    api.settings.reminder_public_base_url = "https://new-api.example/api"
    assert send(api, row).status_code == 409
    current = preview(api, friend)
    assert api.client.patch("/me", json={"display_name": "New name"}).status_code == 200
    assert send(api, current).status_code == 409
    assert not mail.sent


def test_nonself_email_requires_public_unsubscribe_url(api, mail):
    friend, _ = setup(api)
    api.settings.reminder_public_base_url = "http://127.0.0.1:8000"
    row = preview(api, friend)
    assert send(api, row).status_code == 503
    assert not mail.sent


def test_stale_submitted_claim_becomes_uncertain_without_a_retry(api, mail, monkeypatch):
    from iou.ledger import service as ledger

    friend, _ = setup(api)
    old = preview(api, friend)
    with Session(api.engine) as session:
        record = session.get(Reminder, UUID(old["id"]))
        record.status, record.send_key, record.attempted_at = "sending", uuid4(), NOW
        target = service.recipient(session, record.recipient_hash)
        target.in_flight, target.last_attempt_at = record.id, NOW
        session.commit()
    monkeypatch.setattr(ledger, "now_utc", lambda: NOW + timedelta(minutes=6))
    assert send(api, preview(api, friend)).status_code == 429
    assert api.client.get(f"/reminders/{old['id']}").json()["status"] == "uncertain"
    assert not mail.sent


def test_sent_replay_stays_readable_when_email_is_disabled(api, mail):
    friend, _ = setup(api)
    row = preview(api, friend)
    key = uuid4()
    assert send(api, row, key).json()["status"] == "sent"
    api.settings.email_mode = "disabled"
    assert send(api, row, key).json()["status"] == "sent"
    assert len(mail.sent) == 1


def test_reserved_crash_can_expire_without_resending_old_attempt(api, mail, monkeypatch):
    from iou.ledger import service as ledger

    friend, _ = setup(api)
    old = preview(api, friend)
    with Session(api.engine) as session:
        record = session.get(Reminder, UUID(old["id"]))
        record.status, record.send_key = "reserved", uuid4()
        target = service.recipient(session, record.recipient_hash)
        target.in_flight = record.id
        session.commit()
    monkeypatch.setattr(ledger, "now_utc", lambda: NOW + timedelta(minutes=6))
    assert send(api, preview(api, friend)).json()["status"] == "sent"
    assert api.client.get(f"/reminders/{old['id']}").json()["status"] == "cancelled"
    assert len(mail.sent) == 1


@pytest.mark.parametrize(
    "path",
    [
        "/reminders",
        "/reminders/00000000-0000-0000-0000-000000000000",
        "/friends/00000000-0000-0000-0000-000000000000/reminder-preferences",
    ],
)
def test_protected_reads_require_auth(api, path):
    from iou.api import app

    del app.dependency_overrides[get_current_user]
    assert api.client.get(path).status_code == 401
