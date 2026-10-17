"""HTTP contracts: integer USD cents, aware timestamps, bounded text, no owner IDs."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, field_validator

from iou.ledger.models import MAX_CENTS

Cents = Annotated[int, Field(strict=True, ge=1, le=MAX_CENTS)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Notes = Annotated[str, Field(max_length=2000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

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


class MoneyLoanCreate(LoanInput):
    kind: Literal["money"]
    principal_cents: Cents
    currency: Literal["USD"] = "USD"


class ItemLoanCreate(LoanInput):
    kind: Literal["item"]


LoanCreate = Annotated[MoneyLoanCreate | ItemLoanCreate, Field(discriminator="kind")]


class SettlementInput(Input):
    effective_at: AwareDatetime | None = None
    note: Notes | None = None


class RepaymentCreate(SettlementInput):
    amount_cents: Cents


class LoanRead(ReadModel):
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
    interest_cents: Literal[0] = 0
    fees_cents: Literal[0] = 0
    returned_at: datetime | None
    completed_at: datetime | None
    status: Literal["open", "completed"]
    overdue: bool


class EventRead(ReadModel):
    id: UUID
    loan_id: UUID
    action: Literal["repayment", "return"]
    amount_cents: int | None
    note: str | None
    effective_at: datetime
    recorded_at: datetime


class SettlementRead(ReadModel):
    event: EventRead
    loan: LoanRead


class HistoryEntry(ReadModel):
    id: UUID
    action: Literal["lent", "repayment", "return"]
    amount_cents: int | None
    note: str | None
    effective_at: datetime
    recorded_at: datetime
    loan: LoanRead


class Page[T](BaseModel):
    items: list[T]
    limit: int
    offset: int
    has_more: bool
