"""Signed keyset cursors bound to owner, endpoint, filters, and a one-hour window."""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import DateTime, Select, tuple_
from sqlalchemy.orm import Session

from iou.config import get_settings


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


@dataclass
class Results:
    rows: list
    has_more: bool
    next_cursor: str | None


def paginate(
    session: Session,
    query: Select,
    *,
    owner: UUID,
    scope: dict,
    limit: int,
    offset: int,
    mode: str,
    cursor: str | None,
    order: tuple,
    recorded,
    now: datetime,
) -> Results:
    use_cursor = mode == "cursor" or cursor is not None
    key = None
    watermark = now
    expiry = now + timedelta(hours=1)
    after = None
    scope_hash = hashlib.sha256(json.dumps(scope, sort_keys=True, default=str).encode()).hexdigest()
    if use_cursor:
        if offset:
            raise HTTPException(422, "Offset cannot be combined with cursor pagination.")
        secret = get_settings().cursor_signing_key
        if secret is None:
            raise HTTPException(503, "Cursor pagination is not configured.")
        key = secret.get_secret_value().encode()
        if cursor is not None:
            try:
                if len(cursor) > 4096:
                    raise ValueError
                encoded, signature = cursor.split(".")
                expected = b64(hmac.digest(key, encoded.encode(), "sha256"))
                if not hmac.compare_digest(signature, expected):
                    raise ValueError
                payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
                if (
                    payload["v"] != 1
                    or payload["owner"] != str(owner)
                    or payload["scope"] != scope_hash
                ):
                    raise ValueError
                watermark = datetime.fromisoformat(payload["watermark"])
                expiry = datetime.fromisoformat(payload["expiry"])
                if watermark.tzinfo is None or expiry.tzinfo is None or expiry <= now:
                    raise ValueError
                if len(payload["after"]) != len(order):
                    raise ValueError
                after = []
                for column, value in zip(order, payload["after"], strict=True):
                    if isinstance(column.type, DateTime):
                        parsed = datetime.fromisoformat(value)
                        if parsed.tzinfo is None:
                            raise ValueError
                        after.append(parsed.astimezone(UTC))
                    else:
                        after.append(UUID(value))
            except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
                raise HTTPException(
                    422, "Invalid, expired, or mismatched pagination cursor."
                ) from None
        query = query.where(recorded <= watermark)
        if after is not None:
            query = query.where(tuple_(*order) < tuple_(*after))
    rows = list(
        session.execute(
            query.order_by(*(column.desc() for column in order)).offset(offset).limit(limit + 1)
        ).all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if use_cursor and has_more:
        # SQLAlchemy Row mappings use the selected names of these order columns.
        last = rows[-1]._mapping
        values = []
        for column in order:
            value = last[column.key] if column.key in last else getattr(rows[-1][0], column.key)
            values.append(utc(value).isoformat() if isinstance(value, datetime) else str(value))
        payload = {
            "v": 1,
            "owner": str(owner),
            "scope": scope_hash,
            "watermark": watermark.isoformat(),
            "expiry": expiry.isoformat(),
            "after": values,
        }
        encoded = b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        next_cursor = f"{encoded}.{b64(hmac.digest(key, encoded.encode(), 'sha256'))}"
    return Results(rows, has_more, next_cursor)
