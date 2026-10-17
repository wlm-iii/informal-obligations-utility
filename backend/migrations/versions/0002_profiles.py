"""Private owner profiles. No changes to Supabase-managed auth tables.

Revision ID: 0002_profiles
Revises: 0001_baseline
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_profiles"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS iou_app")
    op.execute("REVOKE ALL ON SCHEMA iou_app FROM PUBLIC")
    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("timezone", sa.String(100), server_default="UTC", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="iou_app",
    )
    op.execute("REVOKE ALL ON TABLE iou_app.profiles FROM PUBLIC")
    # These roles exist on Supabase, not necessarily on a plain local PostgreSQL.
    # No browser-accessible role may use our schema, even if someone exposes it later.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL ON SCHEMA iou_app FROM anon;
                REVOKE ALL ON TABLE iou_app.profiles FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL ON SCHEMA iou_app FROM authenticated;
                REVOKE ALL ON TABLE iou_app.profiles FROM authenticated;
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.drop_table("profiles", schema="iou_app")
    # Leave the schema in place: future tables or grants may share it.
