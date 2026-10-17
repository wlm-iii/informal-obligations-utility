from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_ledger import api as api
from test_ledger import new_friend, new_loan, post

from iou.ledger.models import Audit, LoanEvent, MutationReceipt


def paid(api, amount=5000, kind="money"):
    loan = new_loan(api, new_friend(api)["id"], kind)
    body = {"amount_cents": amount} if kind == "money" else {}
    action = "repayments" if kind == "money" else "return"
    response = post(api, f"/loans/{loan['id']}/{action}", body)
    assert response.status_code == 201
    return SimpleNamespace(loan=loan, event=response.json()["event"])


def path(record, action):
    return f"/loans/{record.loan['id']}/events/{record.event['id']}/{action}"


def test_reversal_reopens_money_and_preserves_original(api):
    record = paid(api)
    response = post(api, path(record, "reverse"), {"reason": "Entered twice"})
    assert response.status_code == 201
    data = response.json()
    assert data["loan"]["status"] == "open"
    assert data["loan"]["outstanding_cents"] == 5000
    assert data["original_event"]["amount_cents"] == 5000
    assert data["original_event"]["effective_at"] == record.event["effective_at"]
    assert data["original_event"]["recorded_at"] == record.event["recorded_at"]
    assert data["original_event"]["reversed_at"] is not None
    assert data["reversal"]["event_id"] == record.event["id"]
    assert data["replacement"] is None
    entries = api.client.get(f"/friends/{record.loan['friend_id']}/history").json()["items"]
    assert sorted(row["action"] for row in entries) == ["lent", "repayment", "reversal"]
    reversal = next(row for row in entries if row["action"] == "reversal")
    assert reversal["amount_cents"] == -5000
    assert reversal["reason"] == "Entered twice"
    original = next(row for row in entries if row["action"] == "repayment")
    assert original["reversed_at"] is not None


def test_correct_amount_and_default_effective_time(api):
    record = paid(api, 2000)
    response = post(
        api,
        path(record, "correct"),
        {
            "reason": "Actually ten dollars",
            "replacement": {"action": "repayment", "amount_cents": 1000},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["loan"]["outstanding_cents"] == 4000
    assert data["replacement"]["replaces_event_id"] == record.event["id"]
    assert data["replacement"]["effective_at"] == record.event["effective_at"]
    assert data["reversal"]["replacement_event_id"] == data["replacement"]["id"]
    assert data["original_event"]["amount_cents"] == 2000


def test_replacement_can_be_corrected_again(api):
    record = paid(api, 2000)
    first = post(
        api,
        path(record, "correct"),
        {
            "reason": "Ten",
            "replacement": {"action": "repayment", "amount_cents": 1000},
        },
    ).json()
    next_record = SimpleNamespace(loan=record.loan, event=first["replacement"])
    second = post(
        api,
        path(next_record, "correct"),
        {
            "reason": "Actually five",
            "replacement": {"action": "repayment", "amount_cents": 500},
        },
    )
    assert second.status_code == 201
    assert second.json()["loan"]["repaid_cents"] == 500


def test_correct_date_and_note(api):
    record = paid(api)
    response = post(
        api,
        path(record, "correct"),
        {
            "reason": "Wrong date",
            "replacement": {
                "action": "repayment",
                "amount_cents": 5000,
                "effective_at": "2026-01-04T12:00:00Z",
                "note": "Corrected",
            },
        },
    )
    assert response.status_code == 201
    assert response.json()["loan"]["completed_at"] == "2026-01-04T12:00:00Z"
    assert response.json()["replacement"]["note"] == "Corrected"


def test_later_payments_are_never_silently_reallocated(api):
    record = paid(api, 2000)
    post(api, f"/loans/{record.loan['id']}/repayments", {"amount_cents": 3000})
    key = uuid4()
    response = post(
        api,
        path(record, "correct"),
        {
            "reason": "Wrong amount",
            "replacement": {"action": "repayment", "amount_cents": 2500},
        },
        key,
    )
    assert response.status_code == 409
    assert api.client.get(f"/loans/{record.loan['id']}").json()["outstanding_cents"] == 0
    with Session(api.engine) as session:
        assert session.get(LoanEvent, UUID(record.event["id"])).reversed_at is None
        assert session.scalar(select(func.count()).select_from(Audit)) == 0
        assert session.get(MutationReceipt, (api.user.id, key)) is None


@pytest.mark.parametrize("kind", ["money", "item"])
def test_reversal_retry_is_safe_and_new_key_cannot_reverse_twice(api, kind):
    record = paid(api, kind=kind)
    key = uuid4()
    body = {"reason": "Mistake"}
    first = post(api, path(record, "reverse"), body, key)
    assert first.status_code == 201
    assert post(api, path(record, "reverse"), body, key).json() == first.json()
    assert post(api, path(record, "reverse"), body).status_code == 409
    if kind == "item":
        assert post(api, f"/loans/{record.loan['id']}/return").status_code == 201
    with Session(api.engine) as session:
        assert session.scalar(select(func.count()).select_from(Audit)) == 1


def test_item_return_correction_releases_active_return_index(api):
    record = paid(api, kind="item")
    response = post(
        api,
        path(record, "correct"),
        {
            "reason": "Wrong date",
            "replacement": {"action": "return", "effective_at": "2026-01-05T12:00:00Z"},
        },
    )
    assert response.status_code == 201
    assert response.json()["loan"]["returned_at"] == "2026-01-05T12:00:00Z"
    assert response.json()["loan"]["status"] == "completed"


@pytest.mark.parametrize(
    "replacement",
    [
        {"action": "return"},
        {"action": "repayment", "amount_cents": 0},
        {"action": "repayment", "amount_cents": 1000, "effective_at": "2025-01-01T12:00:00Z"},
        {"action": "repayment", "amount_cents": 1000, "effective_at": "2027-01-01T12:00:00Z"},
    ],
)
def test_invalid_correction_preserves_active_original(api, replacement):
    record = paid(api, 2000)
    response = post(api, path(record, "correct"), {"reason": "Mistake", "replacement": replacement})
    assert response.status_code in (409, 422)
    event = api.client.get(f"/loans/{record.loan['id']}/events/{record.event['id']}").json()
    assert event["reversed_at"] is None
    assert api.client.get(f"/loans/{record.loan['id']}").json()["repaid_cents"] == 2000


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"reason": " "},
        {"reason": "x" * 1001},
        {"reason": "bad\x00reason"},
        {"reason": "X", "owner_id": str(uuid4())},
    ],
)
def test_reason_is_required_and_cannot_supply_actor(api, body):
    record = paid(api)
    assert post(api, path(record, "reverse"), body).status_code == 422


