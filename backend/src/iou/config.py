"""Server-only configuration; environment variables override the root .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://iou@127.0.0.1:54329/iou"
    # No delivery implementation exists yet; fail closed for any other value.
    email_mode: Literal["disabled"] = "disabled"


@lru_cache
def get_settings() -> Settings:
    return Settings()
