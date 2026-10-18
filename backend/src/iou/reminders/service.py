"""Manual reminders with durable claims. Never perform provider I/O under a DB lock."""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from iou.auth import Identity
from iou.config import get_settings
from iou.ledger import service as ledger
from iou.ledger.models import Loan
from iou.profiles import Profile
from iou.reminders import gmail, templates
from iou.reminders.models import Permission, Recipient, Reminder
from iou.reminders.schemas import PermissionRead, ReminderRead


@dataclass(frozen=True)
class Envelope:
    id: UUID
    recipient_email: str
    subject: str
    body: str


def normalize(email):
    return str(email).strip().casefold()


def address_hash(email):
    return hashlib.sha256(normalize(email).encode()).hexdigest()


def recipient(session, identity):
    row = session.scalar(
        select(Recipient)
        .where(Recipient.id == identity)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        try:
            with session.begin_nested():
                session.add(Recipient(id=identity))
                session.flush()
        except IntegrityError:
            pass  # Another owner may have first registered the same address.
        row = session.scalar(
            select(Recipient)
            .where(Recipient.id == identity)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    return row


def signing_key():
    key = get_settings().reminder_signing_key
    if key is None:
        raise HTTPException(503, "Reminder signing is not configured.")
    return key.get_secret_value().encode()


def unsubscribe_token(identity):
    message = f"v1.{identity}"
    return message + "." + hmac.new(signing_key(), message.encode(), hashlib.sha256).hexdigest()


def verify_token(token):
    if len(token) != 132:
        raise HTTPException(400, "Invalid unsubscribe link.")
    version, identity, signature = token.split(".") if token.count(".") == 2 else ("", "", "")
    if (
        version != "v1"
        or len(identity) != 64
        or len(signature) != 64
        or any(c not in "0123456789abcdef" for c in identity + signature)
        or not hmac.compare_digest(unsubscribe_token(identity), token)
    ):
        raise HTTPException(400, "Invalid unsubscribe link.")
    return identity


def unsubscribe(session, token):
    identity = verify_token(token)
    row = recipient(session, identity)
    row.opted_out_at = row.opted_out_at or ledger.now_utc()
    session.commit()


def permission_read(session, owner, friend):
    pref = session.scalar(
        select(Permission).where(Permission.owner_id == owner, Permission.friend_id == friend.id)
    )
    email = normalize(friend.email) if friend.email else None
    suppression = session.get(Recipient, address_hash(email)) if email else None
    confirmed = bool(
        pref
        and pref.confirmed_at
        and pref.recipient_email == email
        and ledger.utc(pref.contact_updated_at) == ledger.utc(friend.updated_at)
    )
    return PermissionRead(
        friend_id=friend.id,
        recipient_email=email,
        permission_confirmed=confirmed,
        opted_out=bool(suppression and suppression.opted_out_at),
    )


def update_permission(session, owner, friend_id, body):
    friend = ledger.friend_for_owner(session, owner, friend_id)
    if not friend.email or normalize(body.recipient_email) != normalize(friend.email):
        raise HTTPException(409, "Confirm the contact's current email address.")
    row = session.get(Permission, friend.id)
    if row is None:
        row = Permission(friend_id=friend.id, owner_id=owner)
        session.add(row)
    row.recipient_email = normalize(friend.email)
    row.contact_updated_at = friend.updated_at
    row.confirmed_at = ledger.now_utc() if body.permission_confirmed else None
    session.flush()
    return permission_read(session, owner, friend)


def allowed(session, owner, friend_id):
    friend = ledger.friend_for_owner(session, owner, friend_id)
    if friend.archived_at or not friend.email:
        raise HTTPException(409, "An active contact with an email address is required.")
    pref = permission_read(session, owner, friend)
    if pref.opted_out:
        raise HTTPException(409, "Recipient has opted out of IOU reminders.")
    if not pref.permission_confirmed:
        raise HTTPException(409, "Recipient permission must be confirmed for this contact.")
    return friend


def snapshot(session, owner, friend, at):
    loans = [
        ledger.loan_read(row, at)
        for row in session.execute(ledger.loan_query(owner).where(Loan.friend_id == friend.id))
    ]
    active = [
        loan
        for loan in loans
        if loan.status != "voided"
        and (loan.total_outstanding_cents > 0 or loan.borrowing_status == "outstanding")
    ]
    if not active:
        raise HTTPException(409, "This friend has no outstanding obligations.")
    # Only message-relevant current facts, never photos, notes, or fictional scores.
    facts = [
        {
            "id": str(loan.id),
            "due_date": str(loan.due_date),
            "kind": loan.kind,
            "principal": loan.outstanding_cents,
            "interest": loan.interest_cents,
            "fees": loan.fees_cents,
            "borrowing": loan.borrowing_status,
        }
        for loan in sorted(active, key=lambda loan: loan.id)
    ]
    digest = hashlib.sha256(
        json.dumps(
            {
                "friend": friend.display_name,
                "lender": session.get(Profile, owner).display_name,
                "email": normalize(friend.email),
                "loans": facts,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return (
        digest,
        sum(loan.total_outstanding_cents for loan in active),
        sum(loan.kind == "item" and loan.borrowing_status == "outstanding" for loan in active),
    )


def create_preview(session, owner, friend_id, body):
    friend = allowed(session, owner, friend_id)
    now = ledger.now_utc()
    digest, cents, items = snapshot(session, owner, friend, now)
    identity = address_hash(friend.email)
    recipient(session, identity)
    link = (
        f"{get_settings().reminder_public_base_url}/reminders/unsubscribe"
        f"?token={unsubscribe_token(identity)}"
    )
    text = templates.render(
        body.tone,
        body.template_id,
        friend.display_name,
        session.get(Profile, owner).display_name,
        cents,
        items,
    )
    text += (
        "\n\nSent through IOU on your contact's behalf; amounts and returns are manually recorded."
        f"\nStop IOU reminders: {link}"
    )
    row = Reminder(
        id=uuid4(),
        owner_id=owner,
        friend_id=friend_id,
        recipient_hash=identity,
        recipient_email=normalize(friend.email),
        tone=body.tone,
        subject="A friendly IOU reminder",
        body=text,
        snapshot_hash=digest,
        status="preview",
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    session.add(row)
    session.flush()
    return ReminderRead.model_validate(row)


def owned(session, owner, identity):
    row = session.scalar(
        select(Reminder)
        .where(Reminder.id == identity, Reminder.owner_id == owner)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "Reminder not found.")
    return row


def validate_live_recipient(email):
    settings = get_settings()
    if settings.email_mode != "gmail":
        raise HTTPException(503, "Email sending is disabled.")
    allowed_emails = {normalize(value) for value in settings.gmail_recipient_allowlist}
    allowed_emails.add(normalize(settings.gmail_sender_email))
    if not settings.gmail_allow_external_recipients and normalize(email) not in allowed_emails:
        raise HTTPException(403, "Recipient is outside the configured demo allowlist.")
    if normalize(email) != normalize(settings.gmail_sender_email) and urlsplit(
        settings.reminder_public_base_url
    ).hostname in ("localhost", "127.0.0.1"):
        raise HTTPException(503, "A public unsubscribe base URL is required for other recipients.")


def validate_preview(session, owner, row, profile, at):
    if at >= ledger.utc(row.expires_at):
        raise HTTPException(409, "Preview expired. Generate and approve a new preview.")
    friend = allowed(session, owner, row.friend_id)
    settings = get_settings()
    expected_footer = (
        f"Stop IOU reminders: {settings.reminder_public_base_url}"
        f"/reminders/unsubscribe?token={unsubscribe_token(row.recipient_hash)}"
    )
    if not row.body.endswith(expected_footer):
        raise HTTPException(409, "Reminder configuration changed. Generate a new preview.")
    digest, _, _ = snapshot(session, owner, friend, at)
    if row.recipient_email != normalize(friend.email) or digest != row.snapshot_hash:
        raise HTTPException(409, "Obligations changed. Generate and approve a new preview.")
    if get_settings().reminder_quiet_hours_enabled:
        hour = at.astimezone(ZoneInfo(profile.timezone)).hour
        if not 9 <= hour < 18:
            raise HTTPException(
                409, "Reminders may only be sent between 09:00 and 18:00 in your timezone."
            )
    validate_live_recipient(row.recipient_email)


def release_claim(target, row):
    if target.in_flight == row.id:
        target.in_flight = None


def stale_claim(session, target, at):
    if target.in_flight is None:
        return False
    old = session.get(Reminder, target.in_flight, populate_existing=True)
    if old and ledger.utc(old.updated_at) <= at - timedelta(minutes=5):
        if old.status in ("reserved", "sending"):
            old.status = "uncertain" if old.attempted_at else "cancelled"
            old.error_code = "stale_attempt"
            old.updated_at = at
        target.in_flight = None
        return True
    return False


def reserve(session, user, identity, body, key):
    profile = ledger.lock_owner(session, user)
    row = owned(session, user.id, identity)
    replay = session.scalar(
        select(Reminder).where(Reminder.owner_id == user.id, Reminder.send_key == key)
    )
    if replay is not None:
        if (
            replay.id != identity
            or normalize(body.recipient_email) != replay.recipient_email
            or not body.approved
        ):
            raise HTTPException(409, "Send key was used for another request.")
        result = ReminderRead.model_validate(replay)
        session.rollback()
        return result, False
    if not body.approved:
        raise HTTPException(422, "Explicit approval of the displayed preview is required.")
    if row.status != "preview":
        raise HTTPException(
            409, "This preview already has a send attempt. Inspect delivery history."
        )
    if normalize(body.recipient_email) != row.recipient_email:
        raise HTTPException(409, "Approve the exact recipient shown in the preview.")
    at = ledger.now_utc()
    target = recipient(session, row.recipient_hash)
    validate_preview(session, user.id, row, profile, at)
    if target.opted_out_at:
        raise HTTPException(409, "Recipient has opted out of IOU reminders.")
    recovered = stale_claim(session, target, at)
    if target.in_flight or (
        target.last_attempt_at and at < ledger.utc(target.last_attempt_at) + timedelta(hours=24)
    ):
        if recovered:
            session.commit()  # Persist uncertainty/recovery without authorizing a new send.
        raise HTTPException(
            429, "One reminder per recipient per 24 hours; another attempt may be in progress."
        )
    row.send_key, row.status, row.updated_at = key, "reserved", at
    target.in_flight = row.id
    result = ReminderRead.model_validate(row)
    session.commit()
    return result, True


def final_authorize(session, user, identity):
    profile = ledger.lock_owner(session, user)
    row = owned(session, user.id, identity)
    target = recipient(session, row.recipient_hash)
    at = ledger.now_utc()
    if row.status != "reserved" or target.in_flight != row.id:
        session.rollback()
        return None
    try:
        validate_preview(session, user.id, row, profile, at)
        if target.opted_out_at:
            raise HTTPException(409, "Recipient opted out.")
    except HTTPException:
        row.status, row.error_code, row.updated_at = "cancelled", "eligibility_changed", at
        release_claim(target, row)
        session.commit()
        return None
    row.status, row.attempted_at, row.updated_at = "sending", at, at
    target.last_attempt_at = at
    envelope = Envelope(row.id, row.recipient_email, row.subject, row.body)
    session.commit()
    return envelope


def finish(session, user, identity, status, code=None, provider_id=None):
    ledger.lock_owner(session, user)
    row = owned(session, user.id, identity)
    target = recipient(session, row.recipient_hash)
    if row.status in ("reserved", "sending", "uncertain"):
        row.status, row.error_code = status, code
        row.provider_message_id = provider_id
        row.updated_at = ledger.now_utc()
        if status == "sent":
            row.sent_at = row.updated_at
        if status == "failed" and target.in_flight == row.id:
            target.last_attempt_at = None  # Definite rejection, not uncertain acceptance.
        release_claim(target, row)
    result = ReminderRead.model_validate(row)
    session.commit()
    return result


def send(session: Session, user: Identity, identity, body, key):
    result, dispatch = reserve(session, user, identity, body, key)
    if not dispatch:
        return result
    # No SQL transaction or owner lock is held during either provider operation.
    try:
        mailer = gmail.get_mailer()
        token = mailer.prepare()
    except (gmail.PreparationFailed, HTTPException):
        return finish(session, user, identity, "failed", "authorization_failed")
    envelope = final_authorize(session, user, identity)
    if envelope is None:
        return ReminderRead.model_validate(owned(session, user.id, identity))
    try:
        message_id = mailer.send(token, envelope)
    except gmail.Rejected:
        return finish(session, user, identity, "failed", "provider_rejected")
    except gmail.Uncertain:
        return finish(session, user, identity, "uncertain", "delivery_uncertain")
    return finish(session, user, identity, "sent", provider_id=message_id)