def test_void_requires_reversing_all_active_settlements(api):
    record = paid(api)
    void_path = f"/loans/{record.loan['id']}/void"
    assert post(api, void_path, {"reason": "Wrong borrower"}).status_code == 409
    post(api, path(record, "reverse"), {"reason": "Undo mistaken repayment"})
    key = uuid4()
    voided = post(api, void_path, {"reason": "Wrong borrower"}, key)
    assert voided.status_code == 201
    assert voided.json()["loan"]["status"] == "voided"
    assert voided.json()["loan"]["outstanding_cents"] == 0
    assert voided.json()["loan"]["principal_cents"] == 5000
    assert not voided.json()["loan"]["overdue"]
    assert post(api, void_path, {"reason": "Wrong borrower"}, key).json() == voided.json()
    assert post(api, void_path, {"reason": "Again"}).status_code == 409
    assert (
        post(api, f"/loans/{record.loan['id']}/repayments", {"amount_cents": 1}).status_code == 409
    )
    assert post(api, path(record, "reverse"), {"reason": "Again"}).status_code == 409
    assert len(api.client.get("/loans?status=voided").json()["items"]) == 1
    assert api.client.get("/loans?status=open").json()["items"] == []
    assert api.client.get("/loans?status=completed").json()["items"] == []
    assert len(api.client.get("/loans?overdue=false").json()["items"]) == 1
    rows = api.client.get(f"/friends/{record.loan['friend_id']}/history").json()["items"]
    assert "void" in [r["action"] for r in rows]


def test_void_item_without_return(api):
    loan = new_loan(api, new_friend(api)["id"], "item")
    result = post(api, f"/loans/{loan['id']}/void", {"reason": "Duplicate entry"})
    assert result.status_code == 201
    assert result.json()["loan"]["outstanding_cents"] is None
    assert post(api, f"/loans/{loan['id']}/return").status_code == 409


def test_foreign_owner_and_wrong_loan_event_return_404(api):
    record = paid(api)
    another = new_loan(api, new_friend(api)["id"])
    assert (
        post(
            api, f"/loans/{another['id']}/events/{record.event['id']}/reverse", {"reason": "X"}
        ).status_code
        == 404
    )
    api.user = type(api.user)(uuid4(), None, "Other")
    assert post(api, path(record, "reverse"), {"reason": "X"}).status_code == 404
    assert post(api, f"/loans/{record.loan['id']}/void", {"reason": "X"}).status_code == 404
    assert (
        api.client.get(f"/loans/{record.loan['id']}/events/{record.event['id']}").status_code == 404
    )
