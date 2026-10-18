"""Store IOU repayment preferences and agreed interest percentage.

Revision ID: 0004_iou_preferences
Revises: 0003_ledger
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_iou_preferences"
down_revision = "0003_ledger"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("loans", sa.Column("repayment_type", sa.String(10)), schema="iou_app")
    op.add_column("loans", sa.Column("repayment_other", sa.String(500)), schema="iou_app")
    op.add_column(
        "loans",
        sa.Column("interest_percent", sa.Integer(), nullable=False, server_default="0"),
        schema="iou_app",
    )
    op.create_check_constraint(
        "ck_loan_interest_percent",
        "loans",
        "interest_percent BETWEEN 0 AND 1000",
        schema="iou_app",
    )
    op.create_check_constraint(
        "ck_loan_repayment_preference",
        "loans",
        "(repayment_type IS NULL AND repayment_other IS NULL) OR "
        "(repayment_type IN ('item', 'money') AND repayment_other IS NULL) OR "
        "(repayment_type = 'other' AND repayment_other IS NOT NULL "
        "AND length(trim(repayment_other)) BETWEEN 1 AND 500)",
        schema="iou_app",
    )


def downgrade():
    op.drop_constraint("ck_loan_repayment_preference", "loans", schema="iou_app")
    op.drop_constraint("ck_loan_interest_percent", "loans", schema="iou_app")
    for column in ("interest_percent", "repayment_other", "repayment_type"):
        op.drop_column("loans", column, schema="iou_app")
