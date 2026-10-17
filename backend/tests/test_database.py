"""Run only against a disposable database: this test applies committed migrations."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from iou.database import get_engine

pytestmark = pytest.mark.database


def test_postgres_and_migrations():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = get_engine()
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
            assert "PostgreSQL" in connection.scalar(text("SELECT version()"))
        command.upgrade(config, "head")
        # Re-running must be harmless; verify schema and migration metadata agree.
        command.upgrade(config, "head")
        command.check(config)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "0001_baseline"
            )
    finally:
        engine.dispose()
