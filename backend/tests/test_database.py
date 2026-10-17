"""Run only against a disposable database: this test applies committed migrations."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect, text
from sqlalchemy.orm import Session

from iou.api import app
from iou.auth import Identity, get_current_user
from iou.database import get_engine, get_session
from iou.profiles import Profile

pytestmark = pytest.mark.database


def test_postgres_and_migrations():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = get_engine()
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
            assert connection.scalar(text("SHOW transaction_isolation")) == "read committed"
            assert "PostgreSQL" in connection.scalar(text("SELECT version()"))
        command.upgrade(config, "head")
        # Re-running must be harmless; verify schema and migration metadata agree.
        command.upgrade(config, "head")
        command.check(config)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "0003_ledger"
            )
            tables = ("profiles", "friends", "loans", "loan_events", "mutation_receipts")
            assert set(tables) <= set(inspect(connection).get_table_names(schema="iou_app"))
            # PostgreSQL ACLs defend the private schema independently of HTTP authorization.
            for role in ("anon", "authenticated"):
                if connection.scalar(
                    text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}
                ):
                    assert not connection.scalar(
                        text("SELECT has_schema_privilege(:role, 'iou_app', 'USAGE')"),
                        {"role": role},
                    )
                    for table in tables:
                        assert not connection.scalar(
                            text("SELECT has_table_privilege(:role, :table, 'SELECT')"),
                            {"role": role, "table": f"iou_app.{table}"},
                        )
    finally:
        engine.dispose()


def test_profile_routes_on_postgres():
    engine = get_engine()
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    users = [Identity(uuid4(), "test@example.com", "First"), Identity(uuid4(), None, "Second")]
    current = users[0]

    def session_dependency():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_current_user] = lambda: current
    try:
        with TestClient(app) as client:
            first = client.get("/me")
            assert first.status_code == 200
            assert first.json()["created_at"].endswith("Z")
            current = users[1]
            assert client.patch("/me", json={"display_name": "Changed"}).status_code == 200
            current = users[0]
            assert client.get("/me").json()["display_name"] == "First"
    finally:
        app.dependency_overrides.clear()
        with Session(engine) as session:
            session.execute(delete(Profile).where(Profile.id.in_([user.id for user in users])))
            session.commit()
        engine.dispose()
