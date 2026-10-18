"""Local-only self-addressed demo. No real email without --send AND typed approval.

Run with the backend interpreter and PYTHONPATH=backend/src. Never uses the hosted
DATABASE_URL from .env. The --migrate flag explicitly upgrades the selected local DB.
"""

import argparse
import json
import os
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from iou.auth import Identity
from iou.config import get_settings
from iou.database import get_engine
from iou.ledger import service as ledger
from iou.ledger.schemas import FriendCreate, MoneyLoanCreate
from iou.reminders import service
from iou.reminders.schemas import PermissionInput, PreviewInput, SendInput


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="postgresql+psycopg://iou@127.0.0.1:54329/iou")
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument(
        "--send",
        action="store_true",
        help="Allow one email to the configured sender, after typed approval",
    )
    args = parser.parse_args()
    url = make_url(args.database_url)
    if (
        url.host not in ("localhost", "127.0.0.1")
        or url.drivername != "postgresql+psycopg"
        or url.query
    ):
        parser.error(
            "Only loopback PostgreSQL is allowed. Never target Supabase or a shared database."
        )
    os.environ["DATABASE_URL"] = args.database_url
    os.environ["EMAIL_MODE"] = "gmail" if args.send else "disabled"
    # Self-addressed, explicitly approved demos may run at any hour. Normal API
    # reminders still enforce their configured quiet hours.
    os.environ["REMINDER_QUIET_HOURS_ENABLED"] = "false"
    get_settings.cache_clear()
    settings = get_settings()
    if not settings.gmail_sender_email or not settings.reminder_signing_key:
        parser.error("Set GMAIL_SENDER_EMAIL and REMINDER_SIGNING_KEY in root .env first.")
    if args.migrate:
        command.upgrade(Config(str(Path(__file__).resolve().parents[3] / "alembic.ini")), "head")
    user = Identity(uuid4(), str(settings.gmail_sender_email), "IOU self-test")
    with Session(get_engine()) as session:
        body = FriendCreate(
            display_name="Demo friend (your own inbox)", email=settings.gmail_sender_email
        )
        result = ledger.mutate(
            session,
            user,
            uuid4(),
            "create-friend",
            body,
            lambda owner: ledger.create_friend(session, owner.id, body),
        )
        friend_id = UUID(json.loads(result.body)["id"])
        now = ledger.now_utc()
        loan = MoneyLoanCreate(
            friend_id=friend_id,
            kind="money",
            description="Fictional self-test only",
            principal_cents=500,
            lent_at=now - timedelta(minutes=1),
            due_date=now.date() + timedelta(days=1),
        )
        ledger.mutate(
            session,
            user,
            uuid4(),
            "create-loan",
            loan,
            lambda owner: ledger.create_loan(session, owner, loan),
        )
        permission = PermissionInput(
            recipient_email=settings.gmail_sender_email, permission_confirmed=True
        )
        ledger.mutate(
            session,
            user,
            uuid4(),
            f"reminder-permission:{friend_id}",
            permission,
            lambda owner: service.update_permission(session, owner.id, friend_id, permission),
        )
        request = PreviewInput(tone="friendly")
        result = ledger.mutate(
            session,
            user,
            uuid4(),
            f"reminder-preview:{friend_id}",
            request,
            lambda owner: service.create_preview(session, owner.id, friend_id, request),
        )
        preview = json.loads(result.body)
        print(
            f"To: {preview['recipient_email']}\nSubject: {preview['subject']}\n\n"
            f"{preview['body']}\n"
        )
        if not args.send:
            print(
                "Preview only. No Google request or email was sent. "
                "Use --send for one self-addressed email."
            )
            return
        if input("Type SEND to approve this exact email to your own inbox: ").strip() != "SEND":
            print("Cancelled. No email sent.")
            return
        # Quiet hours can be explicitly disabled in .env for a consenting self-demo.
        result = service.send(
            session,
            user,
            UUID(preview["id"]),
            SendInput(approved=True, recipient_email=settings.gmail_sender_email),
            uuid4(),
        )
        print(f"Delivery status: {result.status}; code: {result.error_code or 'none'}")
        print("Same-recipient 24-hour cooldown applies across owners and duplicate demo contacts.")


if __name__ == "__main__":
    try:
        main()
    except HTTPException as error:
        raise SystemExit(f"Reminder blocked: {error.detail}") from None
