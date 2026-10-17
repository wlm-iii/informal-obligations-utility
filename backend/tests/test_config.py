import pytest
from pydantic import ValidationError

from iou.config import Settings


def test_environment_overrides_default(monkeypatch):
    url = "postgresql+psycopg://test@localhost:5432/test"
    monkeypatch.setenv("DATABASE_URL", url)
    assert Settings(_env_file=None).database_url == url


def test_email_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EMAIL_MODE", raising=False)
    assert Settings(_env_file=None).email_mode == "disabled"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com/path",
        "https://example.com?key=secret",
        "not-a-url",
    ],
)
def test_invalid_supabase_origins_rejected(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, supabase_url=url)


def test_supabase_origin_normalized():
    assert Settings(_env_file=None, supabase_url="https://test.supabase.co/").supabase_url == (
        "https://test.supabase.co"
    )


def test_unknown_pool_mode_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_pool_mode="unknown")


def test_unimplemented_email_delivery_fails_closed(monkeypatch):
    monkeypatch.setenv("EMAIL_MODE", "live")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
