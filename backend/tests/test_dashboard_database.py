"""Dashboard snapshot/locking guarantees against disposable PostgreSQL only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_ledger_database import create_loan, post
from test_ledger_database import pg as pg

from iou.ledger import service
from iou.ledger.models import LoanEvent, MutationReceipt
from iou.profiles import Profile

pytestmark = pytest.mark.database


def test_dashboard_reconciles_on_postgresql_without_writes(pg):
    money = create_loan(pg)
    assert post(pg, f"/loans/{money['id']}/repayments", {"amount_cents": 1000}).status_code == 201
    now = datetime.now(UTC)
    friend = post(pg, "/friends", {"display_name": "Hoodie friend"}).json()
    item = post(
        pg,
        "/loans",
        {
            "friend_id": friend["id"],
            "kind": "item",
            "description": "Hoodie",
            "lent_at": (now - timedelta(days=3)).isoformat(),
            "due_date": (now - timedelta(days=1)).date().isoformat(),
            "late_fee_cents": 500,
        },
    ).json()
    assert post(pg, f"/loans/{item['id']}/return").status_code == 201
    payment = post(pg, f"/loans/{item['id']}/fee-payments", {"amount_cents": 200})
    assert payment.status_code == 201, payment.text

    def counts():
        with Session(pg.engine) as session:
            return [
                session.scalar(
                    select(func.count()).select_from(model).where(model.owner_id == pg.user.id)
                )
                for model in (LoanEvent, MutationReceipt)
            ]

    before = counts()
    summary = pg.client.get("/dashboard/summary")
    assert summary.status_code == 200, summary.text
    assert summary.headers["cache-control"] == "no-store"
    metrics = summary.json()["metrics"]
    assert metrics["outstanding"] == dict(
        principal_cents=4000, interest_cents=0, fees_cents=300, total_cents=4300
    )
    assert metrics["cash_received"]["total_cents"] == 1200
    assert metrics["items_returned"] == metrics["returned_items_unpaid_count"] == 1
    trends = pg.client.get("/dashboard/trends").json()
    assert trends["totals"]["cash_received"] == metrics["cash_received"]
    assert pg.client.get("/dashboard/rankings").json()["total"] == 2
    assert pg.client.get("/dashboard/obligations?group=returned_unpaid").json()["total"] == 1
    assert counts() == before
    # Both active and reversed long action names must survive; no truncating rollback.
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with pytest.raises(DBAPIError):
        command.downgrade(config, "0005_charges_scores")
    assert pg.client.get("/dashboard/summary").json()["metrics"] == metrics
    event_id = payment.json()["event"]["id"]
    assert (
        post(
            pg, f"/loans/{item['id']}/events/{event_id}/reverse", {"reason": "Not actually paid"}
        ).status_code
        == 201
    )
    with pytest.raises(DBAPIError):
        command.downgrade(config, "0005_charges_scores")
    assert pg.client.get("/dashboard/summary").json()["metrics"]["outstanding"]["fees_cents"] == 500


def test_dashboard_shared_owner_lock_blocks_financial_writes_not_other_owners(pg, monkeypatch):
    loan = create_loan(pg)
    reading, release = Event(), Event()
    original = service.loan_read

    def pause(row, at):
        if not reading.is_set():
            reading.set()
            assert release.wait(timeout=10)
        return original(row, at)

    monkeypatch.setattr(service, "loan_read", pause)
    owner = pg.user
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(pg.client.get, "/dashboard/summary")
        try:
            assert reading.wait(timeout=10)
            # This is the exclusive lock taken by every financial mutation.
            with pytest.raises(DBAPIError) as error, Session(pg.engine) as session:
                session.execute(text("SET LOCAL lock_timeout='200ms'"))
                session.scalar(select(Profile).where(Profile.id == owner.id).with_for_update())
            assert error.value.orig.sqlstate == "55P03"
            pg.user = pg.users[1]
            create_loan(pg)  # Another owner's writes remain independent.
        finally:
            pg.user = owner
            release.set()
        result = future.result(timeout=10)
    assert result.status_code == 200, result.text
    assert result.json()["friend_count"] == 1
    assert post(pg, f"/loans/{loan['id']}/repayments", {"amount_cents": 1000}).status_code == 201
    assert (
        pg.client.get("/dashboard/summary").json()["metrics"]["outstanding"]["total_cents"] == 4000
    )
