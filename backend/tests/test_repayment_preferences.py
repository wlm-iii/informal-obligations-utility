"""Preference metadata must not replace the existing financial contract."""

import hashlib
import json
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from test_ledger import api as api
from test_ledger import new_friend, new_loan, post

from iou.ledger.models import MutationReceipt


def test_preferences_round_trip_without_changing_charge_allocation(api):
    friend = new_friend(api)
    loan = new_loan(
        api,
        friend["id"],
        repayment_type="item",
        principal_cents=10000,
        interest_rate_bps=1000,
        interest_period="weekly",
        lent_at="2026-01-03T12:00:00Z",
    )
    assert loan["repayment_type"] == "item" and loan["interest_cents"] == 1000
    assert loan["outstanding_cents"] == 10000 and loan["total_outstanding_cents"] == 11000
    paid = post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 11000})
    assert paid.status_code == 201
    assert paid.json()["event"]["interest_applied_cents"] == 1000
    assert paid.json()["loan"]["status"] == "completed"


@pytest.mark.parametrize(
    "changes",
    [
        dict(repayment_type="other"),
        dict(repayment_other="Dinner"),
        dict(repayment_type="money", repayment_other="Dinner"),
        dict(repayment_type="cash"),
        dict(interest_percent=10),
    ],
)
def test_invalid_or_obsolete_preference_contract_is_rejected(api, changes):
    friend = new_friend(api)
    body = {
        "friend_id": friend["id"],
        "kind": "money",
        "description": "Lunch",
        "principal_cents": 5000,
        "due_date": "2026-01-20",
        **changes,
    }
    assert post(api, "/loans", body).status_code == 422


def test_item_preference_never_turns_item_into_cash(api):
    loan = new_loan(
        api, new_friend(api)["id"], "item", repayment_type="other", repayment_other="Dinner"
    )
    assert loan["principal_cents"] is None and loan["repayment_other"] == "Dinner"
    assert post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 1}).status_code == 409
    assert post(api, f"/loans/{loan['id']}/return").json()["loan"]["status"] == "completed"


def test_preference_defaults_preserve_level3_creation_receipt(api):
    body = {
        "friend_id": new_friend(api)["id"],
        "kind": "money",
        "description": "Old API",
        "principal_cents": 5000,
        "due_date": "2026-01-20",
    }
    key = uuid4()
    first = post(api, "/loans", body, key)
    # Previous canonical DTO includes Level 3 terms, but no preference properties.
    canonical = {
        **body,
        "notes": None,
        "lent_at": None,
        "currency": "USD",
        "late_fee_cents": 0,
        "grace_days": 0,
        "charge_cap_cents": None,
        "interest_rate_bps": 0,
        "interest_period": "weekly",
    }
    digest = hashlib.sha256(
        json.dumps(
            {"operation": "create-loan", "body": canonical}, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    with Session(api.engine) as session:
        session.get(MutationReceipt, (api.user.id, key)).request_hash = digest
        session.commit()
    assert post(api, "/loans", body, key).json() == first.json()
    assert post(api, "/loans", {**body, "repayment_type": "money"}, key).status_code == 409
