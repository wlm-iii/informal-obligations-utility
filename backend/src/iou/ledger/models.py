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
from sqlalchemy.orm import Mapped, mapped_column

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
        CheckConstraint(
            f"(kind = 'money' AND principal_cents IS NOT NULL AND currency IS NOT NULL "
            f"AND principal_cents BETWEEN 1 AND {MAX_CENTS} AND currency = 'USD') "
            "OR (kind = 'item' AND principal_cents IS NULL AND currency IS NULL)",
            name="ck_loan_terms",
        ),
        CheckConstraint("interest_percent BETWEEN 0 AND 1000", name="ck_loan_interest_percent"),
        CheckConstraint(
            "(repayment_type IS NULL AND repayment_other IS NULL) OR "
            "(repayment_type IN ('item', 'money') AND repayment_other IS NULL) OR "
            "(repayment_type = 'other' AND repayment_other IS NOT NULL "
            "AND length(trim(repayment_other)) BETWEEN 1 AND 500)",
            name="ck_loan_repayment_preference",
        ),
        CheckConstraint("kind IN ('money', 'item')", name="ck_loan_kind"),
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
    repayment_type: Mapped[str | None] = mapped_column(String(10))
    repayment_other: Mapped[str | None] = mapped_column(String(500))
    interest_percent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    principal_cents: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str | None] = mapped_column(String(3))
    lent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[date]
    timezone: Mapped[str] = mapped_column(String(100))
    overdue_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoanEvent(Base):
    __tablename__ = "loan_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["loan_id", "owner_id", "loan_kind"],
            [f"{SCHEMA}.loans.id", f"{SCHEMA}.loans.owner_id", f"{SCHEMA}.loans.kind"],
            name="fk_event_loan_owner_kind",
        ),
        CheckConstraint(
            f"(action = 'repayment' AND loan_kind = 'money' AND amount_cents IS NOT NULL "
            f"AND amount_cents BETWEEN 1 AND {MAX_CENTS}) "
            "OR (action = 'return' AND loan_kind = 'item' AND amount_cents IS NULL)",
            name="ck_event_terms",
        ),
        Index("ix_events_owner_loan_time", "owner_id", "loan_id", "effective_at", "id"),
        Index(
            "uq_one_item_return",
            "loan_id",
            unique=True,
            postgresql_where=text("action = 'return'"),
            sqlite_where=text("action = 'return'"),
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    loan_id: Mapped[UUID]
    loan_kind: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(10))
    amount_cents: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(String(2000))
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
