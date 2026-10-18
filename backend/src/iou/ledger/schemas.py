"""HTTP contracts: integer USD cents, aware timestamps, bounded text, no owner IDs."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from iou.ledger.models import MAX_CENTS

Cents = Annotated[int, Field(strict=True, ge=1, le=MAX_CENTS)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Notes = Annotated[str, Field(max_length=2000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*")
    @classmethod
    def no_nul_text(cls, value):
        if isinstance(value, str) and "\u0000" in value:
            raise ValueError("NUL characters are not supported in text fields.")
        return value

    @field_validator("lent_at", "effective_at", mode="before", check_fields=False)
    @classmethod
    def timestamp_not_epoch(cls, value):
        if value is not None and not isinstance(value, (str, datetime)):
            raise ValueError("Use an ISO-8601 timestamp with an explicit timezone offset.")
        if isinstance(value, str) and value.lstrip("+-").replace(".", "", 1).isdigit():
            raise ValueError("Epoch timestamps are not supported.")
        return value

    @field_validator("lent_at", "effective_at", check_fields=False)
    @classmethod
    def normalize_timestamp(cls, value):
        if value is None:
            return None
        try:
            return value.astimezone(UTC)
        except (OverflowError, ValueError):
            raise ValueError("Timestamp is outside the supported range.") from None


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="after")
    @classmethod
    def utc_timestamps(cls, value):
        if isinstance(value, datetime):
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return value


class FriendCreate(Input):
    display_name: Name
    email: Annotated[EmailStr, Field(max_length=320)] | None = None
    notes: Notes | None = None


class FriendUpdate(Input):
    display_name: Name | None = None
    email: Annotated[EmailStr, Field(max_length=320)] | None = None
    notes: Notes | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def name_not_null(cls, value):
        if value is None:
            raise ValueError("Display name cannot be null.")
        return value


class FriendRead(ReadModel):
    id: UUID
    display_name: str
    email: str | None
    notes: str | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LoanInput(Input):
    friend_id: UUID
    description: Annotated[str, Field(min_length=1, max_length=500)]
    notes: Notes | None = None
    lent_at: AwareDatetime | None = None
    due_date: date
    late_fee_cents: Annotated[int, Field(strict=True, ge=0, le=MAX_CENTS)] = 0
    grace_days: Annotated[int, Field(strict=True, ge=0, le=365)] = 0
    charge_cap_cents: Annotated[int, Field(strict=True, ge=0, le=MAX_CENTS)] | None = None

    repayment_type: Literal["item", "money", "other"] | None = None
    repayment_other: Annotated[str, Field(min_length=1, max_length=500)] | None = None

    @model_validator(mode="after")
    def repayment_details(self):
        if self.repayment_type == "other" and not self.repayment_other:
            raise ValueError("Describe the other repayment preference.")
        if self.repayment_type != "other" and self.repayment_other is not None:
            raise ValueError("Details require the other repayment preference.")
        return self


class MoneyLoanCreate(LoanInput):
    kind: Literal["money"]
    principal_cents: Cents
    currency: Literal["USD"] = "USD"
    interest_rate_bps: Annotated[int, Field(strict=True, ge=0, le=10000)] = 0
    interest_period: Literal["daily", "weekly", "biweekly", "monthly", "quarterly", "yearly"] = (
        "weekly"
    )


class ItemLoanCreate(LoanInput):
    kind: Literal["item"]


LoanCreate = Annotated[MoneyLoanCreate | ItemLoanCreate, Field(discriminator="kind")]


class SettlementInput(Input):
    effective_at: AwareDatetime | None = None
    note: Notes | None = None


class RepaymentCreate(SettlementInput):
    amount_cents: Cents


class WaiverCreate(SettlementInput):
    amount_cents: Cents
    component: Literal["interest", "fees"]
    reason: Annotated[str, Field(min_length=1, max_length=1000)]


class LoanRead(ReadModel):
    repayment_type: Literal["item", "money", "other"] | None = None
    repayment_other: str | None = None
    id: UUID
    friend_id: UUID
    kind: Literal["money", "item"]
    description: str
    notes: str | None
    lent_at: datetime
    due_date: date
    timezone: str
    overdue_at: datetime
    created_at: datetime
    principal_cents: int | None
    currency: Literal["USD"] | None
    repaid_cents: int | None
    outstanding_cents: int | None
    interest_cents: int = 0
    fees_cents: int = 0
    interest_rate_bps: int = 0
    interest_period: str = "weekly"
    interest_period_days: int = 7
    late_fee_cents: int = 0
    grace_days: int = 0
    charge_cap_cents: int = 0
    calculation_version: int = 0
    calculated_at: datetime | None = None
    fee_at: datetime | None = None
    late_fee_assessed_at: datetime | None = None
    interest_accrued_cents: int = 0
    late_fee_assessed_cents: int = 0
    principal_repaid_cents: int = 0
    interest_paid_cents: int = 0
    fees_paid_cents: int = 0
    interest_waived_cents: int = 0
    fees_waived_cents: int = 0
    total_outstanding_cents: int = 0
    charges_currency: Literal["USD"] = "USD"
    borrowing_status: Literal["outstanding", "repaid", "returned", "voided"] = "outstanding"
    settlement_status: Literal["unpaid", "settled", "voided"] = "unpaid"
    returned_at: datetime | None
    completed_at: datetime | None
    status: Literal["open", "completed", "voided"]
    overdue: bool
    voided_at: datetime | None = None
    void_reason: str | None = None


class EventRead(ReadModel):
    id: UUID
    loan_id: UUID
    action: Literal["repayment", "return", "fee_payment", "waiver"]
    amount_cents: int | None
    note: str | None
    effective_at: datetime
    recorded_at: datetime
    reversed_at: datetime | None = None
    replaces_event_id: UUID | None = None
    allocation_order: int = 0
    component: Literal["interest", "fees"] | None = None
    reason: str | None = None
    principal_applied_cents: int | None = None
    interest_applied_cents: int | None = None
    fees_applied_cents: int | None = None


class SettlementRead(ReadModel):
    event: EventRead
    loan: LoanRead


class HistoryEntry(ReadModel):
    id: UUID
    action: Literal[
        "lent",
        "repayment",
        "return",
        "fee_payment",
        "waiver",
        "reversal",
        "void",
        "evidence_added",
        "evidence_removed",
    ]
    amount_cents: int | None
    note: str | None
    effective_at: datetime
    recorded_at: datetime
    loan: LoanRead
    actor: Literal["owner", "system"] = "owner"
    reason: str | None = None
    event_id: UUID | None = None
    replacement_event_id: UUID | None = None
    evidence_id: UUID | None = None
    reversed_at: datetime | None = None
    replaces_event_id: UUID | None = None
    allocation_order: int | None = None
    component: Literal["interest", "fees"] | None = None
    principal_applied_cents: int | None = None
    interest_applied_cents: int | None = None
    fees_applied_cents: int | None = None


class ReasonInput(Input):
    reason: Annotated[str, Field(min_length=1, max_length=1000)]


class ReplacementRepayment(RepaymentCreate):
    action: Literal["repayment"]


class ReplacementReturn(SettlementInput):
    action: Literal["return"]


class ReplacementFeePayment(RepaymentCreate):
    action: Literal["fee_payment"]


class ReplacementWaiver(WaiverCreate):
    action: Literal["waiver"]


class CorrectionInput(ReasonInput):
    replacement: Annotated[
        ReplacementRepayment | ReplacementReturn | ReplacementFeePayment | ReplacementWaiver,
        Field(discriminator="action"),
    ]


class AuditRead(ReadModel):
    id: UUID
    loan_id: UUID
    action: Literal["reversal", "void", "evidence_added", "evidence_removed"]
    actor: Literal["owner", "system"]
    reason: str | None
    event_id: UUID | None
    replacement_event_id: UUID | None
    evidence_id: UUID | None
    effective_at: datetime
    recorded_at: datetime


class CorrectionRead(ReadModel):
    reversal: AuditRead
    original_event: EventRead
    replacement: EventRead | None
    loan: LoanRead


class VoidRead(ReadModel):
    audit: AuditRead
    loan: LoanRead


class Page[T](BaseModel):
    items: list[T]
    limit: int
    offset: int
    has_more: bool
    next_cursor: str | None = None
