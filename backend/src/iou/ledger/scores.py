"""Private fictional reliability, based on obligations rather than amounts or traits."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from iou.ledger import service
from iou.ledger.models import Loan
from iou.ledger.schemas import LoanRead

DISCLAIMER = "Fictional IOU score — for fun, not a real credit score."


class ScoreRead(BaseModel):
    version: str = "iou-reliability-v1"
    score: int | None
    sufficient_history: bool
    minimum_completed: int = 3
    completed_count: int
    on_time_completed: int
    late_completed: int
    currently_overdue: int
    excluded_voided: int
    base_points: int = 600
    on_time_points: int
    late_points: int
    overdue_points: int
    minimum_score: int = 300
    maximum_score: int = 850
    calculated_at: datetime
    disclaimer: str = DISCLAIMER


def score(loans: list[LoanRead], at: datetime) -> ScoreRead:
    on_time = late = overdue = voided = 0
    for loan in loans:
        if loan.status == "voided":
            voided += 1
            continue
        completed = loan.returned_at if loan.kind == "item" else loan.completed_at
        deadline = loan.fee_at or loan.overdue_at
        if completed is not None:
            if completed < deadline:
                on_time += 1
            else:
                late += 1
        elif at >= deadline:
            overdue += 1
    enough = on_time + late >= 3
    value = max(300, min(850, 600 + 25 * on_time - 40 * late - 20 * overdue)) if enough else None
    return ScoreRead(
        score=value,
        sufficient_history=enough,
        completed_count=on_time + late,
        on_time_completed=on_time,
        late_completed=late,
        currently_overdue=overdue,
        excluded_voided=voided,
        on_time_points=25 * on_time,
        late_points=-40 * late,
        overdue_points=-20 * overdue,
        calculated_at=at,
    )


def for_friend(session: Session, owner: UUID, friend_id: UUID) -> ScoreRead:
    service.friend_for_owner(session, owner, friend_id)
    at = service.now_utc()
    loans = [
        service.loan_read(row, at)
        for row in session.execute(service.loan_query(owner).where(Loan.friend_id == friend_id))
    ]
    return score(loans, at)
