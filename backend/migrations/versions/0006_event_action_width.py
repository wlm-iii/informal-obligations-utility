"""Allow Level 3 item fee-payment action names without truncation.

Revision ID: 0006_event_action_width
Revises: 0005_charges_scores
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_event_action_width"
down_revision = "0005_charges_scores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "loan_events",
        "action",
        schema="iou_app",
        existing_type=sa.String(10),
        type_=sa.String(16),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Preserve even reversed financial history; never truncate an action name.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM iou_app.loan_events WHERE length(action) > 10) THEN
                RAISE EXCEPTION 'Cannot downgrade event action width while longer actions exist';
            END IF;
        END $$;
    """)
    op.alter_column(
        "loan_events",
        "action",
        schema="iou_app",
        existing_type=sa.String(16),
        type_=sa.String(10),
        existing_nullable=False,
    )
