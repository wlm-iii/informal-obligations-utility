"""Real PostgreSQL transaction/constraint tests. Disposable databases only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from iou.api import app
from iou.auth import Identity, get_current_user
from iou.database import get_engine, get_session
from iou.evidence.models import Evidence
from iou.ledger.models import Audit, Friend, Loan, LoanEvent, MutationReceipt
from iou.profiles import Profile, get_or_create_profile

pytestmark = pytest.mark.database


@pytest.fixture
def pg():
    engine = get_engine()
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    users = [Identity(uuid4(), "first@example.com", "First"), Identity(uuid4(), None, "Second")]
    state = SimpleNamespace(engine=engine, users=users, user=users[0])

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    app.dependency_overrides[get_current_user] = lambda: state.user
    try:
        with TestClient(app) as client:
            state.client = client
            yield state
    finally:
        app.dependency_overrides.clear()
        ids = [u.id for u in users]
        with Session(engine) as session:
            for model in (Audit, Evidence, LoanEvent, MutationReceipt, Loan, Friend):
                session.execute(delete(model).where(model.owner_id.in_(ids)))
            session.execute(delete(Profile).where(Profile.id.in_(ids)))
            session.commit()
        engine.dispose()


def post(pg, path, body=None, key=None):
    return pg.client.post(
        path,
        headers={"Idempotency-Key": str(key or uuid4())},
        **({"json": body} if body is not None else {}),
    )


def create_loan(pg, kind="money"):
    friend = post(pg, "/friends", {"display_name": "Alex"})
    assert friend.status_code == 201, friend.text
    now = datetime.now(UTC)
    body = {
        "friend_id": friend.json()["id"],
        "kind": kind,
        "description": "Test",
        "lent_at": (now - timedelta(days=1)).isoformat(),
        "due_date": (now + timedelta(days=1)).date().isoformat(),
    }
    if kind == "money":
        body["principal_cents"] = 5000
    loan = post(pg, "/loans", body)
    assert loan.status_code == 201, loan.text
    return loan.json()


def race(*actions):
    barrier = Barrier(len(actions))

    def run(action):
        barrier.wait(timeout=10)
        return action()

    with ThreadPoolExecutor(max_workers=len(actions)) as executor:
        futures = [executor.submit(run, action) for action in actions]
        return [future.result(timeout=20) for future in futures]


def test_concurrent_first_access_and_same_friend_key(pg):
    # Profile doesn't exist yet: profile provisioning and receipt replay both race.
    key = uuid4()
    responses = race(
        *[lambda: post(pg, "/friends", {"display_name": "Alex"}, key) for _ in range(4)]
    )
    assert all(r.status_code == 201 for r in responses)
    assert len({r.json()["id"] for r in responses}) == 1
    with Session(pg.engine) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Friend).where(Friend.owner_id == pg.user.id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count()).select_from(Profile).where(Profile.id == pg.user.id)
            )
            == 1
        )


def test_concurrent_distinct_payments_cannot_overpay(pg):
    loan = create_loan(pg)
    path = f"/loans/{loan['id']}/repayments"
    responses = race(
        lambda: post(pg, path, {"amount_cents": 4000}),
        lambda: post(pg, path, {"amount_cents": 4000}),
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert pg.client.get(f"/loans/{loan['id']}").json()["outstanding_cents"] == 1000
    with Session(pg.engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(LoanEvent)
                .where(LoanEvent.loan_id == UUID(loan["id"]))
            )
            == 1
        )


def test_concurrent_same_payment_key_records_one_event(pg):
    loan = create_loan(pg)
    path = f"/loans/{loan['id']}/repayments"
    key = uuid4()
    responses = race(
        lambda: post(pg, path, {"amount_cents": 2500}, key),
        lambda: post(pg, path, {"amount_cents": 2500}, key),
    )
    assert [r.status_code for r in responses] == [201, 201]
    assert responses[0].json() == responses[1].json()
    assert pg.client.get(f"/loans/{loan['id']}").json()["outstanding_cents"] == 2500


def test_concurrent_key_reuse_with_different_payment_conflicts(pg):
    loan = create_loan(pg)
    path = f"/loans/{loan['id']}/repayments"
    key = uuid4()
    responses = race(
        lambda: post(pg, path, {"amount_cents": 1000}, key),
        lambda: post(pg, path, {"amount_cents": 2000}, key),
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    accepted = next(r.json() for r in responses if r.status_code == 201)
    assert (
        pg.client.get(f"/loans/{loan['id']}").json()["repaid_cents"]
        == accepted["event"]["amount_cents"]
    )


def test_concurrent_same_loan_key_creates_one_loan(pg):
    friend = post(pg, "/friends", {"display_name": "Alex"}).json()
    key = uuid4()
    body = {
        "friend_id": friend["id"],
        "kind": "item",
        "description": "Hoodie",
        "due_date": (datetime.now(UTC) + timedelta(days=1)).date().isoformat(),
    }
    responses = race(lambda: post(pg, "/loans", body, key), lambda: post(pg, "/loans", body, key))
    assert all(r.status_code == 201 for r in responses)
    assert responses[0].json() == responses[1].json()
    assert len(pg.client.get("/loans").json()["items"]) == 1


@pytest.mark.parametrize("same_key", [False, True])
def test_concurrent_returns(pg, same_key):
    loan = create_loan(pg, "item")
    path = f"/loans/{loan['id']}/return"
    first = uuid4()
    second = first if same_key else uuid4()
    responses = race(lambda: post(pg, path, key=first), lambda: post(pg, path, key=second))
    assert sorted(r.status_code for r in responses) == ([201, 201] if same_key else [201, 409])
    if same_key:
        assert responses[0].json() == responses[1].json()
    with Session(pg.engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(LoanEvent)
                .where(LoanEvent.loan_id == UUID(loan["id"]))
            )
            == 1
        )


def test_archive_and_create_are_serialized(pg):
    friend = post(pg, "/friends", {"display_name": "Alex"}).json()
    body = {
        "friend_id": friend["id"],
        "kind": "item",
        "description": "Hoodie",
        "due_date": (datetime.now(UTC) + timedelta(days=1)).date().isoformat(),
    }
    archived, loan = race(
        lambda: pg.client.post(f"/friends/{friend['id']}/archive"), lambda: post(pg, "/loans", body)
    )
    assert archived.status_code == 200
    assert loan.status_code in (201, 409)
    if loan.status_code == 201:
        assert datetime.fromisoformat(loan.json()["created_at"]) <= datetime.fromisoformat(
            archived.json()["archived_at"]
        )
    assert post(pg, "/loans", body).status_code == 409


def test_full_lifecycle_history_and_filters_on_postgres(pg):
    money = create_loan(pg)
    item = post(
        pg,
        "/loans",
        {
            "friend_id": money["friend_id"],
            "kind": "item",
            "description": "Hoodie",
            "due_date": money["due_date"],
        },
    ).json()
    assert len(pg.client.get("/loans?kind=item&overdue=false&status=open").json()["items"]) == 1
    assert post(pg, f"/loans/{money['id']}/repayments", {"amount_cents": 2000}).status_code == 201
    assert pg.client.post(f"/friends/{money['friend_id']}/archive").status_code == 200
    assert post(pg, f"/loans/{money['id']}/repayments", {"amount_cents": 3000}).status_code == 201
    assert post(pg, f"/loans/{item['id']}/return").status_code == 201
    assert len(pg.client.get("/loans?status=completed&overdue=false").json()["items"]) == 2
    assert pg.client.get("/loans?status=open").json()["items"] == []
    page = pg.client.get(f"/friends/{money['friend_id']}/history?limit=2").json()
    assert len(page["items"]) == 2 and page["has_more"]
    rows = pg.client.get(f"/friends/{money['friend_id']}/history").json()["items"]
    assert len(rows) == 5
    assert all(row["recorded_at"].endswith("Z") for row in rows)
    pg.user = pg.users[1]
    assert pg.client.get(f"/friends/{money['friend_id']}/history").status_code == 404
    assert pg.client.get("/loans").json()["items"] == []


def test_database_rejects_cross_owner_friend_and_invalid_terms(pg):
    loan = create_loan(pg)
    other = pg.users[1]
    with Session(pg.engine) as session:
        get_or_create_profile(session, other)
    with Session(pg.engine) as session:
        original = session.get(Loan, UUID(loan["id"]))
        fields = {column.name: getattr(original, column.name) for column in Loan.__table__.columns}
    cases = [
        {"owner_id": other.id},
        {"principal_cents": None},
        {"currency": None},
        {"principal_cents": -1},
        {"kind": "item"},
    ]
    for changes in cases:
        with Session(pg.engine) as session:
            session.add(Loan(**{**fields, "id": uuid4(), **changes}))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()


def test_database_rejects_invalid_events_and_duplicate_returns(pg):
    money = create_loan(pg)
    item = create_loan(pg, "item")
    now = datetime.now(UTC)
    base = {
        "id": uuid4(),
        "owner_id": pg.user.id,
        "loan_id": UUID(money["id"]),
        "loan_kind": "money",
        "action": "repayment",
        "amount_cents": 100,
        "effective_at": now,
        "recorded_at": now,
    }
    with Session(pg.engine) as session:
        get_or_create_profile(session, pg.users[1])
    cases = [
        {"amount_cents": -1},
        {"amount_cents": None},
        {"amount_cents": 1_000_000_000_001},
        {"owner_id": pg.users[1].id},
        {"loan_id": UUID(item["id"])},
        {"action": "return", "amount_cents": None},
    ]
    for changes in cases:
        with Session(pg.engine) as session:
            session.add(LoanEvent(**{**base, **changes, "id": uuid4()}))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    assert post(pg, f"/loans/{item['id']}/return").status_code == 201
    with Session(pg.engine) as session:
        session.add(
            LoanEvent(
                **{
                    **base,
                    "id": uuid4(),
                    "loan_id": UUID(item["id"]),
                    "loan_kind": "item",
                    "action": "return",
                    "amount_cents": None,
                }
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
