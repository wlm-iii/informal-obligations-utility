"""Informal repayment preferences, without changing financial settlement rules.

Revision ID: 0008_repayment_preferences
Revises: 0007_manual_reminders
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_repayment_preferences"
down_revision = "0007_manual_reminders"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("loans", sa.Column("repayment_type", sa.String(10)), schema="iou_app")
    op.add_column("loans", sa.Column("repayment_other", sa.String(500)), schema="iou_app")
    op.create_check_constraint(
        "ck_loan_repayment_preference",
        "loans",
        "(repayment_type IS NULL AND repayment_other IS NULL) OR "
        "(repayment_type IN ('item','money') AND repayment_other IS NULL) OR "
        "(repayment_type = 'other' AND repayment_other IS NOT NULL "
        "AND length(trim(repayment_other)) BETWEEN 1 AND 500)",
        schema="iou_app",
    )


def downgrade():
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM iou_app.loans WHERE repayment_type IS NOT NULL
                   OR repayment_other IS NOT NULL) THEN
            RAISE EXCEPTION 'Cannot discard repayment preference history';
        END IF;
    END $$;""")
    op.drop_constraint("ck_loan_repayment_preference", "loans", schema="iou_app")
    op.drop_column("loans", "repayment_other", schema="iou_app")
    op.drop_column("loans", "repayment_type", schema="iou_app")
