from uuid import UUID

from fastapi import APIRouter, Depends

from iou.auth import CurrentUser
from iou.ledger import scores, service
from iou.ledger.router import Key, no_store
from iou.ledger.schemas import RepaymentCreate, SettlementRead, WaiverCreate
from iou.profiles import SessionDependency

router = APIRouter(tags=["charges and reliability"], dependencies=[Depends(no_store)])


@router.post("/loans/{loan_id}/fee-payments", response_model=SettlementRead, status_code=201)
def fee_payment(
    loan_id: UUID, body: RepaymentCreate, user: CurrentUser, session: SessionDependency, key: Key
):
    return service.mutate(
        session,
        user,
        key,
        f"fee-payment:{loan_id}",
        body,
        lambda owner: service.settle(session, owner.id, loan_id, body, "fee_payment"),
    )


@router.post("/loans/{loan_id}/waivers", response_model=SettlementRead, status_code=201)
def waiver(
    loan_id: UUID, body: WaiverCreate, user: CurrentUser, session: SessionDependency, key: Key
):
    return service.mutate(
        session,
        user,
        key,
        f"waiver:{loan_id}",
        body,
        lambda owner: service.settle(session, owner.id, loan_id, body, "waiver"),
    )


@router.get("/friends/{friend_id}/score", response_model=scores.ScoreRead)
def friend_score(friend_id: UUID, user: CurrentUser, session: SessionDependency):
    return scores.for_friend(session, user.id, friend_id)
