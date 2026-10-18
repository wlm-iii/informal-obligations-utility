"""Opt-in, atomic demo seeding for the configured Gmail sender's existing IOU profile.

Dry-run by default. Never creates Auth users, sends mail, grants consent, resets
cooldowns, deletes data, changes profiles, or runs migrations. All ledger writes
use normal domain operations and deterministic, owner-scoped receipt keys.
"""

import argparse
import json
from datetime import date, datetime, time, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from iou.auth import Identity
from iou.database import get_engine
from iou.evidence import models as evidence_models  # noqa: F401 -- register audit FK metadata
from iou.ledger import corrections, service
from iou.ledger.models import MutationReceipt
from iou.ledger.schemas import (
    CorrectionInput,
    FriendCreate,
    ItemLoanCreate,
    MoneyLoanCreate,
    ReasonInput,
    RepaymentCreate,
    SettlementInput,
    WaiverCreate,
)
from iou.profiles import Profile

TAG = "iou-sender-demo-v1"


def key(owner: UUID, label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"{TAG}:{owner}:{label}")


def seed(session: Session, user: Identity, sender: str) -> dict:
    """Caller owns an outer transaction; Session commits must only release savepoints."""
    if (
        session.join_transaction_mode != "create_savepoint"
        or not isinstance(session.bind, Connection)
        or not session.bind.in_transaction()
    ):
        raise ValueError("Seeding requires an outer transaction and create_savepoint session.")
    profile = session.scalar(select(Profile).where(Profile.id == user.id).with_for_update())
    if profile is None:
        raise ValueError("Sign into IOU and open Tracker first; an existing profile is required.")
    if not user.email or user.email.lower() != sender.lower():
        raise ValueError("Only the configured sender's own profile may be seeded.")
    receipt = session.get(MutationReceipt, (user.id, key(user.id, "friend:alex")))
    if receipt:
        metadata = json.loads(receipt.payload["notes"])
    else:
        metadata = {
            "seed": TAG,
            "anchor": service.now_utc().astimezone(ZoneInfo(profile.timezone)).date().isoformat(),
            "timezone": profile.timezone,
            "notice": "Fictional demo records. All email goes only to the sender's own inbox.",
        }
    if metadata["seed"] != TAG:
        raise ValueError("Seed manifest does not match this version.")
    anchor = date.fromisoformat(metadata["anchor"])
    zone = ZoneInfo(metadata["timezone"])
    notes = json.dumps(metadata, sort_keys=True)
    results = {"created_operations": 0, "replayed_operations": 0, "friends": [], "loans": []}

    def day(offset):
        return datetime.combine(anchor + timedelta(days=offset), time(12), zone)

    def mutate(label, operation, body, work):
        response = service.mutate(session, user, key(user.id, label), operation, body, work)
        replayed = response.headers["Idempotency-Replayed"] == "true"
        results["replayed_operations" if replayed else "created_operations"] += 1
        return json.loads(response.body)

    friends = {}
    for name in ("Alex", "Blair", "Casey", "Drew", "Emery", "Finley"):
        body = FriendCreate(display_name=f"[DEMO] {name}", email=sender, notes=notes)
        result = mutate(
            f"friend:{name.lower()}",
            "create-friend",
            body,
            lambda owner, body=body: service.create_friend(session, owner.id, body),
        )
        friends[name] = UUID(result["id"])
        results["friends"].append(result["id"])

    def loan(label, name, description, lent, due, cents=None, **terms):
        fields = dict(
            friend_id=friends[name],
            description=f"[DEMO] {description}",
            notes="Fictional demonstration only; no real money or property changed hands.",
            lent_at=day(lent),
            due_date=anchor + timedelta(days=due),
            **terms,
        )
        body = (
            MoneyLoanCreate(kind="money", principal_cents=cents, **fields)
            if cents is not None
            else ItemLoanCreate(kind="item", **fields)
        )
        result = mutate(
            f"loan:{label}",
            "create-loan",
            body,
            lambda owner: service.create_loan(session, owner, body),
        )
        results["loans"].append(result["id"])
        return UUID(result["id"])

    def event(label, loan_id, action, effective, amount=None, **extra):
        fields = dict(effective_at=day(effective), note="Fictional demo event.", **extra)
        body = (
            WaiverCreate(amount_cents=amount, **fields)
            if action == "waiver"
            else RepaymentCreate(amount_cents=amount, **fields)
            if amount is not None
            else SettlementInput(**fields)
        )
        operation = {"repayment": "repay", "fee_payment": "fee-payment"}.get(action, action)
        return mutate(
            f"event:{label}",
            f"{operation}:{loan_id}",
            body,
            lambda owner: service.settle(session, owner.id, loan_id, body, action),
        )

    # Reliable borrower: three on-time completions plus a new zero-penalty IOU.
    first = loan("alex-train", "Alex", "Train tickets", -180, -165, 1800)
    event("alex-train-paid", first, "repayment", -170, 1800)
    first = loan("alex-dinner", "Alex", "Dinner split", -60, -50, 3200)
    event("alex-dinner-paid", first, "repayment", -55, 3200)
    first = loan("alex-charger", "Alex", "USB-C charger", -40, -30)
    event("alex-charger-returned", first, "return", -35)
    loan("alex-groceries", "Alex", "Groceries", -5, 9, 2450, repayment_type="money")

    # Mixed track record; an overdue charged loan reaches its explicit lifetime cap.
    first = loan("blair-concert", "Blair", "Concert ticket", -80, -70, 4500)
    event("blair-concert-paid", first, "repayment", -72, 4500)
    first = loan("blair-lunch", "Blair", "Lunch split paid late", -55, -45, 2800)
    event("blair-lunch-paid", first, "repayment", -42, 2800)
    first = loan("blair-game", "Blair", "Board game", -35, -25)
    event("blair-game-returned", first, "return", -27)
    loan(
        "blair-weekend",
        "Blair",
        "Weekend tickets; capped charges",
        -20,
        -6,
        8500,
        interest_rate_bps=200,
        interest_period="weekly",
        late_fee_cents=250,
        grace_days=1,
        charge_cap_cents=500,
    )

    # Partial repayment with monthly interest; another IOU is overdue but still in grace.
    first = loan(
        "casey-travel",
        "Casey",
        "Travel split; partial repayment",
        -25,
        4,
        12000,
        interest_rate_bps=125,
        interest_period="monthly",
        repayment_type="money",
    )
    event("casey-travel-part", first, "repayment", -15, 3500)
    loan(
        "casey-lunch",
        "Casey",
        "Lunch; late but inside grace period",
        -4,
        -1,
        1600,
        late_fee_cents=150,
        grace_days=3,
    )
    first = loan("casey-tripod", "Casey", "Camera tripod", -65, -55)
    event("casey-tripod-returned", first, "return", -58)

    # Borrowing and financial settlement are separate: a returned item retains fees.
    loan(
        "drew-headphones",
        "Drew",
        "Noise-cancelling headphones; overdue",
        -18,
        -3,
        late_fee_cents=500,
        grace_days=1,
        repayment_type="item",
    )
    loan("drew-game", "Drew", "Strategy board game; due soon", -4, 5)
    first = loan(
        "drew-lantern",
        "Drew",
        "Camping lantern; returned with unpaid fee",
        -30,
        -20,
        late_fee_cents=300,
    )
    event("drew-lantern-returned", first, "return", -17)
    event("drew-lantern-fee-part", first, "fee_payment", -16, 100)

    # Fully settled friend, four on-time completions, and no eligibility for a nudge.
    for label, description, lent, due, paid, cents in (
        ("bus", "Bus fare", -120, -110, -115, 750),
        ("groceries", "Groceries", -45, -35, -37, 4200),
        ("movie", "Movie ticket", -14, -7, -10, 1500),
    ):
        first = loan(f"emery-{label}", "Emery", description, lent, due, cents)
        event(f"emery-{label}-paid", first, "repayment", paid, cents)
    first = loan("emery-book", "Emery", "Textbook", -28, -20)
    event("emery-book-returned", first, "return", -21)

    # Courtesy waiver is not cash; other repayment preference is metadata, not a write-off.
    first = loan(
        "finley-tickets", "Finley", "Tickets; late fee waived", -12, -4, 6000, late_fee_cents=200
    )
    event(
        "finley-fee-waived",
        first,
        "waiver",
        -1,
        200,
        component="fees",
        reason="Demo courtesy waiver; principal is still owed.",
    )
    first = loan(
        "finley-power-bank", "Finley", "Power bank; returned late without penalties", -9, -2
    )
    event("finley-power-bank-returned", first, "return", -1)
    loan(
        "finley-coffee",
        "Finley",
        "Coffee; other repayment preference",
        -1,
        6,
        925,
        repayment_type="other",
        repayment_other="Discuss over coffee; no automatic write-off.",
    )

    # Auditable correction with daily interest, plus a voided duplicate excluded from totals.
    first = loan(
        "casey-correction",
        "Casey",
        "Grocery split; corrected payment",
        -8,
        7,
        5000,
        interest_rate_bps=10,
        interest_period="daily",
    )
    original = event("casey-original-payment", first, "repayment", -4, 1000)
    original_id = UUID(original["event"]["id"])
    body = CorrectionInput(
        reason="Demo correction: recorded $10 instead of $15.",
        replacement={
            "action": "repayment",
            "amount_cents": 1500,
            "effective_at": day(-4),
            "note": "Fictional corrected payment.",
        },
    )
    mutate(
        "correct:casey-payment",
        f"correct:{first}:{original_id}",
        body,
        lambda owner: corrections.reverse_or_correct(session, owner.id, first, original_id, body),
    )
    duplicate = loan("finley-voided", "Finley", "Accidental duplicate; voided", -3, 8, 2500)
    body = ReasonInput(reason="Demo duplicate entry; not an actual obligation.")
    mutate(
        "void:finley-duplicate",
        f"void:{duplicate}",
        body,
        lambda owner: corrections.void_loan(session, owner.id, duplicate, body),
    )
    results["anchor"] = anchor.isoformat()
    return results


