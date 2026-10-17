"""Periodic optional charges, immutable allocations, and settlement projection.

Revision ID: 0005_charges_scores
Revises: 0004_history_proof

Existing loans are explicitly version 0, with zero interest/fees/grace/cap.
Old repayments remain principal-only; no historical financial fields are repriced.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_charges_scores"
down_revision = "0004_history_proof"
branch_labels = None
depends_on = None
S = "iou_app"

EVENT_TERMS = (
    "((action = 'repayment' AND loan_kind = 'money') OR "
    "(action = 'fee_payment' AND loan_kind = 'item')) "
    "AND amount_cents BETWEEN 1 AND 1000000000000 AND amount_cents IS NOT NULL "
    "AND component IS NULL AND reason IS NULL OR "
    "(action = 'return' AND loan_kind = 'item' AND amount_cents IS NULL "
    "AND component IS NULL AND reason IS NULL) OR "
    "(action = 'waiver' AND amount_cents IS NOT NULL AND amount_cents BETWEEN 1 AND 1000000000000 "
    "AND component IN ('interest','fees') AND component IS NOT NULL AND reason IS NOT NULL "
    "AND length(trim(reason)) BETWEEN 1 AND 1000)"
)
ALLOCATION = (
    "(action = 'return' AND principal_applied_cents IS NULL AND interest_applied_cents IS NULL "
    "AND fees_applied_cents IS NULL) OR "
    "(action != 'return' AND principal_applied_cents IS NOT NULL "
    "AND interest_applied_cents IS NOT NULL AND fees_applied_cents IS NOT NULL "
    "AND principal_applied_cents >= 0 AND interest_applied_cents >= 0 AND fees_applied_cents >= 0 "
    "AND principal_applied_cents + interest_applied_cents + fees_applied_cents = amount_cents)"
)


def upgrade() -> None:
    op.add_column(
        "loan_events",
        sa.Column("allocation_order", sa.Integer(), server_default="0", nullable=False),
        schema=S,
    )
    op.add_column("loan_events", sa.Column("component", sa.String(8)), schema=S)
    op.add_column("loan_events", sa.Column("reason", sa.String(1000)), schema=S)
    for name in ("principal_applied_cents", "interest_applied_cents", "fees_applied_cents"):
        op.add_column("loan_events", sa.Column(name, sa.BigInteger()), schema=S)
    op.execute("""
        UPDATE iou_app.loan_events SET principal_applied_cents=amount_cents,
            interest_applied_cents=0, fees_applied_cents=0 WHERE action='repayment';
    """)
    op.execute("""
        WITH numbered AS (
            SELECT id, row_number() OVER (PARTITION BY loan_id ORDER BY recorded_at, id) AS n
            FROM iou_app.loan_events
        ) UPDATE iou_app.loan_events e SET allocation_order=numbered.n
          FROM numbered WHERE e.id=numbered.id
    """)
    op.drop_constraint("ck_event_terms", "loan_events", schema=S, type_="check")
    op.create_check_constraint("ck_event_terms", "loan_events", EVENT_TERMS, schema=S)
    op.create_check_constraint("ck_event_allocation", "loan_events", ALLOCATION, schema=S)
    op.create_check_constraint(
        "ck_allocation_order", "loan_events", "allocation_order >= 0", schema=S
    )
    op.create_index(
        "uq_active_allocation_order",
        "loan_events",
        ["loan_id", "allocation_order"],
        unique=True,
        schema=S,
        postgresql_where=sa.text("allocation_order > 0 AND reversed_at IS NULL"),
    )
    for name, type_, default in (
        ("interest_rate_bps", sa.Integer(), "0"),
        ("interest_period", sa.String(12), "weekly"),
        ("late_fee_cents", sa.BigInteger(), "0"),
        ("charge_cap_cents", sa.BigInteger(), "0"),
        ("grace_days", sa.Integer(), "0"),
        ("calculation_version", sa.Integer(), "0"),
    ):
        op.add_column(
            "loans", sa.Column(name, type_, server_default=default, nullable=False), schema=S
        )
    op.add_column("loans", sa.Column("fee_at", sa.DateTime(timezone=True)), schema=S)
    op.add_column("loans", sa.Column("settled_at", sa.DateTime(timezone=True)), schema=S)
    op.execute("UPDATE iou_app.loans SET fee_at=overdue_at")
    op.execute("""
        WITH balances AS (
            SELECT loan_id,
                sum(CASE WHEN action='repayment' THEN amount_cents ELSE 0 END) AS paid,
                max(CASE WHEN action='repayment' THEN effective_at END) AS last_payment,
                max(CASE WHEN action='return' THEN effective_at END) AS returned
            FROM iou_app.loan_events WHERE reversed_at IS NULL GROUP BY loan_id
        ) UPDATE iou_app.loans l SET settled_at=CASE
            WHEN l.kind='money' AND balances.paid >= l.principal_cents THEN balances.last_payment
            WHEN l.kind='item' THEN balances.returned END
          FROM balances WHERE l.id=balances.loan_id
    """)
    op.create_check_constraint(
        "ck_charge_terms",
        "loans",
        "interest_rate_bps BETWEEN 0 AND 10000 AND grace_days BETWEEN 0 AND 365 "
        "AND interest_period IN ('daily','weekly','biweekly','monthly','quarterly','yearly') "
        "AND late_fee_cents BETWEEN 0 AND 1000000000000 "
        "AND charge_cap_cents BETWEEN 0 AND 1000000000000 "
        "AND (kind = 'money' OR interest_rate_bps = 0)",
        schema=S,
    )
    op.create_check_constraint(
        "ck_calculation_version",
        "loans",
        "calculation_version = 1 OR (calculation_version = 0 AND interest_rate_bps = 0 "
        "AND late_fee_cents = 0 AND charge_cap_cents = 0 AND grace_days = 0)",
        schema=S,
    )
    op.create_check_constraint(
        "ck_settled_time", "loans", "settled_at IS NULL OR settled_at >= lent_at", schema=S
    )


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM iou_app.loans WHERE calculation_version != 0)
               OR EXISTS (SELECT 1 FROM iou_app.loan_events
                          WHERE action NOT IN ('repayment','return')
                             OR interest_applied_cents > 0 OR fees_applied_cents > 0)
            THEN RAISE EXCEPTION 'Cannot downgrade: preserve Level 3 terms and allocations';
            END IF;
        END $$
    """)
    for name in ("ck_settled_time", "ck_calculation_version", "ck_charge_terms"):
        op.drop_constraint(name, "loans", schema=S, type_="check")
    for name in (
        "settled_at",
        "fee_at",
        "calculation_version",
        "grace_days",
        "charge_cap_cents",
        "late_fee_cents",
        "interest_period",
        "interest_rate_bps",
    ):
        op.drop_column("loans", name, schema=S)
    op.drop_index("uq_active_allocation_order", table_name="loan_events", schema=S)
    for name in ("ck_allocation_order", "ck_event_allocation", "ck_event_terms"):
        op.drop_constraint(name, "loan_events", schema=S, type_="check")
    op.create_check_constraint(
        "ck_event_terms",
        "loan_events",
        "(action = 'repayment' AND loan_kind = 'money' AND amount_cents IS NOT NULL "
        "AND amount_cents BETWEEN 1 AND 1000000000000) "
        "OR (action = 'return' AND loan_kind = 'item' AND amount_cents IS NULL)",
        schema=S,
    )
    for name in (
        "fees_applied_cents",
        "interest_applied_cents",
        "principal_applied_cents",
        "reason",
        "component",
        "allocation_order",
    ):
        op.drop_column("loan_events", name, schema=S)
