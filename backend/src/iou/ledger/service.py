"""Ledger operations, owner-scoped queries, and atomic/replay-safe mutation receipts."""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.orm import Session

from iou.auth import Identity
from iou.ledger.models import Audit, Friend, Loan, LoanEvent, MutationReceipt
from iou.ledger.schemas import (
    EventRead,
    FriendCreate,
    FriendRead,
    HistoryEntry,
    ItemLoanCreate,
    LoanRead,
    MoneyLoanCreate,
    Page,
    RepaymentCreate,
    SettlementInput,
    SettlementRead,
)
from iou.profiles import Profile, get_or_create_profile


def now_utc() -> datetime:
    return datetime.now(UTC)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def friend_for_owner(session: Session, owner: UUID, friend_id: UUID) -> Friend:
    friend = session.scalar(select(Friend).where(Friend.owner_id == owner, Friend.id == friend_id))
    if friend is None:
        raise HTTPException(404, "Friend not found.")
    return friend


def loan_query(owner: UUID) -> Select:
    totals = (
        select(
            LoanEvent.loan_id,
            func.coalesce(func.sum(LoanEvent.amount_cents), 0).label("paid_cents"),
            func.max(case((LoanEvent.action == "repayment", LoanEvent.effective_at))).label(
                "last_payment"
            ),
            func.max(case((LoanEvent.action == "return", LoanEvent.effective_at))).label(
                "returned_at"
            ),
        )
        .where(LoanEvent.owner_id == owner, LoanEvent.reversed_at.is_(None))
        .group_by(LoanEvent.loan_id)
        .subquery()
    )
    paid = func.coalesce(totals.c.paid_cents, 0)
    complete = and_(
        Audit.id.is_(None),
        or_(
            and_(Loan.kind == "money", paid >= Loan.principal_cents),
            and_(Loan.kind == "item", totals.c.returned_at.is_not(None)),
        ),
    )
    return (
        select(
            Loan,
            paid.label("paid_cents"),
            totals.c.last_payment,
            totals.c.returned_at,
            complete.label("is_complete"),
            Audit.id.is_not(None).label("is_voided"),
            Audit.recorded_at.label("voided_at"),
            Audit.reason.label("void_reason"),
        )
        .outerjoin(totals, totals.c.loan_id == Loan.id)
        .outerjoin(
            Audit, and_(Audit.loan_id == Loan.id, Audit.owner_id == owner, Audit.action == "void")
        )
        .where(Loan.owner_id == owner)
    )


def loan_read(row, at: datetime) -> LoanRead:
    loan = row[0]
    money = loan.kind == "money"
    paid = int(row.paid_cents) if money else None
    complete = bool(row.is_complete)
    voided = bool(row.is_voided)
    completed_at = (row.last_payment if money else row.returned_at) if complete else None
    return LoanRead(
        id=loan.id,
        friend_id=loan.friend_id,
        kind=loan.kind,
        description=loan.description,
        notes=loan.notes,
        lent_at=loan.lent_at,
        due_date=loan.due_date,
        timezone=loan.timezone,
        overdue_at=loan.overdue_at,
        created_at=loan.created_at,
        principal_cents=loan.principal_cents,
        currency=loan.currency,
        repaid_cents=paid,
        outstanding_cents=(0 if voided else loan.principal_cents - paid) if money else None,
        returned_at=row.returned_at,
        completed_at=completed_at,
        status="voided" if voided else "completed" if complete else "open",
        overdue=not complete and not voided and at >= utc(loan.overdue_at),
        voided_at=row.voided_at,
        void_reason=row.void_reason,
    )


def loan_for_owner(session: Session, owner: UUID, loan_id: UUID) -> LoanRead:
    row = session.execute(loan_query(owner).where(Loan.id == loan_id)).one_or_none()
    if row is None:
        raise HTTPException(404, "Loan not found.")
    return loan_read(row, now_utc())


