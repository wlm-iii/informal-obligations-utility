from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from test_evidence import FakeStorage, image_bytes
from test_ledger_database import create_loan, post, race
from test_ledger_database import pg as pg

from iou.config import Settings
from iou.evidence import cleanup
from iou.evidence import service as evidence
from iou.evidence.models import Evidence
from iou.ledger import pagination
from iou.ledger import service as ledger
from iou.ledger.models import Audit, LoanEvent
from iou.profiles import Profile, get_or_create_profile

pytestmark = pytest.mark.database


def payment(pg, amount=2000):
    loan = create_loan(pg)
    result = post(pg, f"/loans/{loan['id']}/repayments", {"amount_cents": amount})
    assert result.status_code == 201
    return loan, result.json()["event"]


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_corrections_reverse_original_once(pg, same_key):
    loan, event = payment(pg)
    path = f"/loans/{loan['id']}/events/{event['id']}/correct"
    body = {"reason": "Wrong amount", "replacement": {"action": "repayment", "amount_cents": 1000}}
    first = uuid4()
    second = first if same_key else uuid4()
    responses = race(lambda: post(pg, path, body, first), lambda: post(pg, path, body, second))
    assert sorted(r.status_code for r in responses) == ([201, 201] if same_key else [201, 409])
    assert pg.client.get(f"/loans/{loan['id']}").json()["repaid_cents"] == 1000
    with Session(pg.engine) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Audit).where(Audit.owner_id == pg.user.id)
            )
            == 1
        )


def test_correction_races_later_repayment_without_overpay(pg):
    loan, event = payment(pg)
    correction, repayment = race(
        lambda: post(
            pg,
            f"/loans/{loan['id']}/events/{event['id']}/correct",
            {
                "reason": "Actually forty",
                "replacement": {"action": "repayment", "amount_cents": 4000},
            },
        ),
        lambda: post(pg, f"/loans/{loan['id']}/repayments", {"amount_cents": 2000}),
    )
    assert sorted((correction.status_code, repayment.status_code)) == [201, 409]
    assert pg.client.get(f"/loans/{loan['id']}").json()["repaid_cents"] == 4000


def test_void_and_settlement_cannot_both_succeed(pg):
    loan = create_loan(pg)
    responses = race(
        lambda: post(pg, f"/loans/{loan['id']}/void", {"reason": "Mistake"}),
        lambda: post(pg, f"/loans/{loan['id']}/repayments", {"amount_cents": 1}),
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    row = pg.client.get(f"/loans/{loan['id']}").json()
    assert (row["status"], row["repaid_cents"]) in (("voided", 0), ("open", 1))


def test_item_reversal_and_replacement_keep_one_active_return(pg):
    loan = create_loan(pg, "item")
    event = post(pg, f"/loans/{loan['id']}/return").json()["event"]
    result = post(
        pg,
        f"/loans/{loan['id']}/events/{event['id']}/correct",
        {
            "reason": "Wrong timestamp",
            "replacement": {"action": "return"},
        },
    )
    assert result.status_code == 201
    assert result.json()["replacement"]["replaces_event_id"] == event["id"]
    assert post(pg, f"/loans/{loan['id']}/return").status_code == 409
    with Session(pg.engine) as session:
        count = session.scalar(
            select(func.count())
            .select_from(LoanEvent)
            .where(
                LoanEvent.loan_id == UUID(loan["id"]),
                LoanEvent.reversed_at.is_(None),
            )
        )
        assert count == 1


def test_downgrade_refuses_to_erase_recorded_audit(pg):
    loan, event = payment(pg)
    assert (
        post(
            pg, f"/loans/{loan['id']}/events/{event['id']}/reverse", {"reason": "Mistake"}
        ).status_code
        == 201
    )
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with pytest.raises(DBAPIError):
        command.downgrade(config, "0003_ledger")
    with pg.engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0007_manual_reminders"
        )
    assert pg.client.get(f"/loans/{loan['id']}").json()["outstanding_cents"] == 5000


