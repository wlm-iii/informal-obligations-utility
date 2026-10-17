"""Financial and evidence timeline with stable, owner-bound keyset pagination."""

from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    String,
    Uuid,
    and_,
    case,
    literal,
    select,
    union_all,
)
from sqlalchemy.orm import Session

from iou.ledger import pagination, service
from iou.ledger.models import Audit, Loan, LoanEvent
from iou.ledger.schemas import HistoryEntry, Page


def timeline_query(owner: UUID, friend_id: UUID):
    def empty_uuid(name):
        return literal(None, type_=Uuid()).label(name)

    lending = select(
        Loan.id.label("id"),
        Loan.id.label("loan_id"),
        literal("lent").label("action"),
        Loan.principal_cents.label("amount_cents"),
        Loan.notes.label("note"),
        Loan.lent_at.label("effective_at"),
        Loan.created_at.label("recorded_at"),
        literal("owner").label("actor"),
        literal(None, type_=String()).label("reason"),
        empty_uuid("event_id"),
        empty_uuid("replacement_event_id"),
        empty_uuid("evidence_id"),
        literal(None, type_=DateTime(timezone=True)).label("reversed_at"),
        empty_uuid("replaces_event_id"),
        literal(None, type_=String()).label("component"),
        literal(None, type_=BigInteger()).label("principal_applied_cents"),
        literal(None, type_=BigInteger()).label("interest_applied_cents"),
        literal(None, type_=BigInteger()).label("fees_applied_cents"),
        literal(None, type_=Integer()).label("allocation_order"),
    ).where(Loan.owner_id == owner, Loan.friend_id == friend_id)
    settlements = (
        select(
            LoanEvent.id,
            LoanEvent.loan_id,
            LoanEvent.action,
            LoanEvent.amount_cents,
            LoanEvent.note,
            LoanEvent.effective_at,
            LoanEvent.recorded_at,
            literal("owner"),
            LoanEvent.reason,
            LoanEvent.id,
            empty_uuid("replacement_event_id"),
            empty_uuid("evidence_id"),
            LoanEvent.reversed_at,
            LoanEvent.replaces_event_id,
            LoanEvent.component,
            LoanEvent.principal_applied_cents,
            LoanEvent.interest_applied_cents,
            LoanEvent.fees_applied_cents,
            LoanEvent.allocation_order,
        )
        .join(Loan, and_(Loan.id == LoanEvent.loan_id, Loan.owner_id == LoanEvent.owner_id))
        .where(
            LoanEvent.owner_id == owner,
            Loan.friend_id == friend_id,
        )
    )
    audits = (
        select(
            Audit.id,
            Audit.loan_id,
            Audit.action,
            case((Audit.action == "reversal", -LoanEvent.amount_cents)),
            literal(None, type_=String()),
            Audit.effective_at,
            Audit.recorded_at,
            Audit.actor,
            Audit.reason,
            Audit.event_id,
            Audit.replacement_event_id,
            Audit.evidence_id,
            literal(None, type_=DateTime(timezone=True)),
            empty_uuid("replaces_event_id"),
            case((Audit.action == "reversal", LoanEvent.component)),
            case((Audit.action == "reversal", -LoanEvent.principal_applied_cents)),
            case((Audit.action == "reversal", -LoanEvent.interest_applied_cents)),
            case((Audit.action == "reversal", -LoanEvent.fees_applied_cents)),
            case((Audit.action == "reversal", LoanEvent.allocation_order)),
        )
        .join(Loan, and_(Loan.id == Audit.loan_id, Loan.owner_id == Audit.owner_id))
        .outerjoin(
            LoanEvent,
            and_(LoanEvent.id == Audit.event_id, LoanEvent.owner_id == Audit.owner_id),
        )
        .where(Audit.owner_id == owner, Loan.friend_id == friend_id)
    )
    return union_all(lending, settlements, audits).subquery()


def history(
    session: Session,
    owner: UUID,
    friend_id: UUID,
    limit: int,
    offset: int,
    mode: str = "offset",
    cursor: str | None = None,
) -> Page[HistoryEntry]:
    service.friend_for_owner(session, owner, friend_id)
    timeline = timeline_query(owner, friend_id)
    at = service.now_utc()
    page = pagination.paginate(
        session,
        select(timeline),
        owner=owner,
        scope={"endpoint": "history", "friend": friend_id},
        limit=limit,
        offset=offset,
        mode=mode,
        cursor=cursor,
        order=(timeline.c.effective_at, timeline.c.recorded_at, timeline.c.id),
        recorded=timeline.c.recorded_at,
        now=at,
    )
    ids = {row.loan_id for row in page.rows}
    loans = (
        {
            row[0].id: service.loan_read(row, at)
            for row in session.execute(service.loan_query(owner).where(Loan.id.in_(ids)))
        }
        if ids
        else {}
    )
    entries = [
        HistoryEntry(
            **{key: value for key, value in row._mapping.items() if key != "loan_id"},
            loan=loans[row.loan_id],
        )
        for row in page.rows
    ]
    return Page[HistoryEntry](
        items=entries,
        limit=limit,
        offset=offset,
        has_more=page.has_more,
        next_cursor=page.next_cursor,
    )
