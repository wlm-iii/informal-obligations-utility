from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from iou.database import Base
from iou.ledger.models import SCHEMA

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["loan_id", "owner_id"],
            [f"{SCHEMA}.loans.id", f"{SCHEMA}.loans.owner_id"],
            name="fk_evidence_loan_owner",
        ),
        ForeignKeyConstraint(
            ["event_id", "owner_id", "loan_id"],
            [
                f"{SCHEMA}.loan_events.id",
                f"{SCHEMA}.loan_events.owner_id",
                f"{SCHEMA}.loan_events.loan_id",
            ],
            name="fk_evidence_event_owner_loan",
        ),
        UniqueConstraint("id", "owner_id", "loan_id", name="uq_evidence_id_owner_loan"),
        UniqueConstraint("object_path", name="uq_evidence_object_path"),
        CheckConstraint(
            "state IN ('pending', 'uploading', 'ready', 'removed')", name="ck_evidence_state"
        ),
        CheckConstraint("content_type IN ('image/jpeg', 'image/png')", name="ck_evidence_type"),
        CheckConstraint(
            "state IN ('pending', 'removed') OR (object_path IS NOT NULL "
            "AND original_sha256 IS NOT NULL AND sha256 IS NOT NULL AND size_bytes IS NOT NULL "
            "AND original_size_bytes IS NOT NULL AND width IS NOT NULL AND height IS NOT NULL)",
            name="ck_evidence_upload_metadata",
        ),
        CheckConstraint("state != 'ready' OR uploaded_at IS NOT NULL", name="ck_evidence_ready"),
        CheckConstraint("state != 'removed' OR removed_at IS NOT NULL", name="ck_evidence_removed"),
        CheckConstraint(
            f"size_bytes IS NULL OR size_bytes BETWEEN 1 AND {MAX_BYTES}", name="ck_evidence_size"
        ),
        CheckConstraint(
            f"original_size_bytes IS NULL OR original_size_bytes BETWEEN 1 AND {MAX_BYTES}",
            name="ck_evidence_original_size",
        ),
        CheckConstraint(
            f"width IS NULL OR (width BETWEEN 1 AND 8000 AND height BETWEEN 1 AND 8000 "
            f"AND width * height <= {MAX_PIXELS})",
            name="ck_evidence_dimensions",
        ),
        Index("ix_evidence_owner_loan_created", "owner_id", "loan_id", "created_at", "id"),
        Index("ix_evidence_cleanup", "state", "expires_at", "cleanup_attempted_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    loan_id: Mapped[UUID]
    event_id: Mapped[UUID | None]
    state: Mapped[str] = mapped_column(String(12), default="pending", server_default="pending")
    # Persist the provider namespace: changing EVIDENCE_BUCKET must not orphan old objects.
    bucket: Mapped[str] = mapped_column(String(63))
    storage_origin: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(String(2000))
    content_type: Mapped[str] = mapped_column(String(20))
    object_path: Mapped[str | None] = mapped_column(String(300))
    original_sha256: Mapped[str | None] = mapped_column(String(64))
    sha256: Mapped[str | None] = mapped_column(String(64))
    original_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleanup_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleaned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
