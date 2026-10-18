from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DBAPIError
from test_ledger_database import pg as pg
from test_ledger_database import post

pytestmark = pytest.mark.database


def test_preference_migration_preserves_metadata_and_blocks_loss(pg):
    friend = post(pg, "/friends", {"display_name": "Alex"}).json()
    result = post(
        pg,
        "/loans",
        {
            "friend_id": friend["id"],
            "kind": "money",
            "description": "Lunch",
            "principal_cents": 5000,
            "due_date": (datetime.now(UTC) + timedelta(days=1)).date().isoformat(),
            "repayment_type": "other",
            "repayment_other": "Lunch together",
        },
    )
    assert result.status_code == 201, result.text
    loan = result.json()
    assert pg.client.get(f"/loans/{loan['id']}").json()["repayment_other"] == "Lunch together"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with pytest.raises(DBAPIError):
        command.downgrade(config, "0007_manual_reminders")
    assert pg.client.get(f"/loans/{loan['id']}").json()["repayment_type"] == "other"
