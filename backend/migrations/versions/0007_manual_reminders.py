"""Private template reminders, recipient permission, and durable delivery claims.

Revision ID: 0007_manual_reminders
Revises: 0006_event_action_width
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_manual_reminders"
down_revision = "0006_event_action_width"
branch_labels = None
depends_on = None
S = "iou_app"


def upgrade() -> None:
    op.create_table(
        "reminder_recipients",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("opted_out_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("in_flight", sa.Uuid()),
        schema=S,
    )
    op.create_table(
        "reminder_permissions",
        sa.Column("friend_id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("contact_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["friend_id", "owner_id"],
            [f"{S}.friends.id", f"{S}.friends.owner_id"],
            name="fk_reminder_permission_friend",
        ),
        schema=S,
    )
    op.create_index("ix_reminder_permissions_owner", "reminder_permissions", ["owner_id"], schema=S)
    op.create_table(
        "reminders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("friend_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_hash", sa.String(64), nullable=False),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("tone", sa.String(16), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.String(4000), nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("send_key", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("provider_message_id", sa.String(200)),
        sa.Column("error_code", sa.String(40)),
        sa.ForeignKeyConstraint(
            ["friend_id", "owner_id"],
            [f"{S}.friends.id", f"{S}.friends.owner_id"],
            name="fk_reminder_friend",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_hash"], [f"{S}.reminder_recipients.id"], name="fk_reminder_recipient"
        ),
        sa.UniqueConstraint("owner_id", "send_key", name="uq_reminder_send_key"),
        sa.CheckConstraint("tone IN ('friendly','playful','direct')", name="ck_reminder_tone"),
        sa.CheckConstraint(
            "status IN ('preview','reserved','sending','sent','failed','uncertain','cancelled')",
            name="ck_reminder_status",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_reminder_expiry"),
        sa.CheckConstraint(
            "(status = 'preview' AND send_key IS NULL) OR "
            "(status != 'preview' AND send_key IS NOT NULL)",
            name="ck_reminder_send_key",
        ),
        schema=S,
    )
    op.create_index(
        "ix_reminders_owner_created", "reminders", ["owner_id", "created_at", "id"], schema=S
    )
    for table in ("reminder_recipients", "reminder_permissions", "reminders"):
        op.execute(f"REVOKE ALL ON TABLE {S}.{table} FROM PUBLIC")
        op.execute(f"""DO $$ BEGIN
            IF EXISTS (SELECT FROM pg_roles WHERE rolname='anon') THEN
                REVOKE ALL ON TABLE {S}.{table} FROM anon;
            END IF;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') THEN
                REVOKE ALL ON TABLE {S}.{table} FROM authenticated;
            END IF;
        END $$;""")


def downgrade() -> None:
    op.execute(f"""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM {S}.reminders) OR EXISTS (SELECT 1 FROM {S}.reminder_permissions)
            OR EXISTS (SELECT 1 FROM {S}.reminder_recipients) THEN
            RAISE EXCEPTION 'Cannot downgrade while reminder records exist';
        END IF;
    END $$;""")
    op.drop_table("reminders", schema=S)
    op.drop_table("reminder_permissions", schema=S)
    op.drop_table("reminder_recipients", schema=S)
