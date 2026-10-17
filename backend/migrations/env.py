"""Alembic configuration. Import all future model modules before reading metadata."""

from alembic import context

from iou.config import get_settings
from iou.database import Base, get_engine
from iou.evidence import models as evidence_models  # noqa: F401 -- register evidence metadata
from iou.ledger import models  # noqa: F401 -- register ledger migration metadata
from iou.profiles import Profile  # noqa: F401 -- register migration metadata

# Import future model modules here so autogenerate sees their tables.
target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    # Do not inspect or propose dropping Supabase-managed auth/storage/public tables.
    if type_ == "schema":
        return name in (None, "iou_app")
    if type_ == "table":
        return parent_names.get("schema_name") == "iou_app"
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_schemas=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
