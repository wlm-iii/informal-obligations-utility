"""Reversal and void workflows; callers hold the owner lock via service.mutate."""

from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from iou.ledger import finance, service
from iou.ledger.models import Audit, LoanEvent
from iou.ledger.schemas import (
    AuditRead,
    CorrectionInput,
    CorrectionRead,
    EventRead,
    ReasonInput,
    VoidRead,
)


def event_for_owner(session: Session, owner: UUID, loan_id: UUID, event_id: UUID) -> LoanEvent:
    event = session.scalar(
        select(LoanEvent).where(
            LoanEvent.id == event_id,
            LoanEvent.owner_id == owner,
            LoanEvent.loan_id == loan_id,
        )
    )
    if event is None:
        raise HTTPException(404, "Settlement event not found.")
    return event


def reverse_or_correct(
    session: Session,
    owner: UUID,
    loan_id: UUID,
    event_id: UUID,
    body: ReasonInput | CorrectionInput,
) -> CorrectionRead:
    loan = service.loan_for_owner(session, owner, loan_id)
    if loan.status == "voided":
        raise HTTPException(409, "A voided loan cannot be corrected.")
    original = event_for_owner(session, owner, loan_id, event_id)
    if original.reversed_at is not None:
        raise HTTPException(409, "This settlement event has already been reversed.")
    if isinstance(body, CorrectionInput) and body.replacement.action != original.action:
        raise HTTPException(409, "Replacement must have the same settlement kind.")
    now = service.now_utc()
    original.reversed_at = now
    session.flush()  # Release the one-active-return index before adding a replacement.
    replacement = None
    if isinstance(body, CorrectionInput):
        payload = body.replacement.model_copy(
            update={
                "effective_at": body.replacement.effective_at or service.utc(original.effective_at),
            }
        )
        # Re-evaluates the balance after reversal. Later payments are never silently edited.
        settlement = service.settle(
            session,
            owner,
            loan_id,
            payload,
            original.action,
            replaces_event_id=original.id,
        )
        replacement = session.get(LoanEvent, settlement.event.id)
    finance.synchronize(session, owner, loan_id, now)
    audit = Audit(
        id=uuid4(),
        owner_id=owner,
        loan_id=loan_id,
        action="reversal",
        actor="owner",
        reason=body.reason,
        event_id=original.id,
        replacement_event_id=replacement.id if replacement else None,
        effective_at=original.effective_at,
        recorded_at=now,
    )
    session.add(audit)
    session.flush()
    return CorrectionRead(
        reversal=AuditRead.model_validate(audit),
        original_event=EventRead.model_validate(original),
        replacement=EventRead.model_validate(replacement) if replacement else None,
        loan=service.loan_for_owner(session, owner, loan_id),
    )


def void_loan(session: Session, owner: UUID, loan_id: UUID, body: ReasonInput) -> VoidRead:
    loan = service.loan_for_owner(session, owner, loan_id)
    if loan.status == "voided":
        raise HTTPException(409, "This loan is already voided.")
    active = session.scalar(
        select(func.count())
        .select_from(LoanEvent)
        .where(
            LoanEvent.owner_id == owner,
            LoanEvent.loan_id == loan_id,
            LoanEvent.reversed_at.is_(None),
        )
    )
    if active:
        raise HTTPException(409, "Reverse active repayments or returns before voiding this loan.")
    now = service.now_utc()
    audit = Audit(
        id=uuid4(),
        owner_id=owner,
        loan_id=loan_id,
        action="void",
        actor="owner",
        reason=body.reason,
        effective_at=now,
        recorded_at=now,
    )
    session.add(audit)
    session.flush()
    return VoidRead(
        audit=AuditRead.model_validate(audit), loan=service.loan_for_owner(session, owner, loan_id)
    )