def apply(engine, user: Identity, sender: str) -> dict:
    # Normal ledger commits release nested savepoints, not this all-or-nothing transaction.
    with engine.begin() as connection:
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            return seed(session, user, sender)


def main():
    from iou.config import get_settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Write the explicitly confirmed dataset."
    )
    parser.add_argument(
        "--confirm-owner", type=UUID, help="Must match the configured sender's Auth UUID."
    )
    args = parser.parse_args()
    settings = get_settings()
    sender = str(settings.gmail_sender_email or "").strip().lower()
    if not sender:
        parser.error("Configure the Gmail sender address first. No writes performed.")
    engine = get_engine()
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            rows = connection.execute(
                text(
                    "SELECT p.id, p.display_name FROM auth.users u "
                    "JOIN iou_app.profiles p ON p.id=u.id "
                    "WHERE lower(u.email)=:email"
                ),
                {"email": sender},
            ).all()
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if len(rows) != 1:
            parser.error("Sender must sign into IOU and open Tracker first. No writes performed.")
        if revision != "0008_repayment_preferences":
            parser.error(
                "Unexpected database revision; review migrations separately. No writes performed."
            )
        owner = rows[0]
        print(f"Target: existing sender profile {owner.id}; dataset {TAG}.")
        print("6 demo friends, 23 loans, 18 events, 2 audits. No email or consent changes.")
        if not args.apply:
            print(
                "Dry run only. Apply with --apply --confirm-owner <UUID> after checking the target."
            )
            return
        if args.confirm_owner != owner.id:
            parser.error("--confirm-owner must match the sender profile UUID. No writes performed.")
        result = apply(engine, Identity(owner.id, sender, owner.display_name), sender)
        print(
            f"Applied atomically: {result['created_operations']} created operations; "
            f"{result['replayed_operations']} replayed; anchor {result['anchor']}."
        )
    except (ValueError, KeyError) as error:
        raise SystemExit(str(error)) from None
    except Exception as error:
        # Database exceptions may contain credentials, hostnames, or private parameter values.
        raise SystemExit(
            f"Seed failed ({type(error).__name__}); transaction rolled back. "
            "Inspect privately; do not paste database errors or credentials."
        ) from None


if __name__ == "__main__":
    main()
