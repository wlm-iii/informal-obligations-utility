from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from iou.auth import CurrentUser
from iou.evidence import service
from iou.evidence.models import MAX_BYTES, Evidence
from iou.evidence.schemas import EvidenceCreate, EvidenceRead, SignedEvidenceURL
from iou.ledger import pagination as pages
from iou.ledger import service as ledger
from iou.ledger.router import Cursor, Key, Limit, Mode, Offset, no_store
from iou.ledger.schemas import Page, ReasonInput
from iou.profiles import SessionDependency

router = APIRouter(tags=["evidence"], dependencies=[Depends(no_store)])


@router.post("/loans/{loan_id}/evidence", response_model=EvidenceRead, status_code=201)
def create(
    loan_id: UUID, body: EvidenceCreate, user: CurrentUser, session: SessionDependency, key: Key
):
    return ledger.mutate(
        session,
        user,
        key,
        f"evidence-intent:{loan_id}",
        body,
        lambda owner: service.create_intent(session, owner.id, loan_id, body),
    )


@router.get("/loans/{loan_id}/evidence", response_model=Page[EvidenceRead])
def listing(
    loan_id: UUID,
    user: CurrentUser,
    session: SessionDependency,
    state: Literal["pending", "uploading", "ready", "removed"] | None = None,
    limit: Limit = 25,
    offset: Offset = 0,
    pagination: Mode = "offset",
    cursor: Cursor = None,
):
    ledger.loan_for_owner(session, user.id, loan_id)
    query = select(Evidence).where(Evidence.owner_id == user.id, Evidence.loan_id == loan_id)
    if state is not None:
        query = query.where(Evidence.state == state)
    page = pages.paginate(
        session,
        query,
        owner=user.id,
        scope={"endpoint": "evidence", "loan": loan_id, "state": state},
        limit=limit,
        offset=offset,
        mode=pagination,
        cursor=cursor,
        order=(Evidence.created_at, Evidence.id),
        recorded=Evidence.created_at,
        now=ledger.now_utc(),
    )
    return Page[EvidenceRead](
        items=[EvidenceRead.model_validate(row[0]) for row in page.rows],
        limit=limit,
        offset=offset,
        has_more=page.has_more,
        next_cursor=page.next_cursor,
    )


@router.get("/evidence/{evidence_id}", response_model=EvidenceRead)
def detail(evidence_id: UUID, user: CurrentUser, session: SessionDependency):
    return service.evidence_for_owner(session, user.id, evidence_id)


@router.put(
    "/evidence/{evidence_id}/content",
    response_model=EvidenceRead,
    openapi_extra={
        "requestBody": {
            "required": True,
            "description": "Raw static JPEG/PNG, at most 5 MiB.",
            "content": {
                mime: {"schema": {"type": "string", "format": "binary"}}
                for mime in ("image/jpeg", "image/png")
            },
        }
    },
)
async def content(
    evidence_id: UUID, request: Request, user: CurrentUser, session: SessionDependency
):
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    await run_in_threadpool(service.upload_preflight, session, user.id, evidence_id, content_type)
    length = request.headers.get("content-length")
    if length is not None:
        try:
            size = int(length)
            if size < 0:
                raise ValueError
        except ValueError:
            raise HTTPException(400, "Invalid Content-Length.") from None
        if size > MAX_BYTES:
            raise HTTPException(413, "Image exceeds 5 MiB.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "Image exceeds 5 MiB.")
        data.extend(chunk)
    return await run_in_threadpool(
        service.upload, session, user, evidence_id, bytes(data), content_type
    )


@router.post("/evidence/{evidence_id}/view-url", response_model=SignedEvidenceURL)
def view_url(evidence_id: UUID, user: CurrentUser, session: SessionDependency):
    return service.signed_url(session, user, evidence_id)


@router.post("/evidence/{evidence_id}/remove", response_model=EvidenceRead, status_code=201)
def remove(
    evidence_id: UUID, body: ReasonInput, user: CurrentUser, session: SessionDependency, key: Key
):
    return ledger.mutate(
        session,
        user,
        key,
        f"evidence-remove:{evidence_id}",
        body,
        lambda owner: service.remove(session, owner.id, evidence_id, body.reason),
    )
