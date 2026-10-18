from datetime import datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from iou.ledger.schemas import Input, Notes, ReadModel


class EvidenceCreate(Input):
    filename: Annotated[str, Field(min_length=1, max_length=200)]
    content_type: Literal["image/jpeg", "image/png"]
    event_id: UUID | None = None
    note: Notes | None = None

    @field_validator("filename")
    @classmethod
    def filename_label_only(cls, value: str) -> str:
        value = PurePosixPath(value.replace("\\", "/")).name
        if not value or value in (".", "..") or any(ord(char) < 32 for char in value):
            raise ValueError("Use a valid filename label.")
        return value


class EvidenceRead(ReadModel):
    id: UUID
    loan_id: UUID
    event_id: UUID | None
    state: Literal["pending", "uploading", "ready", "removed"]
    filename: str
    note: str | None
    content_type: Literal["image/jpeg", "image/png"]
    original_sha256: str | None
    sha256: str | None
    original_size_bytes: int | None
    size_bytes: int | None
    width: int | None
    height: int | None
    created_at: datetime
    expires_at: datetime
    uploaded_at: datetime | None
    removed_at: datetime | None
    cleaned_at: datetime | None


class SignedEvidenceURL(ReadModel):
    url: str
    expires_at: datetime
