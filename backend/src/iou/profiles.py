"""Private application profiles, keyed only by the verified Supabase subject."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, String, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from iou.auth import CurrentUser, Identity
from iou.database import Base, get_session

router = APIRouter(tags=["profile"])


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = {"schema": "iou_app"}

    id: Mapped[UUID] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(100), default="UTC", server_default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProfileResponse(BaseModel):
    id: UUID
    email: str | None
    display_name: str
    timezone: str
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        # PostgreSQL renders timestamptz in the connection's timezone; API always uses UTC.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("display_name", "timezone", mode="before")
    @classmethod
    def not_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null.")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use a valid IANA timezone, such as America/Los_Angeles.") from None
        return value


def get_or_create_profile(session: Session, user: Identity) -> Profile:
    profile = session.get(Profile, user.id)
    if profile is None:
        profile = Profile(id=user.id, display_name=user.display_name, timezone="UTC")
        session.add(profile)
        try:
            session.commit()
        except IntegrityError:
            # Concurrent first requests may insert the same subject. Never overwrite it.
            session.rollback()
            profile = session.get(Profile, user.id)
            if profile is None:
                raise
        session.refresh(profile)
    return profile


def serialize(profile: Profile, user: Identity, response: Response) -> ProfileResponse:
    response.headers["Cache-Control"] = "no-store"
    return ProfileResponse(
        id=profile.id,
        email=user.email,
        display_name=profile.display_name,
        timezone=profile.timezone,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


SessionDependency = Annotated[Session, Depends(get_session)]


@router.get("/me", response_model=ProfileResponse)
def me(user: CurrentUser, session: SessionDependency, response: Response):
    """Idempotently provision the signed-in user's profile on first access."""
    return serialize(get_or_create_profile(session, user), user, response)


@router.patch("/me", response_model=ProfileResponse)
def update_me(
    body: ProfileUpdate, user: CurrentUser, session: SessionDependency, response: Response
):
    profile = get_or_create_profile(session, user)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(profile, key, value)
    if changes:
        profile.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(profile)
    return serialize(profile, user, response)
