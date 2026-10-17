"""private friends and basic lending

Revision ID: 0003_ledger
Revises: 0002_profiles
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_ledger"
down_revision: str | Sequence[str] | None = "0002_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed against the Level 1 models; composite keys enforce owner/kind boundaries.
    op.create_table(
        "friends",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(display_name)) BETWEEN 1 AND 100", name="ck_friend_name"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["iou_app.profiles.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_friends_id_owner"),
        schema="iou_app",
    )
    op.create_index(
        "ix_friends_owner_created",
        "friends",
        ["owner_id", "created_at", "id"],
        unique=False,
        schema="iou_app",
    )
    op.create_table(
        "mutation_receipts",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["iou_app.profiles.id"],
        ),
        sa.PrimaryKeyConstraint("owner_id", "key"),
        schema="iou_app",
    )
    op.create_table(
        "loans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("friend_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("principal_cents", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("lent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("overdue_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(kind = 'money' AND principal_cents IS NOT NULL AND currency IS NOT NULL "
            "AND principal_cents BETWEEN 1 AND 1000000000000 AND currency = 'USD') "
            "OR (kind = 'item' AND principal_cents IS NULL AND currency IS NULL)",
            name="ck_loan_terms",
        ),
        sa.CheckConstraint("kind IN ('money', 'item')", name="ck_loan_kind"),
        sa.CheckConstraint(
            "length(trim(description)) BETWEEN 1 AND 500", name="ck_loan_description"
        ),
        sa.CheckConstraint("overdue_at > lent_at", name="ck_loan_due_boundary"),
        sa.ForeignKeyConstraint(
            ["friend_id", "owner_id"],
            ["iou_app.friends.id", "iou_app.friends.owner_id"],
            name="fk_loan_friend_owner",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["iou_app.profiles.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", "kind", name="uq_loans_id_owner_kind"),
        schema="iou_app",
    )
    op.create_index(
        "ix_loans_owner_due", "loans", ["owner_id", "overdue_at"], unique=False, schema="iou_app"
    )
    op.create_index(
        "ix_loans_owner_friend_created",
        "loans",
        ["owner_id", "friend_id", "created_at", "id"],
        unique=False,
        schema="iou_app",
    )
    op.create_table(
        "loan_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("loan_id", sa.Uuid(), nullable=False),
        sa.Column("loan_kind", sa.String(length=10), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.String(length=2000), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(action = 'repayment' AND loan_kind = 'money' AND amount_cents IS NOT NULL "
            "AND amount_cents BETWEEN 1 AND 1000000000000) "
            "OR (action = 'return' AND loan_kind = 'item' AND amount_cents IS NULL)",
            name="ck_event_terms",
        ),
        sa.ForeignKeyConstraint(
            ["loan_id", "owner_id", "loan_kind"],
            ["iou_app.loans.id", "iou_app.loans.owner_id", "iou_app.loans.kind"],
            name="fk_event_loan_owner_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="iou_app",
    )
    op.create_index(
        "ix_events_owner_loan_time",
        "loan_events",
        ["owner_id", "loan_id", "effective_at", "id"],
        unique=False,
        schema="iou_app",
    )
    op.create_index(
        "uq_one_item_return",
        "loan_events",
        ["loan_id"],
        unique=True,
        schema="iou_app",
        postgresql_where=sa.text("action = 'return'"),
        sqlite_where=sa.text("action = 'return'"),
    )
    # Supabase may assign default table grants. Revoke browser access on every new table.
    for table in ("friends", "loans", "loan_events", "mutation_receipts"):
        op.execute(f"REVOKE ALL ON TABLE iou_app.{table} FROM PUBLIC")
        op.execute(f"""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    REVOKE ALL ON TABLE iou_app.{table} FROM anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    REVOKE ALL ON TABLE iou_app.{table} FROM authenticated;
                END IF;
            END $$
        """)


def downgrade() -> None:
    # DESTRUCTIVE: removes Level 1 contacts, obligations, events, and retry receipts.
    op.drop_index(
        "uq_one_item_return",
        table_name="loan_events",
        schema="iou_app",
        postgresql_where=sa.text("action = 'return'"),
        sqlite_where=sa.text("action = 'return'"),
    )
    op.drop_index("ix_events_owner_loan_time", table_name="loan_events", schema="iou_app")
    op.drop_table("loan_events", schema="iou_app")
    op.drop_index("ix_loans_owner_friend_created", table_name="loans", schema="iou_app")
    op.drop_index("ix_loans_owner_due", table_name="loans", schema="iou_app")
    op.drop_table("loans", schema="iou_app")
    op.drop_table("mutation_receipts", schema="iou_app")
    op.drop_index("ix_friends_owner_created", table_name="friends", schema="iou_app")
    op.drop_table("friends", schema="iou_app")