def lock_owner(session: Session, user: Identity) -> Profile:
    get_or_create_profile(session, user)
    return session.scalar(
        select(Profile)
        .where(Profile.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def mutate(
    session: Session,
    user: Identity,
    key: UUID,
    operation: str,
    body: BaseModel,
    work: Callable[[Profile], BaseModel],
) -> JSONResponse:
    # Serialize all ledger writes for this owner. This coordinates archive/create and
    # concurrent payments, including across workers. There is no network I/O under the lock.
    owner = lock_owner(session, user)
    digest = hashlib.sha256(
        json.dumps(
            {"operation": operation, "body": body.model_dump(mode="json")},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    receipt = session.get(MutationReceipt, (user.id, key))
    if receipt is not None:
        if receipt.request_hash != digest:
            raise HTTPException(409, "Idempotency key was already used for a different request.")
        response = JSONResponse(
            receipt.payload,
            receipt.status_code,
            headers={
                "Cache-Control": "no-store",
                "Idempotency-Replayed": "true",
            },
        )
        session.rollback()  # Read-only replay: release the owner lock before sending the response.
        return response
    result = work(owner).model_dump(mode="json")
    session.add(
        MutationReceipt(
            owner_id=user.id,
            key=key,
            request_hash=digest,
            status_code=201,
            payload=result,
        )
    )
    # Data changes and receipt commit together; failures leave neither behind.
    session.commit()
    return JSONResponse(
        result,
        201,
        headers={
            "Cache-Control": "no-store",
            "Idempotency-Replayed": "false",
        },
    )


def create_friend(session: Session, owner: UUID, body: FriendCreate) -> FriendRead:
    now = now_utc()
    friend = Friend(id=uuid4(), owner_id=owner, created_at=now, updated_at=now, **body.model_dump())
    session.add(friend)
    session.flush()
    return FriendRead.model_validate(friend)


def create_loan(
    session: Session,
    owner: Profile,
    body: MoneyLoanCreate | ItemLoanCreate,
) -> LoanRead:
    friend = friend_for_owner(session, owner.id, body.friend_id)
    if friend.archived_at is not None:
        raise HTTPException(409, "Archived friends cannot receive new loans.")
    now = now_utc()
    lent = utc(body.lent_at) if body.lent_at is not None else now
    if lent > now:
        raise HTTPException(422, "Lending time cannot be in the future.")
    zone = ZoneInfo(owner.timezone)
    try:
        local_lending_date = lent.astimezone(zone).date()
    except (OverflowError, ValueError):
        raise HTTPException(422, "Lending time is outside the supported range.") from None
    if body.due_date < local_lending_date:
        raise HTTPException(422, "Due date cannot precede the local lending date.")
    try:
        boundary = datetime.combine(body.due_date + timedelta(days=1), time.min, zone).astimezone(
            UTC
        )
    except (OverflowError, ValueError):
        raise HTTPException(422, "Due date is outside the supported range.") from None
    if boundary <= lent:
        raise HTTPException(422, "Due date does not provide a valid boundary after lending time.")
    # A snapshot of the actual inclusive-date boundary avoids SQL timezone conversions
    # and preserves behavior when the owner changes timezone later.
    loan = Loan(
        id=uuid4(),
        owner_id=owner.id,
        friend_id=friend.id,
        kind=body.kind,
        description=body.description,
        notes=body.notes,
        lent_at=lent,
        due_date=body.due_date,
        timezone=owner.timezone,
        overdue_at=boundary,
        created_at=now,
        principal_cents=body.principal_cents if body.kind == "money" else None,
        currency="USD" if body.kind == "money" else None,
    )
    session.add(loan)
    session.flush()
    return loan_for_owner(session, owner.id, loan.id)


def settle(
    session: Session,
    owner: UUID,
    loan_id: UUID,
    body: RepaymentCreate | SettlementInput,
    action: str,
    *,
    replaces_event_id: UUID | None = None,
) -> SettlementRead:
    loan = loan_for_owner(session, owner, loan_id)
    required_kind = "money" if action == "repayment" else "item"
    if loan.kind != required_kind:
        raise HTTPException(409, "This action is not valid for this loan kind.")
    if loan.status != "open":
        raise HTTPException(409, "This loan is completed or voided.")
    amount = body.amount_cents if isinstance(body, RepaymentCreate) else None
    if amount is not None and amount > loan.outstanding_cents:
        raise HTTPException(409, "Repayment exceeds the outstanding principal.")
    now = now_utc()
    effective = utc(body.effective_at) if body.effective_at is not None else now
    if effective < utc(loan.lent_at) or effective > now:
        raise HTTPException(422, "Effective time must be between lending time and now.")
    event = LoanEvent(
        id=uuid4(),
        owner_id=owner,
        loan_id=loan_id,
        loan_kind=loan.kind,
        action=action,
        replaces_event_id=replaces_event_id,
        amount_cents=amount,
        note=body.note,
        effective_at=effective,
        recorded_at=now,
    )
    session.add(event)
    session.flush()
    return SettlementRead(
        event=EventRead.model_validate(event),
        loan=loan_for_owner(session, owner, loan_id),
    )


def history(
    session: Session,
    owner: UUID,
    friend_id: UUID,
    limit: int,
    offset: int,
    mode: str = "offset",
    cursor: str | None = None,
) -> Page[HistoryEntry]:
    from iou.ledger.history import history as read_history

    return read_history(session, owner, friend_id, limit, offset, mode, cursor)
