"""Dashboard metrics v1: USD cash components never value borrowed items."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from iou.ledger.schemas import LoanRead
from iou.ledger.scores import ScoreRead

Archived = Literal["include", "exclude", "only"]
Bucket = Literal["day", "week", "month"]
ObligationGroup = Literal["overdue", "upcoming", "returned_unpaid"]
RankingSort = Literal["score", "outstanding"]
Direction = Literal["asc", "desc"]


class ScopeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    friend_id: UUID | None = None
    archived: Archived = "include"


class ObligationsQuery(ScopeQuery):
    group: ObligationGroup = "overdue"
    upcoming_days: int = Field(default=7, ge=0, le=90)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=100_000)


class RankingsQuery(ScopeQuery):
    sort_by: RankingSort = "score"
    direction: Direction = "desc"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=100_000)


class TrendsQuery(ScopeQuery):
    start_date: date | None = None
    end_date: date | None = None
    bucket: Bucket = "day"

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def iso_date(cls, value):
        if value is not None and (
            not isinstance(value, str)
            or len(value) != 10
            or date.fromisoformat(value).isoformat() != value
        ):
            raise ValueError("Use an ISO calendar date: YYYY-MM-DD.")
        return value


class Components(BaseModel):
    principal_cents: int = 0
    interest_cents: int = 0
    fees_cents: int = 0
    total_cents: int = 0


class Metrics(BaseModel):
    loan_count: int = 0
    money_loan_count: int = 0
    item_loan_count: int = 0
    open_count: int = 0
    completed_count: int = 0
    overdue_count: int = 0
    items_outstanding: int = 0
    items_returned: int = 0
    returned_items_unpaid_count: int = 0
    principal_lent_cents: int = 0
    interest_accrued_cents: int = 0
    fees_assessed_cents: int = 0
    outstanding: Components = Field(default_factory=Components)
    cash_received: Components = Field(default_factory=Components)
    waived: Components = Field(default_factory=Components)


class Context(BaseModel):
    metrics_version: str = "iou-dashboard-v1"
    calculated_at: datetime
    timezone: str
    currency: Literal["USD"] = "USD"
    friend_id: UUID | None
    archived: Archived


class Summary(Context):
    friend_count: int
    excluded_voided_count: int
    metrics: Metrics


class FriendLabel(BaseModel):
    id: UUID
    display_name: str
    archived: bool


class Obligation(BaseModel):
    friend: FriendLabel
    loan: LoanRead


class Obligations(Context):
    group: ObligationGroup
    upcoming_days: int
    items: list[Obligation]
    total: int
    limit: int
    offset: int


class Ranking(BaseModel):
    rank: int | None
    friend: FriendLabel
    reliability: ScoreRead
    metrics: Metrics


class Rankings(Context):
    sort_by: RankingSort
    direction: Direction
    items: list[Ranking]
    total: int
    limit: int
    offset: int


class Flows(BaseModel):
    principal_lent_cents: int = 0
    items_lent: int = 0
    items_returned: int = 0
    cash_received: Components = Field(default_factory=Components)
    waived: Components = Field(default_factory=Components)


class TrendPeriod(Flows):
    period_start: date
    period_end: date


class Trends(Context):
    start_date: date
    end_date: date
    bucket: Bucket
    totals: Flows
    items: list[TrendPeriod]
