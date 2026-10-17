"""Supabase access-token verification. No passwords or provider secrets live here."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWKClientError

from iou.config import get_settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    id: UUID
    email: str | None
    display_name: str


@lru_cache(maxsize=8)
def get_jwks_client(url: str) -> PyJWKClient:
    # A bounded cache supports key rotation; no token-controlled URLs are used.
    return PyJWKClient(url, cache_jwk_set=True, lifespan=300, timeout=5)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="A valid sign-in is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Identity:
    if credentials is None or len(credentials.credentials) > 16384:
        raise unauthorized()
    settings = get_settings()
    if not settings.supabase_url:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    issuer = f"{settings.supabase_url}/auth/v1"
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in ("ES256", "RS256") or not isinstance(header.get("kid"), str):
            raise unauthorized()
        key = get_jwks_client(f"{issuer}/.well-known/jwks.json").get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["ES256", "RS256"],
            issuer=issuer,
            audience="authenticated",
            options={"require": ["exp", "iat", "iss", "aud", "sub", "role"]},
        )
        if claims["role"] != "authenticated":
            raise unauthorized()
        user_id = UUID(claims["sub"])
    except PyJWKClientConnectionError:
        raise HTTPException(
            status_code=503, detail="Sign-in verification is temporarily unavailable."
        ) from None
    except (jwt.InvalidTokenError, PyJWKClientError, ValueError, TypeError, KeyError):
        raise unauthorized() from None

    metadata = claims.get("user_metadata")
    name = metadata.get("full_name") or metadata.get("name") if isinstance(metadata, dict) else None
    name = name.strip() if isinstance(name, str) else ""
    email = claims.get("email")
    return Identity(
        id=user_id,
        email=email if isinstance(email, str) else None,
        display_name=name[:100] or "IOU user",
    )


CurrentUser = Annotated[Identity, Depends(get_current_user)]
