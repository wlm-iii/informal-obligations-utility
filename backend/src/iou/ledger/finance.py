"""ORM adapter around the pure calculator; no historical allocation rewriting."""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from iou.ledger.calculator import (
    Allocation,
    Balance,
    CalculationError,
    Entry,
    Terms,
    calculate,
    utc,
)
from iou.ledger.models import Loan, LoanEvent


def load(session: Session, owner: UUID, loan_id: UUID) -> Loan:
    loan = session.scalar(
        select(Loan)
        .where(Loan.id == loan_id, Loan.owner_id == owner)
        .options(selectinload(Loan.events))
        .execution_options(populate_existing=True)
    )
    if loan is None:
        raise HTTPException(404, "Loan not found.")
    return loan


def evaluate(loan: Loan, at: datetime, extra: LoanEvent | None = None) -> Balance:
    terms = Terms(
        loan.kind,
        loan.principal_cents or 0,
        utc(loan.lent_at),
        loan.timezone,
        utc(loan.fee_at or loan.overdue_at),
        loan.interest_rate_bps,
        loan.interest_period,
        loan.late_fee_cents,
        loan.charge_cap_cents,
    )
    rows = [*loan.events, *([extra] if extra is not None else [])]
    entries = []
    for row in rows:
        if row.reversed_at is not None:
            continue
        snapshot = None
        if row.principal_applied_cents is not None:
            snapshot = Allocation(
                row.principal_applied_cents, row.interest_applied_cents, row.fees_applied_cents
            )
        entries.append(
            Entry(
                row.id,
                row.action,
                row.amount_cents,
                utc(row.effective_at),
                row.component,
                snapshot,
                row.allocation_order,
            )
        )
    try:
        return calculate(terms, entries, at)
    except CalculationError as error:
        raise HTTPException(409, str(error)) from None


def synchronize(session: Session, owner: UUID, loan_id: UUID, at: datetime) -> Balance:
    loan = load(session, owner, loan_id)
    balance = evaluate(loan, at)
    loan.settled_at = balance.completed_at
    session.flush()
    return balance