def test_cursor_history_and_filters_on_postgres(pg, monkeypatch):
    settings = Settings(_env_file=None, cursor_signing_key="p" * 32)
    monkeypatch.setattr(pagination, "get_settings", lambda: settings)
    now = datetime.now(UTC)
    monkeypatch.setattr(ledger, "now_utc", lambda: now)
    loan, event = payment(pg)
    post(
        pg,
        f"/loans/{loan['id']}/events/{event['id']}/correct",
        {
            "reason": "Ten",
            "replacement": {"action": "repayment", "amount_cents": 1000},
        },
    )
    path = f"/friends/{loan['friend_id']}/history"
    page = pg.client.get(path, params={"pagination": "cursor", "limit": 2}).json()
    rows = list(page["items"])
    assert page["next_cursor"]
    while page["next_cursor"]:
        response = pg.client.get(path, params={"cursor": page["next_cursor"], "limit": 2})
        assert response.status_code == 200, response.text
        page = response.json()
        rows.extend(page["items"])
    assert len(rows) == 4 and len({r["id"] for r in rows}) == 4
    assert {r["action"] for r in rows} == {"lent", "repayment", "reversal"}
    assert all(r["recorded_at"].endswith("Z") for r in rows)


class UnlockedStorage(FakeStorage):
    def __init__(self, pg):
        super().__init__()
        self.pg = pg
        self.barrier = None

    def probe(self):
        with Session(self.pg.engine) as session:
            # NOWAIT would fail if a provider operation held the owner's transaction lock.
            session.scalar(
                select(Profile).where(Profile.id == self.pg.user.id).with_for_update(nowait=True)
            )
            session.rollback()

    def upload(self, *args):
        if self.barrier:
            # Concurrent requests may legitimately hold each other's brief claim lock.
            # Both reaching this barrier proves neither holds its lock during I/O.
            self.barrier.wait(timeout=10)
        else:
            self.probe()
        super().upload(*args)

    def signed_url(self, *args):
        self.probe()
        return super().signed_url(*args)

    def delete(self, *args):
        self.probe()
        return super().delete(*args)


@pytest.fixture
def store(pg, monkeypatch):
    fake = UnlockedStorage(pg)
    monkeypatch.setattr(evidence, "get_storage", lambda *args: fake)
    monkeypatch.setattr(cleanup, "get_storage", lambda *args: fake)
    return fake


def new_intent(pg, loan=None):
    loan = loan or create_loan(pg)
    response = post(
        pg, f"/loans/{loan['id']}/evidence", {"filename": "proof.png", "content_type": "image/png"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def put(pg, row):
    return pg.client.put(
        f"/evidence/{row['id']}/content",
        content=image_bytes(),
        headers={"Content-Type": "image/png"},
    )


def test_storage_calls_do_not_hold_owner_lock_and_cleanup_is_durable(pg, store):
    row = new_intent(pg)
    assert put(pg, row).status_code == 200
    assert pg.client.post(f"/evidence/{row['id']}/view-url").status_code == 200
    assert post(pg, f"/evidence/{row['id']}/remove", {"reason": "Private"}).status_code == 201
    assert cleanup.cleanup_batch(pg.engine, apply=True)["cleaned"] == 1
    assert not store.files


def test_concurrent_uploads_create_one_added_audit(pg, store):
    row = new_intent(pg)
    store.barrier = Barrier(2)
    responses = race(lambda: put(pg, row), lambda: put(pg, row))
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json() == responses[1].json()
    with Session(pg.engine) as session:
        count = session.scalar(
            select(func.count())
            .select_from(Audit)
            .where(Audit.evidence_id == UUID(row["id"]), Audit.action == "evidence_added")
        )
        assert count == 1


def test_removal_during_postgres_upload_never_publishes(pg, store):
    row = new_intent(pg)
    store.on_upload = lambda: post(pg, f"/evidence/{row['id']}/remove", {"reason": "Wrong file"})
    result = put(pg, row)
    assert result.status_code == 409
    assert not store.files
    assert pg.client.get(f"/evidence/{row['id']}").json()["state"] == "removed"


def test_evidence_and_audit_composite_keys_block_cross_owner_rows(pg, store):
    loan, event = payment(pg)
    with Session(pg.engine) as session:
        get_or_create_profile(session, pg.users[1])
    with Session(pg.engine) as session:
        session.add(
            Evidence(
                id=uuid4(),
                owner_id=pg.users[1].id,
                loan_id=UUID(loan["id"]),
                bucket=store.bucket,
                storage_origin=store.origin,
                filename="x.png",
                content_type="image/png",
                state="pending",
                created_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    assert (
        post(pg, f"/loans/{loan['id']}/events/{event['id']}/reverse", {"reason": "X"}).status_code
        == 201
    )
    with Session(pg.engine) as session:
        session.add(
            Audit(
                id=uuid4(),
                owner_id=pg.user.id,
                loan_id=UUID(loan["id"]),
                action="reversal",
                reason="Twice",
                event_id=UUID(event["id"]),
                actor="owner",
                effective_at=datetime.now(UTC),
                recorded_at=datetime.now(UTC),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
