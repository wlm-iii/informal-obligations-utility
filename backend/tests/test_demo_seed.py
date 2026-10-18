"""Seeder coverage and atomic/replay safeguards without real database or email access."""

import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from test_ledger import NOW, new_friend
from test_ledger import api as api

from iou.auth import Identity
from iou.demo_seed import apply
from iou.ledger import service
from iou.ledger.models import Audit, Friend, Loan, LoanEvent, MutationReceipt
from iou.profiles import Profile
from iou.reminders.models import Permission, Recipient, Reminder


@pytest.fixture
def dataset(api):
    assert api.client.get("/me").status_code == 200

    # SQLite's legacy driver otherwise RELEASEs a first SAVEPOINT as a top-level
    # commit. PostgreSQL has real outer transactions (also covered separately).
    def begin(connection):
        connection.exec_driver_sql("BEGIN")

    event.listen(api.engine, "begin", begin)
    yield api
    event.remove(api.engine, "begin", begin)


def counts(engine):
    with Session(engine) as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (
                Friend,
                Loan,
                LoanEvent,
                Audit,
                MutationReceipt,
                Profile,
                Permission,
                Reminder,
                Recipient,
            )
        )


def test_standalone_module_registers_all_audit_foreign_key_metadata():
    # API fixtures import every model; the standalone CLI must not depend on that.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import iou.demo_seed; from iou.database import Base; "
            "assert list(Base.metadata.sorted_tables)",
        ],
        env={
            **os.environ,
            "EMAIL_MODE": "disabled",
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "Standalone seeder metadata registration failed."


def test_demo_covers_ages_types_charges_and_auditable_states(dataset):
    api = dataset
    result = apply(api.engine, api.user, api.user.email)
    assert result["created_operations"] == 48
    assert result["replayed_operations"] == 0
    assert counts(api.engine) == (6, 23, 18, 2, 48, 1, 0, 0, 0)
    with Session(api.engine) as session:
        friends = session.scalars(select(Friend)).all()
        assert all(
            f.email == api.user.email and f.display_name.startswith("[DEMO]") for f in friends
        )
        loans = [
            service.loan_read(row, NOW) for row in session.execute(service.loan_query(api.user.id))
        ]
        assert {x.kind for x in loans} == {"money", "item"}
        assert {x.status for x in loans} == {"open", "completed", "voided"}
        assert {x.interest_period for x in loans if x.interest_rate_bps} == {
            "daily",
            "weekly",
            "monthly",
        }
        assert (NOW - min(service.utc(x.lent_at) for x in loans)).days == 180
        assert (NOW - max(service.utc(x.lent_at) for x in loans)).days == 1
        assert any(x.overdue and x.fees_cents == 0 and x.grace_days for x in loans)
        assert any(
            x.kind == "item" and x.borrowing_status == "returned" and x.fees_cents > 0
            for x in loans
        )
        assert any(x.fees_waived_cents == 200 and x.outstanding_cents == 6000 for x in loans)
        assert any(
            x.charge_cap_cents == 500 and x.interest_cents + x.fees_cents == 500 for x in loans
        )
        assert any(x.repayment_type == "other" and x.total_outstanding_cents > 0 for x in loans)
        assert sum(x.reversed_at is not None for x in session.scalars(select(LoanEvent))) == 1


def test_replay_is_stable_even_as_calendar_changes(dataset, monkeypatch):
    first = apply(dataset.engine, dataset.user, dataset.user.email)
    before = counts(dataset.engine)
    monkeypatch.setattr(service, "now_utc", lambda: NOW + timedelta(days=7))
    second = apply(dataset.engine, dataset.user, dataset.user.email)
    assert second["friends"] == first["friends"] and second["loans"] == first["loans"]
    assert second["anchor"] == first["anchor"]
    assert second["created_operations"] == 0 and second["replayed_operations"] == 48
    assert counts(dataset.engine) == before


def test_failure_rolls_back_whole_seed_and_preserves_existing_records(dataset, monkeypatch):
    old = new_friend(dataset, display_name="Pre-existing real record")
    before = counts(dataset.engine)
    original = service.settle
    calls = 0

    def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Injected test failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "settle", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        apply(dataset.engine, dataset.user, dataset.user.email)
    assert counts(dataset.engine) == before
    assert dataset.client.get(f"/friends/{old['id']}").status_code == 200


def test_requires_existing_matching_sender_profile(dataset):
    before = counts(dataset.engine)
    with pytest.raises(ValueError, match="existing profile"):
        apply(dataset.engine, Identity(uuid4(), dataset.user.email, "Missing"), dataset.user.email)
    with pytest.raises(ValueError, match="sender's own profile"):
        apply(dataset.engine, dataset.user, "not-the-sender@example.com")
    assert counts(dataset.engine) == before
