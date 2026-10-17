import hashlib
import json
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session
from test_ledger import NOW, new_friend, new_loan, post
from test_ledger import api as api

from iou.ledger import service
from iou.ledger.models import LoanEvent, MutationReceipt


def charged(api, **changes):
    defaults = dict(
        principal_cents=10000,
        lent_at="2026-01-03T12:00:00Z",
        due_date="2026-01-09",
        interest_rate_bps=1000,
        interest_period="weekly",
        late_fee_cents=200,
    )
    return new_loan(api, new_friend(api)["id"], **{**defaults, **changes})


def test_pre_level3_loan_creation_receipt_remains_replayable(api):
    friend = new_friend(api)
    body = {
        "friend_id": friend["id"],
        "kind": "money",
        "description": "Old loan",
        "principal_cents": 5000,
        "due_date": "2026-01-20",
        "lent_at": "2026-01-01T12:00:00Z",
    }
    key = uuid4()
    first = post(api, "/loans", body, key)
    canonical_old = {**body, "currency": "USD", "notes": None}
    legacy_hash = hashlib.sha256(
        json.dumps(
            {"operation": "create-loan", "body": canonical_old},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    with Session(api.engine) as session:
        receipt = session.get(MutationReceipt, (api.user.id, key))
        receipt.request_hash = legacy_hash
        session.commit()
    assert post(api, "/loans", body, key).json() == first.json()
    assert post(api, "/loans", {**body, "late_fee_cents": 100}, key).status_code == 409
    assert len(api.client.get("/loans").json()["items"]) == 1


def test_optional_terms_periodic_interest_and_payment_breakdown(api):
    loan = charged(api)
    assert loan["interest_cents"] == 1000 and loan["fees_cents"] == 200
    assert loan["total_outstanding_cents"] == 11200
    assert loan["charge_cap_cents"] == 10000 and loan["calculation_version"] == 1
    result = post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 1200})
    assert result.status_code == 201
    event = result.json()["event"]
    assert event["principal_applied_cents"] == 0
    assert event["interest_applied_cents"] == 1000 and event["fees_applied_cents"] == 200
    settled = post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 10000})
    assert settled.status_code == 201
    assert settled.json()["loan"]["status"] == "completed"
    assert api.client.get("/loans?status=open").json()["items"] == []
    assert len(api.client.get("/loans?status=completed").json()["items"]) == 1


def test_interest_and_late_fees_independently_optional(api):
    friend = new_friend(api)
    free = new_loan(api, friend["id"])
    assert free["interest_cents"] == free["fees_cents"] == 0
    rate_only = new_loan(
        api,
        friend["id"],
        principal_cents=10000,
        interest_rate_bps=100,
        interest_period="daily",
        due_date="2026-01-09",
    )
    assert rate_only["interest_cents"] == 900 and rate_only["fees_cents"] == 0
    fee_only = new_loan(api, friend["id"], late_fee_cents=100, due_date="2026-01-09")
    assert fee_only["fees_cents"] == 100 and fee_only["interest_cents"] == 0


def test_grace_snapshot_fee_idempotency_and_no_scheduler(api, monkeypatch):
    friend = new_friend(api)
    loan = new_loan(api, friend["id"], due_date="2026-01-09", grace_days=2, late_fee_cents=500)
    assert loan["overdue"] and loan["fees_cents"] == 0
    assert loan["fee_at"] == "2026-01-12T00:00:00Z"
    monkeypatch.setattr(service, "now_utc", lambda: NOW + timedelta(days=2))
    first = api.client.get(f"/loans/{loan['id']}").json()
    again = api.client.get(f"/loans/{loan['id']}").json()
    assert first == again and first["fees_cents"] == 500
    assert first["late_fee_assessed_at"] == "2026-01-12T00:00:00Z"


