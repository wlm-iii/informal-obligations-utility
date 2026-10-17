from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_ledger_database import pg as pg
from test_ledger_database import post, race

from iou.ledger.models import LoanEvent

pytestmark = pytest.mark.database


def charged(pg, kind="money"):
    friend = post(pg, "/friends", {"display_name": "Alex"}).json()
    now = datetime.now(UTC)
    body = {
        "friend_id": friend["id"],
        "kind": kind,
        "description": "Test",
        "lent_at": (now - timedelta(days=7)).isoformat(),
        "due_date": (now - timedelta(days=1)).date().isoformat(),
        "late_fee_cents": 200,
    }
    if kind == "money":
        body.update(principal_cents=10000, interest_rate_bps=1000, interest_period="weekly")
    response = post(pg, "/loans", body)
    assert response.status_code == 201, response.text
    return response.json()


def test_migration_preserves_legacy_zero_charge_records(pg):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(config, "0004_history_proof")
    friend_id, loan_id, event_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    try:
        with pg.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO iou_app.profiles(id,display_name) VALUES (:owner,'Legacy owner')"
                ),
                {"owner": pg.user.id},
            )
            connection.execute(
                text(
                    "INSERT INTO iou_app.friends(id,owner_id,display_name) "
                    "VALUES (:id,:owner,'Legacy friend')"
                ),
                {"id": friend_id, "owner": pg.user.id},
            )
            connection.execute(
                text("""
                INSERT INTO iou_app.loans(id,owner_id,friend_id,kind,description,principal_cents,
                    currency,lent_at,due_date,timezone,overdue_at)
                VALUES (:id,:owner,:friend,'money','Legacy',10000,'USD',:lent,:due,'UTC',:boundary)
            """),
                {
                    "id": loan_id,
                    "owner": pg.user.id,
                    "friend": friend_id,
                    "lent": now - timedelta(days=7),
                    "due": now.date() + timedelta(days=1),
                    "boundary": now + timedelta(days=2),
                },
            )
            connection.execute(
                text("""
                INSERT INTO iou_app.loan_events
                    (id,owner_id,loan_id,loan_kind,action,amount_cents,effective_at)
                VALUES (:id,:owner,:loan,'money','repayment',10000,:effective)
            """),
                {
                    "id": event_id,
                    "owner": pg.user.id,
                    "loan": loan_id,
                    "effective": now - timedelta(days=2),
                },
            )
        command.upgrade(config, "head")
        state = pg.client.get(f"/loans/{loan_id}").json()
        assert state["calculation_version"] == 0 and state["status"] == "completed"
        assert (
            state["interest_cents"] == state["fees_cents"] == state["total_outstanding_cents"] == 0
        )
        event = pg.client.get(f"/loans/{loan_id}/events/{event_id}").json()
        assert event["principal_applied_cents"] == 10000
        assert event["interest_applied_cents"] == event["fees_applied_cents"] == 0
        command.downgrade(config, "0004_history_proof")
        with pg.engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT amount_cents FROM iou_app.loan_events WHERE id=:id"),
                    {"id": event_id},
                )
                == 10000
            )
    finally:
        command.upgrade(config, "head")


def test_new_terms_prevent_unsafe_downgrade(pg):
    loan = charged(pg)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with pytest.raises(DBAPIError):
        command.downgrade(config, "0004_history_proof")
    assert pg.client.get(f"/loans/{loan['id']}").json()["interest_rate_bps"] == 1000


def test_concurrent_charged_payments_cannot_overpay(pg):
    loan = charged(pg)
    assert loan["total_outstanding_cents"] == 11200
    path = f"/loans/{loan['id']}/repayments"
    responses = race(
        lambda: post(pg, path, {"amount_cents": 7000}),
        lambda: post(pg, path, {"amount_cents": 7000}),
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    current = pg.client.get(f"/loans/{loan['id']}").json()
    assert current["total_outstanding_cents"] == 4200
    with Session(pg.engine) as session:
        event = session.scalar(select(LoanEvent).where(LoanEvent.loan_id == UUID(loan["id"])))
        assert (
            event.principal_applied_cents,
            event.interest_applied_cents,
            event.fees_applied_cents,
        ) == (5800, 1000, 200)


def test_waiver_and_full_payment_race_is_serialized(pg):
    loan = charged(pg)
    responses = race(
        lambda: post(
            pg,
            f"/loans/{loan['id']}/waivers",
            {"component": "fees", "amount_cents": 200, "reason": "Forgiven"},
        ),
        lambda: post(pg, f"/loans/{loan['id']}/repayments", {"amount_cents": 11200}),
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    current = pg.client.get(f"/loans/{loan['id']}").json()
    assert current["total_outstanding_cents"] in (0, 11000)
    assert current["fees_paid_cents"] + current["fees_waived_cents"] == 200


def test_item_charges_status_score_and_history_filters(pg):
    loan = charged(pg, "item")
    assert post(pg, f"/loans/{loan['id']}/return").status_code == 201
    returned = pg.client.get(f"/loans/{loan['id']}").json()
    assert returned["borrowing_status"] == "returned" and returned["status"] == "open"
    assert pg.client.get("/loans?overdue=true").json()["items"] == []
    waiver = post(
        pg,
        f"/loans/{loan['id']}/waivers",
        {"component": "fees", "amount_cents": 200, "reason": "Friends"},
    )
    assert waiver.status_code == 201
    assert len(pg.client.get("/loans?status=completed").json()["items"]) == 1
    score = pg.client.get(f"/friends/{loan['friend_id']}/score").json()
    assert score["late_completed"] == 1 and score["currently_overdue"] == 0
    history = pg.client.get(f"/friends/{loan['friend_id']}/history").json()["items"]
    row = next(row for row in history if row["action"] == "waiver")
    assert row["fees_applied_cents"] == 200 and row["reason"] == "Friends"
    assert (
        post(
            pg,
            f"/loans/{loan['id']}/events/{waiver.json()['event']['id']}/reverse",
            {"reason": "Mistake"},
        ).status_code
        == 201
    )
    assert len(pg.client.get("/loans?status=open").json()["items"]) == 1
