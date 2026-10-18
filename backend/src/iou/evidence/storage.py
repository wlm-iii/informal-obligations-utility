"""Small bounded Supabase Storage adapter; secrets and provider errors never reach clients."""

import hashlib
import json
import re
from http.client import HTTPException as HTTPProtocolError
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastapi import HTTPException

from iou.config import get_settings
from iou.evidence.models import MAX_BYTES


class StorageUnavailable(Exception):
    pass


class ObjectExists(Exception):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Storage:
    def __init__(self, origin: str, bucket: str, key: str):
        self.origin = origin
        self.base = f"{origin}/storage/v1"
        self.bucket = bucket
        self.key = key

    def _request(self, method, path, *, data=None, content_type="application/json", limit=65536):
        headers = {"apikey": self.key, "Content-Type": content_type, "x-upsert": "false"}
        # Legacy service_role keys are JWTs. New sb_secret keys belong ONLY in apikey.
        if not self.key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {self.key}"
        request = Request(f"{self.base}{path}", data=data, method=method, headers=headers)
        try:
            with build_opener(NoRedirects()).open(request, timeout=10) as response:
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise StorageUnavailable
                return body
        except HTTPError as error:
            try:
                details = json.loads(error.read(8192))
            except (ValueError, OSError, HTTPProtocolError):
                details = {}
            if not isinstance(details, dict):
                details = {}
            if (
                method == "POST"
                and path.startswith(f"/object/{self.bucket}/")
                and (
                    error.code == 409
                    or str(details.get("statusCode")) == "409"
                    or details.get("error") == "Duplicate"
                )
            ):
                raise ObjectExists from None
            if method == "DELETE" and error.code == 404:
                return b"[]"
            raise StorageUnavailable from None
        except (URLError, OSError, TimeoutError, HTTPProtocolError):
            raise StorageUnavailable from None

    def private_bucket(self):
        try:
            metadata = json.loads(self._request("GET", f"/bucket/{self.bucket}"))
            if metadata.get("public") is not False:
                raise StorageUnavailable
        except (ValueError, AttributeError):
            raise StorageUnavailable from None

    def object_path(self, path):
        if not path or any(part in ("", ".", "..") for part in path.split("/")):
            raise StorageUnavailable
        return f"{self.bucket}/{quote(path, safe='/')}"

    def upload(self, path: str, data: bytes, content_type: str):
        self.private_bucket()
        target = self.object_path(path)
        try:
            self._request("POST", f"/object/{target}", data=data, content_type=content_type)
        except ObjectExists:
            # Never overwrite. A retry may find an upload accepted before a network/DB failure.
            existing = self._request("GET", f"/object/{target}", limit=MAX_BYTES)
            if hashlib.sha256(existing).digest() != hashlib.sha256(data).digest():
                raise StorageUnavailable from None

    def signed_url(self, path: str, seconds: int) -> str:
        self.private_bucket()
        target = self.object_path(path)
        try:
            result = json.loads(
                self._request(
                    "POST",
                    f"/object/sign/{target}",
                    data=json.dumps({"expiresIn": seconds}).encode(),
                )
            )
            url = urlsplit(result["signedURL"])
            expected = f"/object/sign/{target}"
            if (
                url.scheme
                or url.netloc
                or url.path not in (expected, f"/storage/v1{expected}")
                or not url.query
            ):
                raise StorageUnavailable
            prefix = self.origin if url.path.startswith("/storage/v1/") else self.base
            return f"{prefix}{url.path}?{url.query}"
        except (ValueError, KeyError, TypeError, AttributeError, ObjectExists):
            raise StorageUnavailable from None

    def delete(self, path: str):
        self.object_path(path)  # Validate before sending privileged requests.
        self._request(
            "DELETE",
            f"/object/{self.bucket}",
            data=json.dumps({"prefixes": [path]}).encode(),
        )


def get_storage(bucket: str | None = None, origin: str | None = None) -> Storage:
    settings = get_settings()
    key = settings.supabase_storage_key
    if not settings.supabase_url or not key or not key.get_secret_value().strip():
        raise HTTPException(503, "Evidence storage is not configured.")
    if key.get_secret_value().startswith("sb_publishable_"):
        raise HTTPException(503, "Evidence storage requires server-side credentials.")
    if origin is not None and origin != settings.supabase_url:
        raise HTTPException(503, "Storage project does not match this evidence record.")
    bucket = bucket or settings.evidence_bucket
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", bucket):
        raise HTTPException(503, "Evidence bucket configuration is invalid.")
    return Storage(settings.supabase_url, bucket, key.get_secret_value())
