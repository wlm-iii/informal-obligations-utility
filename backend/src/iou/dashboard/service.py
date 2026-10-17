"""Read-only projections; reuse the ledger calculator and fictional score rule."""

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from iou.dashboard import schemas as dto
from iou.ledger import scores
from iou.ledger import service as ledger
from iou.ledger.models import Friend, Loan
from iou.ledger.schemas import LoanRead
from iou.profiles import Profile


@dataclass
class Snapshot:
    context: dto.Context
    friends: dict[UUID, dto.FriendLabel]
    loans: list[LoanRead]
    records: list[Loan]


def load(session: Session, owner: UUID, friend_id: UUID | None, archived: dto.Archived) -> Snapshot:
    # All ledger writers lock this same owner row exclusively. Hold a shared lock
    # through serialization so parent/void/child reads cannot straddle a mutation.
    # No profile provisioning, persistent aggregates, provider calls, or GET writes.
    profile = session.scalar(select(Profile).where(Profile.id == owner).with_for_update(read=True))
    context = dto.Context(
        calculated_at=ledger.now_utc(),
        timezone=profile.timezone if profile else "UTC",
        friend_id=friend_id,
        archived=archived,
    )
    if friend_id is not None:
        ledger.friend_for_owner(session, owner, friend_id)
    if profile is None:
        return Snapshot(context, {}, [], [])
    conditions = [Friend.owner_id == owner]
    if friend_id is not None:
        conditions.append(Friend.id == friend_id)
    if archived != "include":
        conditions.append(
            Friend.archived_at.is_(None)
            if archived == "exclude"
            else Friend.archived_at.is_not(None)
        )
    friends = {
        friend.id: dto.FriendLabel(
            id=friend.id, display_name=friend.display_name, archived=friend.archived_at is not None
        )
        for friend in session.scalars(select(Friend).where(*conditions))
    }
    rows = session.execute(
        ledger.loan_query(owner).join(Friend, Friend.id == Loan.friend_id).where(*conditions)
    ).all()
    return Snapshot(
        context,
        friends,
        [ledger.loan_read(row, context.calculated_at) for row in rows],
        [row[0] for row in rows if not row.is_voided],
    )


def components(principal: int, interest: int, fees: int) -> dto.Components:
    return dto.Components(
        principal_cents=principal,
        interest_cents=interest,
        fees_cents=fees,
        total_cents=principal + interest + fees,
    )


def metrics(loans: list[LoanRead]) -> dto.Metrics:
    active = [loan for loan in loans if loan.status != "voided"]
    money = [loan for loan in active if loan.kind == "money"]
    items = [loan for loan in active if loan.kind == "item"]
    return dto.Metrics(
        loan_count=len(active),
        money_loan_count=len(money),
        item_loan_count=len(items),
        open_count=sum(loan.status == "open" for loan in active),
        completed_count=sum(loan.status == "completed" for loan in active),
        overdue_count=sum(loan.overdue for loan in active),
        items_outstanding=sum(loan.returned_at is None for loan in items),
        items_returned=sum(loan.returned_at is not None for loan in items),
        returned_items_unpaid_count=sum(
            loan.returned_at is not None and loan.fees_cents > 0 for loan in items
        ),
        principal_lent_cents=sum(loan.principal_cents for loan in money),
        interest_accrued_cents=sum(loan.interest_accrued_cents for loan in active),
        fees_assessed_cents=sum(loan.late_fee_assessed_cents for loan in active),
        outstanding=components(
            sum(loan.outstanding_cents for loan in money),
            sum(loan.interest_cents for loan in active),
            sum(loan.fees_cents for loan in active),
        ),
        cash_received=components(
            sum(loan.principal_repaid_cents for loan in active),
            sum(loan.interest_paid_cents for loan in active),
            sum(loan.fees_paid_cents for loan in active),
        ),
        waived=components(
            0,
            sum(loan.interest_waived_cents for loan in active),
            sum(loan.fees_waived_cents for loan in active),
        ),
    )


def summary(data: Snapshot) -> dto.Summary:
    return dto.Summary(
        **data.context.model_dump(),
        friend_count=len(data.friends),
        excluded_voided_count=sum(loan.status == "voided" for loan in data.loans),
        metrics=metrics(data.loans),
    )