def test_waivers_are_auditable_reversible_and_do_not_restore_cap(api):
    loan = charged(api)
    key = uuid4()
    body = {"component": "interest", "amount_cents": 1000, "reason": "Friend discount"}
    first = post(api, f"/loans/{loan['id']}/waivers", body, key)
    assert first.status_code == 201
    assert post(api, f"/loans/{loan['id']}/waivers", body, key).json() == first.json()
    assert first.json()["loan"]["interest_cents"] == 0
    assert first.json()["loan"]["interest_waived_cents"] == 1000
    event = first.json()["event"]
    reverse = post(api, f"/loans/{loan['id']}/events/{event['id']}/reverse", {"reason": "Mistake"})
    assert reverse.status_code == 201 and reverse.json()["loan"]["interest_cents"] == 1000
    rows = api.client.get(f"/friends/{loan['friend_id']}/history").json()["items"]
    waiver = next(r for r in rows if r["action"] == "waiver")
    assert waiver["reason"] == "Friend discount" and waiver["reversed_at"] is not None


def test_item_return_and_fee_settlement_are_separate(api):
    loan = new_loan(api, new_friend(api)["id"], "item", due_date="2026-01-09", late_fee_cents=500)
    returned = post(api, f"/loans/{loan['id']}/return")
    assert returned.status_code == 201
    state = returned.json()["loan"]
    assert state["borrowing_status"] == "returned" and state["status"] == "open"
    assert not state["overdue"] and state["total_outstanding_cents"] == 500
    assert state["outstanding_cents"] is None
    assert api.client.get("/loans?overdue=true").json()["items"] == []
    paid = post(api, f"/loans/{loan['id']}/fee-payments", {"amount_cents": 500})
    assert paid.status_code == 201 and paid.json()["loan"]["status"] == "completed"
    assert paid.json()["event"]["fees_applied_cents"] == 500


def test_item_fee_can_be_waived_and_waiver_corrected(api):
    loan = new_loan(api, new_friend(api)["id"], "item", due_date="2026-01-09", late_fee_cents=500)
    post(api, f"/loans/{loan['id']}/return")
    waiver = post(
        api,
        f"/loans/{loan['id']}/waivers",
        {"component": "fees", "amount_cents": 500, "reason": "No worries"},
    ).json()
    assert waiver["loan"]["status"] == "completed"
    correction = post(
        api,
        f"/loans/{loan['id']}/events/{waiver['event']['id']}/correct",
        {
            "reason": "Only half",
            "replacement": {
                "action": "waiver",
                "component": "fees",
                "amount_cents": 250,
                "reason": "Half forgiven",
            },
        },
    )
    assert correction.status_code == 201
    assert correction.json()["loan"]["total_outstanding_cents"] == 250
    assert correction.json()["loan"]["status"] == "open"


def test_corrections_must_not_reallocate_later_payments(api):
    loan = charged(api)
    first = post(
        api,
        f"/loans/{loan['id']}/repayments",
        {"amount_cents": 1200, "effective_at": "2026-01-08T12:00:00Z"},
    ).json()
    second = post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 2000}).json()
    snapshot = second["event"]
    response = post(
        api,
        f"/loans/{loan['id']}/events/{first['event']['id']}/reverse",
        {"reason": "Earlier mistake"},
    )
    assert response.status_code == 409
    with Session(api.engine) as session:
        original = session.get(LoanEvent, UUID(first["event"]["id"]))
        assert original.reversed_at is None
    current = api.client.get(f"/loans/{loan['id']}/events/{snapshot['id']}").json()
    assert current == snapshot


@pytest.mark.parametrize(
    "changes",
    [
        {"interest_rate_bps": -1},
        {"interest_rate_bps": 1.5},
        {"interest_rate_bps": True},
        {"interest_rate_bps": 10001},
        {"interest_period": "bimonthly"},
        {"late_fee_cents": -1},
        {"late_fee_cents": 1.5},
        {"grace_days": 366},
        {"charge_cap_cents": -1},
    ],
)
def test_terms_validation(api, changes):
    friend = new_friend(api)
    response = post(
        api,
        "/loans",
        {
            "friend_id": friend["id"],
            "kind": "money",
            "description": "Test",
            "principal_cents": 5000,
            "due_date": "2026-01-20",
            **changes,
        },
    )
    assert response.status_code == 422


