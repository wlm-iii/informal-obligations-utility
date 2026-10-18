from uuid import UUID

from fastapi import APIRouter, Depends

from iou.auth import CurrentUser
from iou.ledger import corrections, service
from iou.ledger.router import Key, no_store
from iou.ledger.schemas import CorrectionInput, CorrectionRead, EventRead, ReasonInput, VoidRead
from iou.profiles import SessionDependency

router = APIRouter(tags=["corrections"], dependencies=[Depends(no_store)])


@router.get("/loans/{loan_id}/events/{event_id}", response_model=EventRead)
def event(loan_id: UUID, event_id: UUID, user: CurrentUser, session: SessionDependency):
    return corrections.event_for_owner(session, user.id, loan_id, event_id)


@router.post(
    "/loans/{loan_id}/events/{event_id}/reverse", response_model=CorrectionRead, status_code=201
)
def reverse(
    loan_id: UUID,
    event_id: UUID,
    body: ReasonInput,
    user: CurrentUser,
    session: SessionDependency,
    key: Key,
):
    return service.mutate(
        session,
        user,
        key,
        f"reverse:{loan_id}:{event_id}",
        body,
        lambda owner: corrections.reverse_or_correct(session, owner.id, loan_id, event_id, body),
    )


@router.post(
    "/loans/{loan_id}/events/{event_id}/correct", response_model=CorrectionRead, status_code=201
)
def correct(
    loan_id: UUID,
    event_id: UUID,
    body: CorrectionInput,
    user: CurrentUser,
    session: SessionDependency,
    key: Key,
):
    return service.mutate(
        session,
        user,
        key,
        f"correct:{loan_id}:{event_id}",
        body,
        lambda owner: corrections.reverse_or_correct(session, owner.id, loan_id, event_id, body),
    )


@router.post("/loans/{loan_id}/void", response_model=VoidRead, status_code=201)
def void(loan_id: UUID, body: ReasonInput, user: CurrentUser, session: SessionDependency, key: Key):
    return service.mutate(
        session,
        user,
        key,
        f"void:{loan_id}",
        body,
        lambda owner: corrections.void_loan(session, owner.id, loan_id, body),
    )
