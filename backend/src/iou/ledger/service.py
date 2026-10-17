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
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from iou.auth import Identity
from iou.ledger import finance
from iou.ledger.calculator import PERIOD_DAYS, Balance
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
    WaiverCreate,
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
            func.max(LoanEvent.effective_at).label("returned_at"),
        )
        .where(
            LoanEvent.owner_id == owner,
            LoanEvent.reversed_at.is_(None),
            LoanEvent.action == "return",
        )
        .group_by(LoanEvent.loan_id)
        .subquery()
    )
    complete = and_(Audit.id.is_(None), Loan.settled_at.is_not(None))
    return (
        select(
            Loan,
            totals.c.returned_at,
            complete.label("is_complete"),
            and_(
                Audit.id.is_(None),
                or_(
                    and_(Loan.kind == "money", Loan.settled_at.is_(None)),
                    and_(Loan.kind == "item", totals.c.returned_at.is_(None)),
                ),
            ).label("is_borrowing_open"),
            Audit.id.is_not(None).label("is_voided"),
            Audit.recorded_at.label("voided_at"),
            Audit.reason.label("void_reason"),
        )
        .outerjoin(totals, totals.c.loan_id == Loan.id)
        .outerjoin(
            Audit, and_(Audit.loan_id == Loan.id, Audit.owner_id == owner, Audit.action == "void")
        )
        .where(Loan.owner_id == owner)
        .options(selectinload(Loan.events))
        .execution_options(populate_existing=True)
    )


def loan_read(row, at: datetime) -> LoanRead:
    loan = row[0]
    money = loan.kind == "money"
    voided = bool(row.is_voided)
    balance = Balance(0) if voided else finance.evaluate(loan, at)
    complete = balance.completed_at is not None
    borrowing_complete = complete if money else balance.returned_at is not None
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
        repaid_cents=(balance.principal_paid + balance.interest_paid + balance.fees_paid)
        if money
        else None,
        outstanding_cents=balance.principal if money else None,
        returned_at=balance.returned_at,
        completed_at=balance.completed_at,
        interest_cents=balance.interest,
        fees_cents=balance.fees,
        interest_rate_bps=loan.interest_rate_bps,
        interest_period=loan.interest_period,
        interest_period_days=PERIOD_DAYS[loan.interest_period],
        late_fee_cents=loan.late_fee_cents,
        grace_days=loan.grace_days,
        charge_cap_cents=loan.charge_cap_cents,
        calculation_version=loan.calculation_version,
        calculated_at=at,
        fee_at=loan.fee_at or loan.overdue_at,
        late_fee_assessed_at=balance.fee_assessed_at,
        interest_accrued_cents=balance.interest_accrued,
        late_fee_assessed_cents=balance.fee_assessed,
        principal_repaid_cents=balance.principal_paid,
        interest_paid_cents=balance.interest_paid,
        fees_paid_cents=balance.fees_paid,
        interest_waived_cents=balance.interest_waived,
        fees_waived_cents=balance.fees_waived,
        total_outstanding_cents=balance.total,
        borrowing_status="voided"
        if voided
        else ("repaid" if money else "returned")
        if borrowing_complete
        else "outstanding",
        settlement_status="voided" if voided else "settled" if balance.total == 0 else "unpaid",
        status="voided" if voided else "completed" if complete else "open",
        overdue=not borrowing_complete and not voided and at >= utc(loan.overdue_at),
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
        compatible = {digest}
        # Old creation receipts predate optional term fields. A default zero-charge
        # retry may replay them, but adding any new term must still conflict.
        payload = body.model_dump(mode="json")
        if operation == "create-loan" and all(
            payload.get(name, default) == default
            for name, default in {
                "interest_rate_bps": 0,
                "interest_period": "weekly",
                "late_fee_cents": 0,
                "grace_days": 0,
                "charge_cap_cents": None,
            }.items()
        ):
            for name in (
                "interest_rate_bps",
                "interest_period",
                "late_fee_cents",
                "grace_days",
                "charge_cap_cents",
            ):
                payload.pop(name, None)
            compatible.add(
                hashlib.sha256(
                    json.dumps(
                        {"operation": operation, "body": payload},
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
            )
        if receipt.request_hash not in compatible:
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
    try:
        fee_at = datetime.combine(
            body.due_date + timedelta(days=body.grace_days + 1), time.min, zone
        ).astimezone(UTC)
    except (OverflowError, ValueError):
        raise HTTPException(422, "Grace period exceeds the supported date range.") from None
    rate = body.interest_rate_bps if body.kind == "money" else 0
    default_cap = (
        max(body.principal_cents if body.kind == "money" else 0, body.late_fee_cents)
        if rate or body.late_fee_cents
        else 0
    )
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
        interest_rate_bps=rate,
        interest_period=body.interest_period if body.kind == "money" else "weekly",
        late_fee_cents=body.late_fee_cents,
        grace_days=body.grace_days,
        fee_at=fee_at,
        charge_cap_cents=body.charge_cap_cents
        if body.charge_cap_cents is not None
        else default_cap,
        calculation_version=1,
    )
    session.add(loan)
    session.flush()
    return loan_for_owner(session, owner.id, loan.id)


def settle(
    session: Session,
    owner: UUID,
    loan_id: UUID,
    body: RepaymentCreate | SettlementInput | WaiverCreate,
    action: str,
    *,
    replaces_event_id: UUID | None = None,
) -> SettlementRead:
    loan = finance.load(session, owner, loan_id)
    voided = session.scalar(
        select(Audit.id).where(
            Audit.loan_id == loan_id, Audit.owner_id == owner, Audit.action == "void"
        )
    )
    if voided:
        raise HTTPException(409, "This loan is voided.")
    if (action == "repayment" and loan.kind != "money") or (
        action in ("return", "fee_payment") and loan.kind != "item"
    ):
        raise HTTPException(409, "This action is not valid for this loan kind.")
    amount = body.amount_cents if isinstance(body, (RepaymentCreate, WaiverCreate)) else None
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
        allocation_order=(
            session.get(LoanEvent, replaces_event_id).allocation_order
            if replaces_event_id
            else max((e.allocation_order for e in loan.events), default=0) + 1
        ),
        amount_cents=amount,
        component=body.component if isinstance(body, WaiverCreate) else None,
        reason=body.reason if isinstance(body, WaiverCreate) else None,
        note=body.note,
        effective_at=effective,
        recorded_at=now,
    )
    balance = finance.evaluate(loan, now, extra=event)
    if action != "return":
        allocation = balance.allocations[event.id]
        event.principal_applied_cents = allocation.principal
        event.interest_applied_cents = allocation.interest
        event.fees_applied_cents = allocation.fees
    loan.settled_at = balance.completed_at
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