def test_waiver_limits_and_owner_boundaries(api):
    loan = charged(api)
    assert (
        post(
            api,
            f"/loans/{loan['id']}/waivers",
            {"component": "principal", "amount_cents": 1, "reason": "X"},
        ).status_code
        == 422
    )
    assert (
        post(
            api,
            f"/loans/{loan['id']}/waivers",
            {"component": "interest", "amount_cents": 1001, "reason": "X"},
        ).status_code
        == 409
    )
    assert post(api, f"/loans/{loan['id']}/fee-payments", {"amount_cents": 1}).status_code == 409
    api.user = type(api.user)(uuid4(), None, "Other")
    assert (
        post(
            api,
            f"/loans/{loan['id']}/waivers",
            {"component": "interest", "amount_cents": 1, "reason": "X"},
        ).status_code
        == 404
    )
    assert api.client.get(f"/friends/{loan['friend_id']}/score").status_code == 404


def test_score_counts_obligations_not_payments_and_uses_grace(api):
    friend = new_friend(api)
    for _ in range(3):
        loan = new_loan(api, friend["id"], due_date="2026-01-09", grace_days=2)
        post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 2000})
        post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 3000})
    score = api.client.get(f"/friends/{friend['id']}/score").json()
    assert score["score"] == 675 and score["completed_count"] == 3
    assert score["on_time_completed"] == 3 and score["late_completed"] == 0
    assert "not a real credit score" in score["disclaimer"]
    assert api.client.get(f"/friends/{friend['id']}/score").headers["cache-control"] == "no-store"


def test_late_completion_is_not_counted_as_currently_overdue(api):
    friend = new_friend(api)
    for due, effective in (
        ("2026-01-09", "2026-01-09T12:00:00Z"),
        ("2026-01-08", "2026-01-10T12:00:00Z"),
        ("2026-01-20", "2026-01-10T12:00:00Z"),
    ):
        loan = new_loan(api, friend["id"], due_date=due)
        assert (
            post(
                api,
                f"/loans/{loan['id']}/repayments",
                {"amount_cents": 5000, "effective_at": effective},
            ).status_code
            == 201
        )
    new_loan(api, friend["id"], due_date="2026-01-08")
    score = api.client.get(f"/friends/{friend['id']}/score").json()
    assert score["score"] == 590
    assert score["late_completed"] == score["currently_overdue"] == 1


def test_scores_clamp_and_insufficient_history_after_reversal(api):
    from iou.ledger.schemas import LoanRead
    from iou.ledger.scores import score

    friend = new_friend(api)
    loan = new_loan(api, friend["id"])
    event = post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 5000}).json()["event"]
    completed = LoanRead.model_validate(api.client.get(f"/loans/{loan['id']}").json())
    assert (
        score([completed.model_copy(update={"id": uuid4()}) for _ in range(20)], NOW).score == 850
    )
    late = completed.model_copy(update={"fee_at": NOW - timedelta(days=1)})
    assert score([late.model_copy(update={"id": uuid4()}) for _ in range(20)], NOW).score == 300
    post(api, f"/loans/{loan['id']}/events/{event['id']}/reverse", {"reason": "Mistake"})
    fresh = api.client.get(f"/friends/{friend['id']}/score").json()
    assert fresh["score"] is None and fresh["completed_count"] == 0


def test_insufficient_history_voids_and_return_timeliness(api):
    friend = new_friend(api)
    item = new_loan(api, friend["id"], "item", due_date="2026-01-09", late_fee_cents=500)
    post(api, f"/loans/{item['id']}/return")
    voided = new_loan(api, friend["id"])
    post(api, f"/loans/{voided['id']}/void", {"reason": "Duplicate"})
    score = api.client.get(f"/friends/{friend['id']}/score").json()
    assert score["score"] is None and not score["sufficient_history"]
    assert score["late_completed"] == 1 and score["currently_overdue"] == 0
    assert score["excluded_voided"] == 1
