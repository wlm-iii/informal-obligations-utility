from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import EmailStr, Field

from iou.ledger.schemas import Input, ReadModel

Tone = Literal["friendly", "playful", "direct"]
Status = Literal["preview", "reserved", "sending", "sent", "failed", "uncertain", "cancelled"]


class PermissionInput(Input):
    recipient_email: EmailStr
    permission_confirmed: Annotated[bool, Field(strict=True)]


class PermissionRead(ReadModel):
    friend_id: UUID
    recipient_email: str | None
    permission_confirmed: bool
    opted_out: bool


class PreviewInput(Input):
    tone: Tone = "friendly"


class SendInput(Input):
    approved: Annotated[bool, Field(strict=True)]
    recipient_email: EmailStr


class ReminderRead(ReadModel):
    id: UUID
    friend_id: UUID
    recipient_email: str
    tone: Tone
    subject: str
    body: str
    status: Status
    created_at: datetime
    expires_at: datetime
    updated_at: datetime
    attempted_at: datetime | None
    sent_at: datetime | None
    provider_message_id: str | None
    error_code: str | None
