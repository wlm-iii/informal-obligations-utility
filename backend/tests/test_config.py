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


def test_unimplemented_email_delivery_fails_closed(monkeypatch):
    monkeypatch.setenv("EMAIL_MODE", "live")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
