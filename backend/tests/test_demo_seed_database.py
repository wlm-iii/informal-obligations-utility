"""Atomic real-PostgreSQL seed acceptance; run on explicitly disposable databases only."""

import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_ledger_database import pg as pg
from test_ledger_database import post

from iou.demo_seed import apply
from iou.ledger import service
from iou.ledger.models import Audit, Friend, Loan, LoanEvent, MutationReceipt
from iou.reminders import gmail
from iou.reminders.models import Permission, Reminder

pytestmark = pytest.mark.database


def counts(engine, owner):
    with Session(engine) as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model).where(model.owner_id == owner))
            for model in (Friend, Loan, LoanEvent, Audit, MutationReceipt, Permission, Reminder)
        )


def test_atomic_seed_replays_without_email_or_touching_another_owner(pg, monkeypatch):
    # Provision both owners normally. Other owner's records must remain unchanged.
    pg.user = pg.users[1]
    post(pg, "/friends", {"display_name": "Other owner's original friend"})
    other_before = counts(pg.engine, pg.user.id)
    pg.user = pg.users[0]
    assert pg.client.get("/me").status_code == 200

    def forbidden():
        raise AssertionError("Seeding must never prepare or send email")

    monkeypatch.setattr(gmail, "get_mailer", forbidden)
    # Run the first application without importing the API/model registry in the child,
    # exactly like the standalone operator command (against this disposable DB only).
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json,sys; from uuid import UUID; "
            "from iou.auth import Identity; from iou.database import get_engine; "
            "from iou.demo_seed import apply; "
            "print(json.dumps(apply(get_engine(), "
            "Identity(UUID(sys.argv[1]), 'first@example.com', 'First'), 'first@example.com')))",
            str(pg.user.id),
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
    assert child.returncode == 0, "Standalone PostgreSQL seeder failed."
    first = json.loads(child.stdout)
    assert counts(pg.engine, pg.user.id) == (6, 23, 18, 2, 48, 0, 0)
    now = service.now_utc()
    monkeypatch.setattr(service, "now_utc", lambda: now + timedelta(days=10))
    second = apply(pg.engine, pg.user, pg.user.email)
    assert second["created_operations"] == 0 and second["replayed_operations"] == 48
    assert second["loans"] == first["loans"] and second["anchor"] == first["anchor"]
    assert counts(pg.engine, pg.user.id) == (6, 23, 18, 2, 48, 0, 0)
    assert counts(pg.engine, pg.users[1].id) == other_before


def test_failure_after_committed_savepoints_rolls_back_entire_postgresql_seed(pg, monkeypatch):
    assert pg.client.get("/me").status_code == 200
    baseline = counts(pg.engine, pg.user.id)
    original = service.settle
    called = 0

    def fail(*args, **kwargs):
        nonlocal called
        called += 1
        if called == 3:
            raise RuntimeError("Injected seed failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "settle", fail)
    with pytest.raises(RuntimeError, match="Injected seed failure"):
        apply(pg.engine, pg.user, pg.user.email)
    assert counts(pg.engine, pg.user.id) == baseline
