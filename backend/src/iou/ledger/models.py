"""Ledger records. All writes go through owner-serialized service transactions."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from iou.database import Base

SCHEMA = "iou_app"
MAX_CENTS = 1_000_000_000_000


class Friend(Base):
    __tablename__ = "friends"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_friends_id_owner"),
        CheckConstraint("length(trim(display_name)) BETWEEN 1 AND 100", name="ck_friend_name"),
        Index("ix_friends_owner_created", "owner_id", "created_at", "id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey(f"{SCHEMA}.profiles.id"))
    display_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(320))
    notes: Mapped[str | None] = mapped_column(String(2000))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (
        ForeignKeyConstraint(
            ["friend_id", "owner_id"],
            [f"{SCHEMA}.friends.id", f"{SCHEMA}.friends.owner_id"],
            name="fk_loan_friend_owner",
        ),
        UniqueConstraint("id", "owner_id", "kind", name="uq_loans_id_owner_kind"),
        UniqueConstraint("id", "owner_id", name="uq_loans_id_owner"),
        CheckConstraint(
            f"(kind = 'money' AND principal_cents IS NOT NULL AND currency IS NOT NULL "
            f"AND principal_cents BETWEEN 1 AND {MAX_CENTS} AND currency = 'USD') "
            "OR (kind = 'item' AND principal_cents IS NULL AND currency IS NULL)",
            name="ck_loan_terms",
        ),
        CheckConstraint("kind IN ('money', 'item')", name="ck_loan_kind"),
        CheckConstraint(
            "interest_rate_bps BETWEEN 0 AND 10000 AND grace_days BETWEEN 0 AND 365 "
            "AND interest_period IN ('daily','weekly','biweekly','monthly','quarterly','yearly') "
            f"AND late_fee_cents BETWEEN 0 AND {MAX_CENTS} "
            f"AND charge_cap_cents BETWEEN 0 AND {MAX_CENTS} "
            "AND (kind = 'money' OR interest_rate_bps = 0)",
            name="ck_charge_terms",
        ),
        CheckConstraint(
            "calculation_version = 1 OR (calculation_version = 0 AND interest_rate_bps = 0 "
            "AND late_fee_cents = 0 AND charge_cap_cents = 0 AND grace_days = 0)",
            name="ck_calculation_version",
        ),
        CheckConstraint("settled_at IS NULL OR settled_at >= lent_at", name="ck_settled_time"),
        CheckConstraint("length(trim(description)) BETWEEN 1 AND 500", name="ck_loan_description"),
        CheckConstraint("overdue_at > lent_at", name="ck_loan_due_boundary"),
        Index("ix_loans_owner_friend_created", "owner_id", "friend_id", "created_at", "id"),
        Index("ix_loans_owner_due", "owner_id", "overdue_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey(f"{SCHEMA}.profiles.id"))
    friend_id: Mapped[UUID]
    kind: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(String(2000))
    principal_cents: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str | None] = mapped_column(String(3))
    lent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[date]
    timezone: Mapped[str] = mapped_column(String(100))
    overdue_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    interest_rate_bps: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    interest_period: Mapped[str] = mapped_column(
        String(12), default="weekly", server_default="weekly"
    )
    late_fee_cents: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    charge_cap_cents: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    grace_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    calculation_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    fee_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    events: Mapped[list["LoanEvent"]] = relationship(
        "LoanEvent",
        primaryjoin="Loan.id == foreign(LoanEvent.loan_id)",
        viewonly=True,
        lazy="raise",
    )


class LoanEvent(Base):
    __tablename__ = "loan_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["loan_id", "owner_id", "loan_kind"],
            [f"{SCHEMA}.loans.id", f"{SCHEMA}.loans.owner_id", f"{SCHEMA}.loans.kind"],
            name="fk_event_loan_owner_kind",
        ),
        UniqueConstraint("id", "owner_id", "loan_id", name="uq_events_id_owner_loan"),
        UniqueConstraint("replaces_event_id", name="uq_event_replacement"),
        ForeignKeyConstraint(
            ["replaces_event_id", "owner_id", "loan_id"],
            [
                f"{SCHEMA}.loan_events.id",
                f"{SCHEMA}.loan_events.owner_id",
                f"{SCHEMA}.loan_events.loan_id",
            ],
            name="fk_replacement_original",
        ),
        CheckConstraint(
            "((action = 'repayment' AND loan_kind = 'money') OR "
            "(action = 'fee_payment' AND loan_kind = 'item')) "
            f"AND amount_cents BETWEEN 1 AND {MAX_CENTS} AND amount_cents IS NOT NULL "
            "AND component IS NULL AND reason IS NULL OR "
            "(action = 'return' AND loan_kind = 'item' AND amount_cents IS NULL "
            "AND component IS NULL AND reason IS NULL) OR "
            "(action = 'waiver' AND amount_cents IS NOT NULL "
            f"AND amount_cents BETWEEN 1 AND {MAX_CENTS} "
            "AND component IN ('interest','fees') AND component IS NOT NULL AND reason IS NOT NULL "
            "AND length(trim(reason)) BETWEEN 1 AND 1000)",
            name="ck_event_terms",
        ),
        CheckConstraint(
            "(action = 'return' AND principal_applied_cents IS NULL "
            "AND interest_applied_cents IS NULL AND fees_applied_cents IS NULL) OR "
            "(action != 'return' AND principal_applied_cents IS NOT NULL "
            "AND interest_applied_cents IS NOT NULL AND fees_applied_cents IS NOT NULL "
            "AND principal_applied_cents >= 0 AND interest_applied_cents >= 0 "
            "AND fees_applied_cents >= 0 AND principal_applied_cents "
            "+ interest_applied_cents + fees_applied_cents = amount_cents)",
            name="ck_event_allocation",
        ),
        CheckConstraint("allocation_order >= 0", name="ck_allocation_order"),
        Index(
            "uq_active_allocation_order",
            "loan_id",
            "allocation_order",
            unique=True,
            postgresql_where=text("allocation_order > 0 AND reversed_at IS NULL"),
            sqlite_where=text("allocation_order > 0 AND reversed_at IS NULL"),
        ),
        Index("ix_events_owner_loan_time", "owner_id", "loan_id", "effective_at", "id"),
        Index(
            "uq_one_item_return",
            "loan_id",
            unique=True,
            postgresql_where=text("action = 'return' AND reversed_at IS NULL"),
            sqlite_where=text("action = 'return' AND reversed_at IS NULL"),
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    loan_id: Mapped[UUID]
    loan_kind: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(10))
    # Projection only: the financial fields stay intact; an immutable audit records the reversal.
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaces_event_id: Mapped[UUID | None]
    amount_cents: Mapped[int | None] = mapped_column(BigInteger)
    allocation_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    component: Mapped[str | None] = mapped_column(String(8))
    reason: Mapped[str | None] = mapped_column(String(1000))
    principal_applied_cents: Mapped[int | None] = mapped_column(BigInteger)
    interest_applied_cents: Mapped[int | None] = mapped_column(BigInteger)
    fees_applied_cents: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(String(2000))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Audit(Base):
    """Append-only application history; not a tamper-proof accounting journal."""

    __tablename__ = "ledger_audit"
    __table_args__ = (
        ForeignKeyConstraint(
            ["loan_id", "owner_id"],
            [f"{SCHEMA}.loans.id", f"{SCHEMA}.loans.owner_id"],
            name="fk_audit_loan_owner",
        ),
        ForeignKeyConstraint(
            ["event_id", "owner_id", "loan_id"],
            [
                f"{SCHEMA}.loan_events.id",
                f"{SCHEMA}.loan_events.owner_id",
                f"{SCHEMA}.loan_events.loan_id",
            ],
            name="fk_audit_event_owner_loan",
        ),
        ForeignKeyConstraint(
            ["replacement_event_id", "owner_id", "loan_id"],
            [
                f"{SCHEMA}.loan_events.id",
                f"{SCHEMA}.loan_events.owner_id",
                f"{SCHEMA}.loan_events.loan_id",
            ],
            name="fk_audit_replacement_owner_loan",
        ),
        ForeignKeyConstraint(
            ["evidence_id", "owner_id", "loan_id"],
            [f"{SCHEMA}.evidence.id", f"{SCHEMA}.evidence.owner_id", f"{SCHEMA}.evidence.loan_id"],
            name="fk_audit_evidence_owner_loan",
        ),
        CheckConstraint("actor IN ('owner', 'system')", name="ck_audit_actor"),
        CheckConstraint(
            "(action = 'reversal' AND event_id IS NOT NULL AND evidence_id IS NULL "
            "AND reason IS NOT NULL AND length(trim(reason)) > 0) OR "
            "(action = 'void' AND event_id IS NULL AND replacement_event_id IS NULL "
            "AND evidence_id IS NULL AND reason IS NOT NULL AND length(trim(reason)) > 0) OR "
            "(action IN ('evidence_added', 'evidence_removed') AND evidence_id IS NOT NULL "
            "AND replacement_event_id IS NULL AND (action = 'evidence_added' OR "
            "(reason IS NOT NULL AND length(trim(reason)) > 0)))",
            name="ck_audit_action",
        ),
        Index(
            "uq_event_reversal",
            "event_id",
            unique=True,
            postgresql_where=text("action = 'reversal'"),
            sqlite_where=text("action = 'reversal'"),
        ),
        Index(
            "uq_loan_void",
            "loan_id",
            unique=True,
            postgresql_where=text("action = 'void'"),
            sqlite_where=text("action = 'void'"),
        ),
        Index(
            "uq_evidence_audit_action",
            "evidence_id",
            "action",
            unique=True,
            postgresql_where=text("action IN ('evidence_added', 'evidence_removed')"),
            sqlite_where=text("action IN ('evidence_added', 'evidence_removed')"),
        ),
        Index("ix_audit_owner_loan_time", "owner_id", "loan_id", "effective_at", "id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    loan_id: Mapped[UUID]
    action: Mapped[str] = mapped_column(String(24))
    actor: Mapped[str] = mapped_column(String(10), default="owner", server_default="owner")
    reason: Mapped[str | None] = mapped_column(String(1000))
    event_id: Mapped[UUID | None]
    replacement_event_id: Mapped[UUID | None]
    evidence_id: Mapped[UUID | None]
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MutationReceipt(Base):
    __tablename__ = "mutation_receipts"
    __table_args__ = ({"schema": SCHEMA},)

    owner_id: Mapped[UUID] = mapped_column(ForeignKey(f"{SCHEMA}.profiles.id"), primary_key=True)
    key: Mapped[UUID] = mapped_column(primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
