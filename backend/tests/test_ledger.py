"""Level 1 contracts and isolation. PostgreSQL locking is tested separately."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from iou.api import app
from iou.auth import Identity, get_current_user
from iou.database import Base, get_session
from iou.ledger import service
from iou.ledger.models import LoanEvent, MutationReceipt

NOW = datetime(2026, 1, 10, 12, tzinfo=UTC)


@pytest.fixture
def api(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"iou_app": None}},
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    state = SimpleNamespace(user=Identity(uuid4(), "owner@example.com", "Owner"), engine=engine)

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    app.dependency_overrides[get_current_user] = lambda: state.user
    monkeypatch.setattr(service, "now_utc", lambda: NOW)
    with TestClient(app) as client:
        state.client = client
        yield state
    app.dependency_overrides.clear()
    engine.dispose()


def post(api, path, body=None, key=None):
    return api.client.post(
        path,
        headers={"Idempotency-Key": str(key or uuid4())},
        **({"json": body} if body is not None else {}),
    )


def new_friend(api, **changes):
    response = post(api, "/friends", {"display_name": "Alex", **changes})
    assert response.status_code == 201, response.text
    return response.json()


def loan_body(friend_id, kind="money", **changes):
    body = {
        "friend_id": friend_id,
        "kind": kind,
        "description": "$50" if kind == "money" else "Hoodie",
        "lent_at": "2026-01-01T12:00:00Z",
        "due_date": "2026-01-20",
    }
    if kind == "money":
        body["principal_cents"] = 5000
    return {**body, **changes}


def new_loan(api, friend_id, kind="money", **changes):
    response = post(api, "/loans", loan_body(friend_id, kind, **changes))
    assert response.status_code == 201, response.text
    return response.json()


def test_friend_management_and_archive(api):
    friend = new_friend(api, display_name="  Alex  ", email="alex@example.com", notes="A friend")
    assert friend["display_name"] == "Alex"
    response = api.client.patch(f"/friends/{friend['id']}", json={"email": None, "notes": None})
    assert response.status_code == 200
    assert response.json()["email"] is None
    assert response.json()["notes"] is None
    assert api.client.get("/friends").headers["cache-control"] == "no-store"
    first = api.client.post(f"/friends/{friend['id']}/archive").json()
    again = api.client.post(f"/friends/{friend['id']}/archive").json()
    assert first == again
    assert api.client.get("/friends").json()["items"] == []
    assert len(api.client.get("/friends?archived=only").json()["items"]) == 1
    assert len(api.client.get("/friends?archived=include").json()["items"]) == 1
    assert api.client.get(f"/friends/{friend['id']}").status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"display_name": " "},
        {"display_name": "x" * 101},
        {"display_name": "Alex", "email": "not-an-email"},
        {"display_name": "Alex", "notes": "x" * 2001},
        {"display_name": "Alex", "owner_id": str(uuid4())},
    ],
)
def test_friend_validation(api, body):
    assert post(api, "/friends", body).status_code == 422


@pytest.mark.parametrize(
    "body", [{"display_name": None}, {"owner_id": str(uuid4())}, {"archived_at": NOW.isoformat()}]
)
def test_friend_patch_validation(api, body):
    friend = new_friend(api)
    assert api.client.patch(f"/friends/{friend['id']}", json=body).status_code == 422


def test_contact_duplicates_are_private_and_allowed(api):
    assert (
        new_friend(api, email="alex@example.com")["id"]
        != new_friend(api, email="alex@example.com")["id"]
    )


def test_full_money_and_item_lifecycle(api):
    friend = new_friend(api)
    money = new_loan(api, friend["id"])
    item = new_loan(api, friend["id"], "item")
    assert money["outstanding_cents"] == 5000
    assert money["interest_cents"] == money["fees_cents"] == 0
    assert item["principal_cents"] is item["outstanding_cents"] is None
    first = post(
        api,
        f"/loans/{money['id']}/repayments",
        {"amount_cents": 2000, "effective_at": "2026-01-03T12:00:00Z"},
    )
    assert first.status_code == 201
    assert first.json()["loan"]["outstanding_cents"] == 3000
    final = post(api, f"/loans/{money['id']}/repayments", {"amount_cents": 3000})
    assert final.status_code == 201
    assert final.json()["loan"]["status"] == "completed"
    assert final.json()["loan"]["outstanding_cents"] == 0
    assert final.json()["loan"]["completed_at"] == NOW.isoformat().replace("+00:00", "Z")
    returned = post(api, f"/loans/{item['id']}/return")
    assert returned.status_code == 201
    assert returned.json()["loan"]["status"] == "completed"
    history = api.client.get(f"/friends/{friend['id']}/history").json()
    assert len(history["items"]) == 5
    assert sorted(e["action"] for e in history["items"]) == [
        "lent",
        "lent",
        "repayment",
        "repayment",
        "return",
    ]
    assert all(e["loan"]["status"] == "completed" for e in history["items"])


def test_archive_prevents_new_lending_but_not_settlement(api):
    friend = new_friend(api)
    money = new_loan(api, friend["id"])
    item = new_loan(api, friend["id"], "item")
    api.client.post(f"/friends/{friend['id']}/archive")
    assert post(api, "/loans", loan_body(friend["id"])).status_code == 409
    assert post(api, f"/loans/{money['id']}/repayments", {"amount_cents": 5000}).status_code == 201
    assert post(api, f"/loans/{item['id']}/return").status_code == 201
    assert len(api.client.get(f"/friends/{friend['id']}/history").json()["items"]) == 4


@pytest.mark.parametrize(
    "changes",
    [
        {"principal_cents": 0},
        {"principal_cents": -1},
        {"principal_cents": 1.5},
        {"principal_cents": "5000"},
        {"principal_cents": True},
        {"principal_cents": 1_000_000_000_001},
        {"currency": "EUR"},
        {"due_date": "2025-12-31"},
        {"due_date": "9999-12-31"},
        {"lent_at": "2027-01-01T12:00:00Z"},
        {"lent_at": "2026-01-01T12:00:00"},
        {"lent_at": 1},
        {"lent_at": "1"},
        {"lent_at": "0001-01-01T00:00:00+14:00"},
        {"kind": "item", "principal_cents": 5000},
        {"kind": "unknown"},
        {"description": " "},
        {"owner_id": str(uuid4())},
        {"interest_rate": 0.1},
    ],
)
def test_loan_validation(api, changes):
    friend = new_friend(api)
    assert post(api, "/loans", loan_body(friend["id"], **changes)).status_code == 422


@pytest.mark.parametrize("amount", [0, -1, 1.5, "5000", True, 1_000_000_000_001])
def test_repayment_amount_validation(api, amount):
    loan = new_loan(api, new_friend(api)["id"])
    assert post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": amount}).status_code == 422


def test_wrong_actions_and_excess_payment_leave_balance_unchanged(api):
    friend = new_friend(api)
    money = new_loan(api, friend["id"])
    item = new_loan(api, friend["id"], "item")
    assert post(api, f"/loans/{money['id']}/return").status_code == 409
    assert post(api, f"/loans/{item['id']}/repayments", {"amount_cents": 1}).status_code == 409
    assert post(api, f"/loans/{money['id']}/repayments", {"amount_cents": 5001}).status_code == 409
    assert api.client.get(f"/loans/{money['id']}").json()["outstanding_cents"] == 5000
    assert post(api, f"/loans/{money['id']}/repayments", {"amount_cents": 5000}).status_code == 201
    assert post(api, f"/loans/{money['id']}/repayments", {"amount_cents": 1}).status_code == 409
    assert post(api, f"/loans/{item['id']}/return").status_code == 201
    assert post(api, f"/loans/{item['id']}/return").status_code == 409


@pytest.mark.parametrize(
    "effective", ["2025-12-31T12:00:00Z", "2027-01-01T12:00:00Z", "2026-01-02T12:00:00"]
)
def test_settlement_time_validation(api, effective):
    loan = new_loan(api, new_friend(api)["id"])
    assert (
        post(
            api, f"/loans/{loan['id']}/repayments", {"amount_cents": 1, "effective_at": effective}
        ).status_code
        == 422
    )


def test_out_of_order_backdating_uses_latest_effective_completion(api):
    loan = new_loan(api, new_friend(api)["id"])
    post(
        api,
        f"/loans/{loan['id']}/repayments",
        {"amount_cents": 2500, "effective_at": "2026-01-08T12:00:00Z"},
    )
    response = post(
        api,
        f"/loans/{loan['id']}/repayments",
        {"amount_cents": 2500, "effective_at": "2026-01-03T12:00:00Z"},
    )
    assert response.json()["loan"]["completed_at"] == "2026-01-08T12:00:00Z"


def test_isolation_for_every_ledger_path(api):
    friend = new_friend(api)
    loan = new_loan(api, friend["id"])
    owner = api.user
    api.user = Identity(uuid4(), "other@example.com", "Other")
    assert api.client.get("/friends").json()["items"] == []
    assert api.client.get("/loans").json()["items"] == []
    for path in (
        f"/friends/{friend['id']}",
        f"/friends/{friend['id']}/history",
        f"/loans/{loan['id']}",
        f"/loans?friend_id={friend['id']}",
    ):
        assert api.client.get(path).status_code == 404
    assert (
        api.client.patch(f"/friends/{friend['id']}", json={"display_name": "Stolen"}).status_code
        == 404
    )
    assert api.client.post(f"/friends/{friend['id']}/archive").status_code == 404
    assert post(api, "/loans", loan_body(friend["id"])).status_code == 404
    assert post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 1}).status_code == 404
    assert post(api, f"/loans/{loan['id']}/return").status_code == 404
    api.user = owner
    assert api.client.get(f"/friends/{friend['id']}").json()["display_name"] == "Alex"
    assert api.client.get(f"/loans/{loan['id']}").json()["outstanding_cents"] == 5000


def test_missing_records_also_return_404(api):
    missing = uuid4()
    assert api.client.get(f"/friends/{missing}").status_code == 404
    assert api.client.get(f"/loans/{missing}").status_code == 404
    assert api.client.get(f"/friends/{missing}/history").status_code == 404


def test_all_creates_replay_original_response(api):
    key = uuid4()
    body = {"display_name": "Alex"}
    first = post(api, "/friends", body, key)
    replay = post(api, "/friends", body, key)
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert replay.headers["idempotency-replayed"] == "true"
    assert len(api.client.get("/friends").json()["items"]) == 1
    loan_key = uuid4()
    body = loan_body(first.json()["id"])
    loan = post(api, "/loans", body, loan_key)
    assert post(api, "/loans", body, loan_key).json() == loan.json()
    payment_key = uuid4()
    path = f"/loans/{loan.json()['id']}/repayments"
    payment = post(api, path, {"amount_cents": 1000}, payment_key)
    assert post(api, path, {"amount_cents": 1000}, payment_key).json() == payment.json()
    assert api.client.get(f"/loans/{loan.json()['id']}").json()["repaid_cents"] == 1000
    item = new_loan(api, first.json()["id"], "item")
    return_key = uuid4()
    returned = post(api, f"/loans/{item['id']}/return", key=return_key)
    assert post(api, f"/loans/{item['id']}/return", {}, return_key).json() == returned.json()


def test_equivalent_timestamp_offsets_replay(api):
    friend = new_friend(api)
    key = uuid4()
    first = post(api, "/loans", loan_body(friend["id"]), key)
    replay = post(api, "/loans", loan_body(friend["id"], lent_at="2026-01-01T13:00:00+01:00"), key)
    assert replay.status_code == 201
    assert replay.json() == first.json()


def test_key_cannot_be_reused_for_another_loan(api):
    friend = new_friend(api)
    first = new_loan(api, friend["id"])
    second = new_loan(api, friend["id"])
    key = uuid4()
    assert (
        post(api, f"/loans/{first['id']}/repayments", {"amount_cents": 1}, key).status_code == 201
    )
    assert (
        post(api, f"/loans/{second['id']}/repayments", {"amount_cents": 1}, key).status_code == 409
    )
    assert api.client.get(f"/loans/{second['id']}").json()["repaid_cents"] == 0


def test_idempotency_key_is_owner_scoped_and_rejects_different_requests(api):
    key = uuid4()
    friend = post(api, "/friends", {"display_name": "Alex"}, key).json()
    assert post(api, "/friends", {"display_name": "Different"}, key).status_code == 409
    assert post(api, "/loans", loan_body(friend["id"]), key).status_code == 409
    api.user = Identity(uuid4(), None, "Other")
    assert post(api, "/friends", {"display_name": "Different"}, key).status_code == 201


def test_failed_mutation_does_not_store_receipt(api):
    loan = new_loan(api, new_friend(api)["id"])
    key = uuid4()
    path = f"/loans/{loan['id']}/repayments"
    assert post(api, path, {"amount_cents": 5001}, key).status_code == 409
    with Session(api.engine) as session:
        assert session.get(MutationReceipt, (api.user.id, key)) is None
        assert session.scalar(select(func.count()).select_from(LoanEvent)) == 0
    assert post(api, path, {"amount_cents": 5000}, key).status_code == 201


def test_exception_rolls_back_event_and_receipt(api, monkeypatch):
    loan = new_loan(api, new_friend(api)["id"])
    key = uuid4()
    original = service.settle

    def fail_after_flush(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("simulated failure before commit")

    monkeypatch.setattr(service, "settle", fail_after_flush)
    with pytest.raises(RuntimeError, match="simulated failure"):
        post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 1000}, key)
    with Session(api.engine) as session:
        assert session.scalar(select(func.count()).select_from(LoanEvent)) == 0
        assert session.get(MutationReceipt, (api.user.id, key)) is None
    assert api.client.get(f"/loans/{loan['id']}").json()["outstanding_cents"] == 5000
    monkeypatch.setattr(service, "settle", original)
    assert (
        post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": 1000}, key).status_code == 201
    )


def test_replay_is_original_snapshot_not_a_new_balance_calculation(api):
    loan = new_loan(api, new_friend(api)["id"])
    path = f"/loans/{loan['id']}/repayments"
    key = uuid4()
    first = post(api, path, {"amount_cents": 1000}, key)
    post(api, path, {"amount_cents": 1000})
    assert post(api, path, {"amount_cents": 1000}, key).json() == first.json()
    assert api.client.get(f"/loans/{loan['id']}").json()["outstanding_cents"] == 3000


def test_required_idempotency_header(api):
    for headers in ({}, {"Idempotency-Key": "not-a-uuid"}):
        assert (
            api.client.post("/friends", json={"display_name": "Alex"}, headers=headers).status_code
            == 422
        )


def test_pagination_and_filters(api):
    friend_ids = [new_friend(api, display_name=str(i))["id"] for i in range(3)]
    first = api.client.get("/friends?limit=2").json()
    second = api.client.get("/friends?limit=2&offset=2").json()
    assert first["has_more"] and not second["has_more"]
    assert len({f["id"] for f in first["items"] + second["items"]}) == 3
    money = new_loan(api, friend_ids[0], due_date="2026-01-09")
    new_loan(api, friend_ids[0], "item")
    new_loan(api, friend_ids[1])
    assert len(api.client.get("/loans?kind=item").json()["items"]) == 1
    assert len(api.client.get(f"/loans?friend_id={friend_ids[0]}").json()["items"]) == 2
    assert api.client.get("/loans?overdue=true").json()["items"][0]["id"] == money["id"]
    assert len(api.client.get("/loans?overdue=false").json()["items"]) == 2
    post(api, f"/loans/{money['id']}/repayments", {"amount_cents": 5000})
    assert len(api.client.get("/loans?status=completed").json()["items"]) == 1
    assert len(api.client.get("/loans?status=open").json()["items"]) == 2
    assert api.client.get("/loans?overdue=true").json()["items"] == []
    history = api.client.get(f"/friends/{friend_ids[0]}/history?limit=1").json()
    assert len(history["items"]) == 1 and history["has_more"]
    for path in ("/friends?limit=0", "/loans?limit=101", "/friends?offset=-1", "/loans?status=bad"):
        assert api.client.get(path).status_code == 422


def test_history_orders_by_effective_then_recorded_time(api):
    friend = new_friend(api)
    loan = new_loan(api, friend["id"])
    post(
        api,
        f"/loans/{loan['id']}/repayments",
        {"amount_cents": 1, "effective_at": "2026-01-08T12:00:00Z"},
    )
    post(
        api,
        f"/loans/{loan['id']}/repayments",
        {"amount_cents": 1, "effective_at": "2026-01-03T12:00:00Z"},
    )
    rows = api.client.get(f"/friends/{friend['id']}/history").json()["items"]
    assert [row["effective_at"] for row in rows] == [
        "2026-01-08T12:00:00Z",
        "2026-01-03T12:00:00Z",
        "2026-01-01T12:00:00Z",
    ]
    assert rows[0]["recorded_at"] == "2026-01-10T12:00:00Z"
    assert all(row["loan"]["outstanding_cents"] == 4998 for row in rows)


def test_timezone_snapshot_dst_and_inclusive_due_date(api, monkeypatch):
    api.client.patch("/me", json={"timezone": "America/Los_Angeles"})
    friend = new_friend(api)
    loan = new_loan(api, friend["id"], due_date="2026-03-08")
    # DST starts on March 8: the following midnight is 07:00Z, not 08:00Z.
    assert loan["overdue_at"] == "2026-03-09T07:00:00Z"
    api.client.patch("/me", json={"timezone": "Asia/Tokyo"})
    boundary = datetime(2026, 3, 9, 7, tzinfo=UTC)
    monkeypatch.setattr(service, "now_utc", lambda: boundary - timedelta(microseconds=1))
    assert not api.client.get(f"/loans/{loan['id']}").json()["overdue"]
    monkeypatch.setattr(service, "now_utc", lambda: boundary)
    assert api.client.get(f"/loans/{loan['id']}").json()["overdue"]
    assert len(api.client.get("/loans?overdue=true").json()["items"]) == 1
    assert api.client.get(f"/loans/{loan['id']}").json()["timezone"] == "America/Los_Angeles"


def test_lending_outside_local_datetime_range_is_validation_error(api):
    api.client.patch("/me", json={"timezone": "America/Los_Angeles"})
    friend = new_friend(api)
    response = post(api, "/loans", loan_body(friend["id"], lent_at="0001-01-01T00:00:00Z"))
    assert response.status_code == 422


def test_loan_replay_remains_valid_after_archive(api):
    friend = new_friend(api)
    key = uuid4()
    body = loan_body(friend["id"])
    first = post(api, "/loans", body, key)
    api.client.post(f"/friends/{friend['id']}/archive")
    assert post(api, "/loans", body, key).json() == first.json()
    assert post(api, "/loans", body).status_code == 409


def test_due_date_uses_local_lending_date(api):
    api.client.patch("/me", json={"timezone": "America/Los_Angeles"})
    friend = new_friend(api)
    # 01:00Z on Jan 2 is still Jan 1 in Los Angeles.
    loan = new_loan(api, friend["id"], lent_at="2026-01-02T01:00:00Z", due_date="2026-01-01")
    assert loan["overdue_at"] == "2026-01-02T08:00:00Z"


def test_no_silent_edits_or_deletes(api):
    friend = new_friend(api)
    loan = new_loan(api, friend["id"])
    assert api.client.delete(f"/friends/{friend['id']}").status_code == 405
    assert api.client.patch(f"/loans/{loan['id']}", json={"principal_cents": 1}).status_code == 405
    assert api.client.delete(f"/loans/{loan['id']}").status_code == 405


def test_new_routes_require_authentication():
    with TestClient(app) as client:
        for path in ("/friends", "/loans", f"/friends/{uuid4()}/history", f"/loans/{uuid4()}"):
            assert client.get(path).status_code == 401
        assert (
            client.post(
                "/friends", json={"display_name": "Alex"}, headers={"Idempotency-Key": str(uuid4())}
            ).status_code
            == 401
        )
