"""Private reminder consent, delivery state, and cross-contact recipient suppression."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from iou.database import Base
from iou.ledger.models import SCHEMA


class Recipient(Base):
    __tablename__ = "reminder_recipients"
    __table_args__ = ({"schema": SCHEMA},)
    # Stable SHA-256 of normalized address. Not anonymous; never exposed publicly.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # A durable projection, not a cascading FK: suppression outlives sender records.
    in_flight: Mapped[UUID | None]


class Permission(Base):
    __tablename__ = "reminder_permissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["friend_id", "owner_id"],
            [f"{SCHEMA}.friends.id", f"{SCHEMA}.friends.owner_id"],
            name="fk_reminder_permission_friend",
        ),
        Index("ix_reminder_permissions_owner", "owner_id"),
        {"schema": SCHEMA},
    )
    friend_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    recipient_email: Mapped[str] = mapped_column(String(320))
    contact_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["friend_id", "owner_id"],
            [f"{SCHEMA}.friends.id", f"{SCHEMA}.friends.owner_id"],
            name="fk_reminder_friend",
        ),
        ForeignKeyConstraint(
            ["recipient_hash"], [f"{SCHEMA}.reminder_recipients.id"], name="fk_reminder_recipient"
        ),
        UniqueConstraint("owner_id", "send_key", name="uq_reminder_send_key"),
        CheckConstraint("tone IN ('friendly','playful','direct')", name="ck_reminder_tone"),
        CheckConstraint(
            "status IN ('preview','reserved','sending','sent','failed','uncertain','cancelled')",
            name="ck_reminder_status",
        ),
        CheckConstraint("expires_at > created_at", name="ck_reminder_expiry"),
        CheckConstraint(
            "(status = 'preview' AND send_key IS NULL) OR "
            "(status != 'preview' AND send_key IS NOT NULL)",
            name="ck_reminder_send_key",
        ),
        Index("ix_reminders_owner_created", "owner_id", "created_at", "id"),
        {"schema": SCHEMA},
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    friend_id: Mapped[UUID]
    recipient_hash: Mapped[str] = mapped_column(String(64))
    recipient_email: Mapped[str] = mapped_column(String(320))
    tone: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(4000))
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="preview")
    send_key: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    error_code: Mapped[str | None] = mapped_column(String(40))
