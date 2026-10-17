from unittest.mock import Mock

from sqlalchemy.pool import NullPool

from iou import database
from iou.config import Settings


def test_session_pool_is_small(monkeypatch):
    settings = Settings(_env_file=None, database_pool_mode="session")
    create = Mock()
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(database, "create_engine", create)
    database.get_engine.__wrapped__()
    assert create.call_args.kwargs == {
        "pool_pre_ping": True,
        "pool_size": 3,
        "max_overflow": 2,
        "isolation_level": "READ COMMITTED",
    }


def test_transaction_pool_disables_prepared_statements_and_double_pooling(monkeypatch):
    settings = Settings(_env_file=None, database_pool_mode="transaction")
    create = Mock()
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.setattr(database, "create_engine", create)
    database.get_engine.__wrapped__()
    assert create.call_args.kwargs == {
        "poolclass": NullPool,
        "connect_args": {"prepare_threshold": None},
        "isolation_level": "READ COMMITTED",
    }
