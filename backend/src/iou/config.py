"""Server-only configuration; environment variables override the root .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://iou@127.0.0.1:54329/iou"
    # Optional for local foundation checks; protected routes fail closed when absent.
    supabase_url: str | None = None
    database_pool_mode: Literal["session", "transaction"] = "session"
    # No delivery implementation exists yet; fail closed for any other value.
    email_mode: Literal["disabled"] = "disabled"

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
