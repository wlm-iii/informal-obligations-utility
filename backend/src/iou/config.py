"""Server-only configuration; environment variables override the root .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )

    database_url: str = "postgresql+psycopg://iou@127.0.0.1:54329/iou"
    # Optional for local foundation checks; protected routes fail closed when absent.
    supabase_url: str | None = None
    database_pool_mode: Literal["session", "transaction"] = "session"
    # Separate server-only secrets. Neither is needed for legacy offset pagination/auth.
    cursor_signing_key: SecretStr | None = None
    supabase_storage_key: SecretStr | None = None
    evidence_bucket: str = Field(default="iou-evidence", pattern=r"^[a-z0-9][a-z0-9_-]{0,62}$")
    evidence_signed_url_seconds: int = Field(default=60, ge=30, le=300)
    # No delivery implementation exists yet; fail closed for any other value.
    email_mode: Literal["disabled"] = "disabled"

    @field_validator("cursor_signing_key", "supabase_storage_key", mode="before")
    @classmethod
    def empty_secret_is_disabled(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("cursor_signing_key")
    @classmethod
    def strong_cursor_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value().encode()) < 32:
            raise ValueError("CURSOR_SIGNING_KEY must contain at least 32 bytes.")
        return value

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = value.rstrip("/")
        url = urlsplit(value)
        local = url.hostname in ("localhost", "127.0.0.1")
        if (
            not url.hostname
            or (url.scheme != "https" and not (local and url.scheme == "http"))
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path
        ):
            raise ValueError(
                "SUPABASE_URL must be an HTTPS project origin (HTTP allowed on loopback)."
            )
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
