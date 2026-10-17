import json
from io import BytesIO
from urllib.error import HTTPError

import pytest
from fastapi import HTTPException

from iou.config import Settings
from iou.evidence import storage
from iou.evidence.storage import NoRedirects, Storage, StorageUnavailable


class Opener:
    def __init__(self, response=b"{}", error=None):
        self.response = response
        self.error = error
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        assert timeout == 10
        if self.error:
            raise self.error
        return BytesIO(self.response)


def test_secret_keys_are_only_sent_in_apikey_header(monkeypatch):
    opener = Opener()
    monkeypatch.setattr(storage, "build_opener", lambda *args: opener)
    client = Storage("https://project.supabase.co", "iou-evidence", "sb_secret_test_only")
    client._request("GET", "/bucket/iou-evidence")
    headers = {k.lower(): v for k, v in opener.requests[0].headers.items()}
    assert headers["apikey"] == "sb_secret_test_only"
    assert "authorization" not in headers
    assert "sb_secret" not in opener.requests[0].full_url


def test_legacy_jwt_keys_get_bearer_header(monkeypatch):
    opener = Opener()
    monkeypatch.setattr(storage, "build_opener", lambda *args: opener)
    Storage("https://project.supabase.co", "iou-evidence", "legacy-test-key")._request(
        "GET", "/bucket/iou-evidence"
    )
    assert opener.requests[0].get_header("Authorization") == "Bearer legacy-test-key"


def test_redirects_are_not_followed():
    assert (
        NoRedirects().redirect_request(None, None, 302, "Redirect", {}, "https://evil.invalid")
        is None
    )


@pytest.mark.parametrize("metadata", [{"public": True}, {}, None, []])
def test_public_or_unknown_bucket_fails_closed(metadata, monkeypatch):
    client = Storage("https://project.supabase.co", "iou-evidence", "sb_secret_test_only")
    monkeypatch.setattr(client, "_request", lambda *a, **k: json.dumps(metadata).encode())
    with pytest.raises(StorageUnavailable):
        client.private_bucket()


def test_duplicate_upload_verifies_existing_content(monkeypatch):
    calls = []

    def request(method, path, **kwargs):
        calls.append((method, path))
        if path.startswith("/bucket/"):
            return b'{"public":false}'
        if method == "POST":
            raise storage.ObjectExists
        return b"same"

    client = Storage("https://project.supabase.co", "iou-evidence", "sb_secret_test_only")
    monkeypatch.setattr(client, "_request", request)
    client.upload("owner/loan/file.png", b"same", "image/png")
    with pytest.raises(StorageUnavailable):
        client.upload("owner/loan/file.png", b"different", "image/png")
    assert ("GET", "/object/iou-evidence/owner/loan/file.png") in calls


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.invalid/secret?token=bad",
        "//evil.invalid/x?token=bad",
        "/object/sign/another-bucket/file?token=bad",
        "/object/sign/iou-evidence/owner/file.png",
    ],
)
def test_bad_signed_urls_never_reach_clients(url, monkeypatch):
    client = Storage("https://project.supabase.co", "iou-evidence", "sb_secret_test_only")

    def request(method, path, **kwargs):
        return (
            b'{"public":false}'
            if path.startswith("/bucket/")
            else json.dumps({"signedURL": url}).encode()
        )

    monkeypatch.setattr(client, "_request", request)
    with pytest.raises(StorageUnavailable):
        client.signed_url("owner/file.png", 60)


def test_signed_url_uses_fixed_origin_and_short_ttl(monkeypatch):
    client = Storage("https://project.supabase.co", "iou-evidence", "sb_secret_test_only")

    def request(method, path, **kwargs):
        if path.startswith("/bucket/"):
            return b'{"public":false}'
        assert json.loads(kwargs["data"]) == {"expiresIn": 60}
        return b'{"signedURL":"/object/sign/iou-evidence/owner/file.png?token=test"}'

    monkeypatch.setattr(client, "_request", request)
    assert (
        client.signed_url("owner/file.png", 60)
        == "https://project.supabase.co/storage/v1/object/sign/iou-evidence/owner/file.png?token=test"
    )


def test_provider_errors_are_sanitized(monkeypatch):
    error = HTTPError(
        "https://project.supabase.co",
        500,
        "private provider info",
        {},
        BytesIO(b'{"error":"private secret detail"}'),
    )
    monkeypatch.setattr(storage, "build_opener", lambda *args: Opener(error=error))
    with pytest.raises(StorageUnavailable) as caught:
        Storage("https://project.supabase.co", "iou-evidence", "sb_secret_test_only")._request(
            "POST", "/object/iou-evidence/file.png", data=b"x"
        )
    assert "private" not in str(caught.value)


def test_supabase_duplicate_status_in_error_body_is_recognized(monkeypatch):
    error = HTTPError(
        "https://project.supabase.co",
        400,
        "Bad request",
        {},
        BytesIO(b'{"statusCode":"409","error":"Duplicate"}'),
    )
    monkeypatch.setattr(storage, "build_opener", lambda *args: Opener(error=error))
    with pytest.raises(storage.ObjectExists):
        Storage("https://project.supabase.co", "iou-evidence", "sb_secret_test_only")._request(
            "POST", "/object/iou-evidence/file.png", data=b"x"
        )


def test_factory_refuses_missing_key_and_changed_project(monkeypatch):
    settings = Settings(
        _env_file=None, supabase_url="https://project.supabase.co", supabase_storage_key=None
    )
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    with pytest.raises(HTTPException) as error:
        storage.get_storage()
    assert error.value.status_code == 503
    settings.supabase_storage_key = Settings(
        _env_file=None, supabase_storage_key="sb_secret_test_only"
    ).supabase_storage_key
    with pytest.raises(HTTPException):
        storage.get_storage("iou-evidence", "https://another.supabase.co")
    assert storage.get_storage("old-bucket", "https://project.supabase.co").bucket == "old-bucket"
    with pytest.raises(HTTPException):
        storage.get_storage("../invalid")


def test_response_and_object_paths_are_bounded(monkeypatch):
    monkeypatch.setattr(storage, "build_opener", lambda *args: Opener(response=b"x" * 20))
    client = Storage("https://project.supabase.co", "iou-evidence", "sb_secret_test_only")
    with pytest.raises(StorageUnavailable):
        client._request("GET", "/bucket/iou-evidence", limit=10)
    for path in ("", "../file.png", "owner//file.png"):
        with pytest.raises(StorageUnavailable):
            client.object_path(path)
