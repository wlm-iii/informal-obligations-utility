"""Server-only configuration; environment variables override the root .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator
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
    # Explicit opt-in only. Gmail credentials alone never enable delivery.
    email_mode: Literal["disabled", "gmail"] = "disabled"
    gmail_client_id: SecretStr | None = None
    gmail_client_secret: SecretStr | None = None
    gmail_refresh_token: SecretStr | None = None
    gmail_sender_email: EmailStr | None = None
    # Default live-recipient restriction is the sender's own address.
    gmail_recipient_allowlist: list[EmailStr] = Field(default_factory=list)
    gmail_allow_external_recipients: bool = False
    reminder_signing_key: SecretStr | None = None
    reminder_public_base_url: str = Field(default="http://127.0.0.1:8000", max_length=1024)
    reminder_quiet_hours_enabled: bool = True

    @field_validator(
        "cursor_signing_key",
        "supabase_storage_key",
        "gmail_client_id",
        "gmail_client_secret",
        "gmail_refresh_token",
        "gmail_sender_email",
        "reminder_signing_key",
        mode="before",
    )
    @classmethod
    def empty_secret_is_disabled(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("cursor_signing_key", "reminder_signing_key")
    @classmethod
    def strong_signing_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value().encode()) < 32:
            raise ValueError("Signing keys must contain at least 32 bytes.")
        return value

    @field_validator("reminder_public_base_url")
    @classmethod
    def reminder_url(cls, value: str) -> str:
        url = urlsplit(value)
        if (
            not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or (
                url.scheme != "https"
                and not (url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1"))
            )
        ):
            raise ValueError("Reminder base URL must use HTTPS (HTTP allowed only on loopback).")
        return value.rstrip("/")

    @model_validator(mode="after")
    def gmail_configuration(self):
        if self.email_mode == "gmail" and not all(
            (
                self.gmail_client_id,
                self.gmail_client_secret,
                self.gmail_refresh_token,
                self.gmail_sender_email,
                self.reminder_signing_key,
            )
        ):
            raise ValueError(
                "Gmail delivery requires sender credentials and a reminder signing key."
            )
        return self

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
