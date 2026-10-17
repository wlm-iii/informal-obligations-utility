"""Authenticated Level 1 API. These paths are mounted at /api in browser deployments."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Query, Response
from sqlalchemy import or_, select

from iou.auth import CurrentUser
from iou.ledger import pagination as pages
from iou.ledger import service
from iou.ledger.models import Friend, Loan
from iou.ledger.schemas import (
    FriendCreate,
    FriendRead,
    FriendUpdate,
    HistoryEntry,
    LoanCreate,
    LoanRead,
    Page,
    RepaymentCreate,
    SettlementInput,
    SettlementRead,
)
from iou.profiles import SessionDependency


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(tags=["ledger"], dependencies=[Depends(no_store)])
Key = Annotated[UUID, Header(alias="Idempotency-Key")]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100_000)]
Mode = Literal["offset", "cursor"]
Cursor = Annotated[str | None, Query(max_length=4096)]


@router.post("/friends", response_model=FriendRead, status_code=201)
def create_friend(body: FriendCreate, user: CurrentUser, session: SessionDependency, key: Key):
    return service.mutate(
        session,
        user,
        key,
        "create-friend",
        body,
        lambda owner: service.create_friend(session, owner.id, body),
    )


@router.get("/friends", response_model=Page[FriendRead])
def friends(
    user: CurrentUser,
    session: SessionDependency,
    archived: Literal["exclude", "only", "include"] = "exclude",
    limit: Limit = 25,
    offset: Offset = 0,
    pagination: Mode = "offset",
    cursor: Cursor = None,
):
    query = select(Friend).where(Friend.owner_id == user.id)
    if archived != "include":
        query = query.where(
            Friend.archived_at.is_not(None) if archived == "only" else Friend.archived_at.is_(None)
        )
    page = pages.paginate(
        session,
        query,
        owner=user.id,
        scope={"endpoint": "friends", "archived": archived},
        limit=limit,
        offset=offset,
        mode=pagination,
        cursor=cursor,
        order=(Friend.created_at, Friend.id),
        recorded=Friend.created_at,
        now=service.now_utc(),
    )
    return Page[FriendRead](
        items=[FriendRead.model_validate(row[0]) for row in page.rows],
        limit=limit,
        offset=offset,
        has_more=page.has_more,
        next_cursor=page.next_cursor,
    )


@router.get("/friends/{friend_id}", response_model=FriendRead)
def friend(friend_id: UUID, user: CurrentUser, session: SessionDependency):
    return service.friend_for_owner(session, user.id, friend_id)


@router.patch("/friends/{friend_id}", response_model=FriendRead)
def update_friend(
    friend_id: UUID, body: FriendUpdate, user: CurrentUser, session: SessionDependency
):
    service.lock_owner(session, user)
    friend = service.friend_for_owner(session, user.id, friend_id)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(friend, key, value)
    if changes:
        friend.updated_at = service.now_utc()
    session.commit()
    session.refresh(friend)
    return friend


@router.post("/friends/{friend_id}/archive", response_model=FriendRead)
def archive_friend(friend_id: UUID, user: CurrentUser, session: SessionDependency):
    service.lock_owner(session, user)
    friend = service.friend_for_owner(session, user.id, friend_id)
    if friend.archived_at is None:
        friend.archived_at = friend.updated_at = service.now_utc()
    session.commit()
    session.refresh(friend)
    return friend


@router.get("/friends/{friend_id}/history", response_model=Page[HistoryEntry])
def history(
    friend_id: UUID,
    user: CurrentUser,
    session: SessionDependency,
    limit: Limit = 25,
    offset: Offset = 0,
    pagination: Mode = "offset",
    cursor: Cursor = None,
):
    return service.history(session, user.id, friend_id, limit, offset, pagination, cursor)


@router.post("/loans", response_model=LoanRead, status_code=201)
def create_loan(body: LoanCreate, user: CurrentUser, session: SessionDependency, key: Key):
    return service.mutate(
        session,
        user,
        key,
        "create-loan",
        body,
        lambda owner: service.create_loan(session, owner, body),
    )


@router.get("/loans", response_model=Page[LoanRead])
def loans(
    user: CurrentUser,
    session: SessionDependency,
    friend_id: UUID | None = None,
    kind: Literal["money", "item"] | None = None,
    status: Literal["open", "completed", "voided"] | None = None,
    overdue: bool | None = None,
    limit: Limit = 25,
    offset: Offset = 0,
    pagination: Mode = "offset",
    cursor: Cursor = None,
):
    at = service.now_utc()
    query = service.loan_query(user.id)
    complete = query.selected_columns.is_complete
    voided = query.selected_columns.is_voided
    if friend_id is not None:
        service.friend_for_owner(session, user.id, friend_id)
        query = query.where(Loan.friend_id == friend_id)
    if kind is not None:
        query = query.where(Loan.kind == kind)
    if status == "open":
        query = query.where(~complete, ~voided)
    elif status == "completed":
        query = query.where(complete)
    elif status == "voided":
        query = query.where(voided)
    if overdue is not None:
        query = query.where(
            or_(complete, voided, Loan.overdue_at > at)
            if not overdue
            else (~complete & (Loan.overdue_at <= at))
        )
    page = pages.paginate(
        session,
        query,
        owner=user.id,
        scope={
            "endpoint": "loans",
            "friend": friend_id,
            "kind": kind,
            "status": status,
            "overdue": overdue,
        },
        limit=limit,
        offset=offset,
        mode=pagination,
        cursor=cursor,
        order=(Loan.created_at, Loan.id),
        recorded=Loan.created_at,
        now=at,
    )
    return Page[LoanRead](
        items=[service.loan_read(row, at) for row in page.rows],
        limit=limit,
        offset=offset,
        has_more=page.has_more,
        next_cursor=page.next_cursor,
    )


@router.get("/loans/{loan_id}", response_model=LoanRead)
def loan(loan_id: UUID, user: CurrentUser, session: SessionDependency):
    return service.loan_for_owner(session, user.id, loan_id)


@router.post("/loans/{loan_id}/repayments", response_model=SettlementRead, status_code=201)
def repay(
    loan_id: UUID, body: RepaymentCreate, user: CurrentUser, session: SessionDependency, key: Key
):
    return service.mutate(
        session,
        user,
        key,
        f"repay:{loan_id}",
        body,
        lambda owner: service.settle(session, owner.id, loan_id, body, "repayment"),
    )


@router.post("/loans/{loan_id}/return", response_model=SettlementRead, status_code=201)
def return_item(
    loan_id: UUID,
    user: CurrentUser,
    session: SessionDependency,
    key: Key,
    body: Annotated[SettlementInput | None, Body()] = None,
):
    body = body or SettlementInput()
    return service.mutate(
        session,
        user,
        key,
        f"return:{loan_id}",
        body,
        lambda owner: service.settle(session, owner.id, loan_id, body, "return"),
    )
