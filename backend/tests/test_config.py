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


def test_evidence_secrets_are_hidden_and_blank_values_disable_features():
    settings = Settings(
        _env_file=None,
        cursor_signing_key="cursor_private_value_" * 3,
        supabase_storage_key="sb_secret_private_value",
    )
    assert "cursor_private_value" not in repr(settings)
    assert "sb_secret_private_value" not in repr(settings)
    disabled = Settings(_env_file=None, cursor_signing_key="", supabase_storage_key=" ")
    assert disabled.cursor_signing_key is None and disabled.supabase_storage_key is None


def test_weak_cursor_keys_do_not_appear_in_config_errors():
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, cursor_signing_key="short_private_key")
    assert "short_private_key" not in str(error.value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"evidence_bucket": "../public"},
        {"evidence_bucket": "has/slash"},
        {"evidence_signed_url_seconds": 301},
        {"evidence_signed_url_seconds": 0},
    ],
)
def test_evidence_configuration_is_bounded(kwargs):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)


def test_unimplemented_email_delivery_fails_closed(monkeypatch):
    monkeypatch.setenv("EMAIL_MODE", "live")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
