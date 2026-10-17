"""SQLAlchemy foundation. Importing this module does not open a connection."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from iou.config import get_settings


class Base(DeclarativeBase):
    """Future domain models inherit from this base and are imported by Alembic."""


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if settings.database_pool_mode == "transaction":
        # Supabase transaction pooling: no client-side pool or prepared statements.
        return create_engine(
            settings.database_url,
            poolclass=NullPool,
            connect_args={"prepare_threshold": None},
        )
    return create_engine(settings.database_url, pool_pre_ping=True, pool_size=3, max_overflow=2)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: callers explicitly commit; failures roll back on close."""
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as session:
        yield session
