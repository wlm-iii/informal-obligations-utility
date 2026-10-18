"""Preset previews and explicitly approved sends. Public unsubscribe is POST-only."""

from html import escape
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from iou.auth import CurrentUser
from iou.ledger import service as ledger
from iou.ledger.router import Key, Limit, no_store
from iou.ledger.schemas import Page
from iou.profiles import SessionDependency
from iou.reminders import service
from iou.reminders.models import Reminder
from iou.reminders.schemas import (
    PermissionInput,
    PermissionRead,
    PreviewInput,
    ReminderRead,
    SendInput,
)

router = APIRouter(tags=["manual reminders"], dependencies=[Depends(no_store)])
Offset = Annotated[int, Query(ge=0, le=100_000)]


@router.get("/friends/{friend_id}/reminder-preferences", response_model=PermissionRead)
def preferences(friend_id: UUID, user: CurrentUser, session: SessionDependency):
    friend = ledger.friend_for_owner(session, user.id, friend_id)
    return service.permission_read(session, user.id, friend)


@router.put(
    "/friends/{friend_id}/reminder-preferences", response_model=PermissionRead, status_code=201
)
def permission(
    friend_id: UUID, body: PermissionInput, user: CurrentUser, session: SessionDependency, key: Key
):
    return ledger.mutate(
        session,
        user,
        key,
        f"reminder-permission:{friend_id}",
        body,
        lambda owner: service.update_permission(session, owner.id, friend_id, body),
    )


@router.post("/friends/{friend_id}/reminder-previews", response_model=ReminderRead, status_code=201)
def preview(
    friend_id: UUID, body: PreviewInput, user: CurrentUser, session: SessionDependency, key: Key
):
    return ledger.mutate(
        session,
        user,
        key,
        f"reminder-preview:{friend_id}",
        body,
        lambda owner: service.create_preview(session, owner.id, friend_id, body),
    )


@router.post("/reminders/{reminder_id}/send", response_model=ReminderRead, status_code=202)
def send(
    reminder_id: UUID, body: SendInput, user: CurrentUser, session: SessionDependency, key: Key
):
    return service.send(session, user, reminder_id, body, key)


@router.get("/reminders", response_model=Page[ReminderRead])
def history(
    user: CurrentUser,
    session: SessionDependency,
    friend_id: UUID | None = None,
    limit: Limit = 25,
    offset: Offset = 0,
):
    if friend_id is not None:
        ledger.friend_for_owner(session, user.id, friend_id)
    query = select(Reminder).where(Reminder.owner_id == user.id)
    if friend_id is not None:
        query = query.where(Reminder.friend_id == friend_id)
    rows = list(
        session.scalars(
            query.order_by(Reminder.created_at.desc(), Reminder.id.desc())
            .offset(offset)
            .limit(limit + 1)
        )
    )
    return Page[ReminderRead](
        items=[ReminderRead.model_validate(row) for row in rows[:limit]],
        limit=limit,
        offset=offset,
        has_more=len(rows) > limit,
    )


# Before /reminders/{reminder_id}: literal unsubscribe must never be parsed as a UUID.
@router.get("/reminders/unsubscribe", response_class=HTMLResponse)
def unsubscribe_confirmation(token: Annotated[str, Query(max_length=256)]):
    service.verify_token(token)
    return HTMLResponse(
        '<!doctype html><meta name="viewport" content="width=device-width">'
        "<title>Stop IOU reminders</title><h1>Stop IOU email reminders?</h1>"
        "<p>This stops reminders to this address from all IOU users.</p>"
        '<form method="post" action="unsubscribe"><input type="hidden" name="token" value="'
        + escape(token, quote=True)
        + '"><button type="submit">Stop reminders</button></form>',
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; form-action 'self'; base-uri 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/reminders/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: Annotated[str, Form(max_length=256)], session: SessionDependency):
    service.unsubscribe(session, token)
    return HTMLResponse(
        "<h1>IOU reminders stopped.</h1><p>You can close this page.</p>",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.get("/reminders/{reminder_id}", response_model=ReminderRead)
def reminder(reminder_id: UUID, user: CurrentUser, session: SessionDependency):
    return service.owned(session, user.id, reminder_id)
