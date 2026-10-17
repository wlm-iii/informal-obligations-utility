"""Authenticated dashboard API. Browser routes additionally use the /api prefix."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from iou.auth import CurrentUser
from iou.dashboard import schemas as dto
from iou.dashboard import service
from iou.ledger.router import no_store
from iou.profiles import SessionDependency

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(no_store)])


@router.get("/summary", response_model=dto.Summary)
def summary(
    query: Annotated[dto.ScopeQuery, Query()], user: CurrentUser, session: SessionDependency
):
    return service.summary(service.load(session, user.id, query.friend_id, query.archived))


@router.get("/obligations", response_model=dto.Obligations)
def obligations(
    query: Annotated[dto.ObligationsQuery, Query()], user: CurrentUser, session: SessionDependency
):
    data = service.load(session, user.id, query.friend_id, query.archived)
    return service.obligations(data, query.group, query.upcoming_days, query.limit, query.offset)


@router.get("/rankings", response_model=dto.Rankings)
def rankings(
    query: Annotated[dto.RankingsQuery, Query()], user: CurrentUser, session: SessionDependency
):
    data = service.load(session, user.id, query.friend_id, query.archived)
    return service.rankings(data, query.sort_by, query.direction, query.limit, query.offset)


@router.get("/trends", response_model=dto.Trends)
def trends(
    query: Annotated[dto.TrendsQuery, Query()], user: CurrentUser, session: SessionDependency
):
    data = service.load(session, user.id, query.friend_id, query.archived)
    return service.trends(data, query.start_date, query.end_date, query.bucket)