def obligations(
    data: Snapshot, group: dto.ObligationGroup, days: int, limit: int, offset: int
) -> dto.Obligations:
    def matches(loan):
        if loan.status == "voided":
            return False
        if group == "overdue":
            return loan.overdue
        if group == "returned_unpaid":
            return loan.kind == "item" and loan.returned_at is not None and loan.fees_cents > 0
        today = data.context.calculated_at.astimezone(ZoneInfo(loan.timezone)).date()
        return (
            loan.borrowing_status == "outstanding"
            and not loan.overdue
            and 0 <= (loan.due_date - today).days <= days
        )

    loans = sorted(
        (loan for loan in data.loans if matches(loan)), key=lambda loan: (loan.overdue_at, loan.id)
    )
    return dto.Obligations(
        **data.context.model_dump(),
        group=group,
        upcoming_days=days,
        items=[
            dto.Obligation(friend=data.friends[loan.friend_id], loan=loan)
            for loan in loans[offset : offset + limit]
        ],
        total=len(loans),
        limit=limit,
        offset=offset,
    )


def rankings(
    data: Snapshot, sort_by: dto.RankingSort, direction: dto.Direction, limit: int, offset: int
) -> dto.Rankings:
    grouped = defaultdict(list)
    for loan in data.loans:
        grouped[loan.friend_id].append(loan)
    entries = [
        dto.Ranking(
            rank=None,
            friend=friend,
            reliability=scores.score(grouped[friend.id], data.context.calculated_at),
            metrics=metrics(grouped[friend.id]),
        )
        for friend in data.friends.values()
    ]

    def sort_key(entry):
        value = (
            entry.reliability.score if sort_by == "score" else entry.metrics.outstanding.total_cents
        )
        return (value is None, (value or 0) * (-1 if direction == "desc" else 1), entry.friend.id)

    entries.sort(key=sort_key)
    for index, entry in enumerate(entries, 1):
        if sort_by != "score" or entry.reliability.score is not None:
            entry.rank = index
    return dto.Rankings(
        **data.context.model_dump(),
        sort_by=sort_by,
        direction=direction,
        items=entries[offset : offset + limit],
        total=len(entries),
        limit=limit,
        offset=offset,
    )


def period(day: date, bucket: dto.Bucket) -> tuple[date, date]:
    if bucket == "day":
        return day, day
    if bucket == "week":
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=6)
    return day.replace(day=1), day.replace(day=monthrange(day.year, day.month)[1])


def trends(data: Snapshot, start: date | None, end: date | None, bucket: dto.Bucket) -> dto.Trends:
    zone = ZoneInfo(data.context.timezone)
    today = data.context.calculated_at.astimezone(zone).date()
    end = end or today
    # Bounds also prevent date arithmetic overflow at datetime's extreme years.
    if end > today or end < date(2, 1, 1):
        raise HTTPException(422, "end_date must be a supported date no later than today.")
    start = start or end - timedelta(days=29)
    if start < date(2, 1, 1) or start > end or (end - start).days >= 366:
        raise HTTPException(422, "Use an inclusive date range of 1 to 366 days.")
    periods = {}
    day = start
    while day <= end:
        first, last = period(day, bucket)
        periods.setdefault(first, dto.TrendPeriod(period_start=first, period_end=last))
        day += timedelta(days=1)
    total = dto.Flows()

    def targets(at):
        if ledger.utc(at) > data.context.calculated_at:
            return ()
        local = ledger.utc(at).astimezone(zone).date()
        return (total, periods[period(local, bucket)[0]]) if start <= local <= end else ()

    def apply(target, event):
        if event.action == "return":
            target.items_returned += 1
            return
        values = components(
            event.principal_applied_cents, event.interest_applied_cents, event.fees_applied_cents
        )
        field = "waived" if event.action == "waiver" else "cash_received"
        previous = getattr(target, field)
        setattr(
            target,
            field,
            components(
                previous.principal_cents + values.principal_cents,
                previous.interest_cents + values.interest_cents,
                previous.fees_cents + values.fees_cents,
            ),
        )

    for loan in data.records:
        for target in targets(loan.lent_at):
            if loan.kind == "money":
                target.principal_lent_cents += loan.principal_cents
            else:
                target.items_lent += 1
        for event in loan.events:
            if event.reversed_at is None:
                for target in targets(event.effective_at):
                    apply(target, event)
    return dto.Trends(
        **data.context.model_dump(),
        start_date=start,
        end_date=end,
        bucket=bucket,
        totals=total,
        items=list(periods.values()),
    )
