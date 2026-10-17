"""Real signature verification and owner isolation without contacting Supabase."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from iou import auth
from iou.api import app
from iou.config import Settings
from iou.database import Base, get_session
from iou.profiles import Profile

ISSUER = "https://test.supabase.co/auth/v1"


@pytest.fixture
def setup(monkeypatch):
    private_key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    owner = uuid4()
    claims = {
        "iss": ISSUER,
        "aud": "authenticated",
        "sub": str(owner),
        "role": "authenticated",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "email": "person@example.com",
        "user_metadata": {"full_name": "Test Person"},
    }
    settings = Settings(_env_file=None, supabase_url="https://test.supabase.co")
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key())
    )
    monkeypatch.setattr(auth, "get_jwks_client", lambda url: jwks)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"iou_app": None}},
    )
    Base.metadata.create_all(engine)

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            claims=claims,
            key=private_key,
            engine=engine,
            jwks=jwks,
            settings=settings,
            owner=owner,
        )
    app.dependency_overrides.clear()
    engine.dispose()


def headers(setup, **changes):
    token = jwt.encode(
        {**setup.claims, **changes}, setup.key, algorithm="ES256", headers={"kid": "test"}
    )
    return {"Authorization": f"Bearer {token}"}


def test_missing_token_and_wrong_scheme(setup):
    for h in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer garbage"}):
        response = setup.client.get("/me", headers=h)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"iat": datetime.now(UTC) + timedelta(hours=2)},
        {"nbf": datetime.now(UTC) + timedelta(hours=2)},
        {"iss": "https://other.supabase.co/auth/v1"},
        {"aud": "other"},
        {"role": "anon"},
        {"role": "service_role"},
        {"sub": "not-a-uuid"},
        {"sub": 42},
    ],
)
def test_invalid_claims_rejected(setup, changes):
    assert setup.client.get("/me", headers=headers(setup, **changes)).status_code == 401


@pytest.mark.parametrize("missing", ["exp", "iat", "iss", "aud", "sub", "role"])
def test_required_claims(setup, missing):
    claims = {k: v for k, v in setup.claims.items() if k != missing}
    token = jwt.encode(claims, setup.key, algorithm="ES256", headers={"kid": "test"})
    assert setup.client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_wrong_signature_and_symmetric_algorithm_rejected(setup):
    wrong = ec.generate_private_key(ec.SECP256R1())
    tokens = [
        jwt.encode(setup.claims, wrong, algorithm="ES256", headers={"kid": "test"}),
        jwt.encode(setup.claims, "x" * 64, algorithm="HS256", headers={"kid": "test"}),
        jwt.encode(setup.claims, setup.key, algorithm="ES256"),
    ]
    for token in tokens:
        assert (
            setup.client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
        )


def test_unconfigured_auth_fails_closed(setup, monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: Settings(_env_file=None, supabase_url=None))
    assert setup.client.get("/me", headers=headers(setup)).status_code == 503


def test_jwks_outage_is_service_unavailable(setup):
    def unavailable(token):
        raise jwt.PyJWKClientConnectionError("internal details")

    setup.jwks.get_signing_key_from_jwt = unavailable
    response = setup.client.get("/me", headers=headers(setup))
    assert response.status_code == 503
    assert "internal details" not in response.text


def test_unknown_signing_key_is_unauthorized(setup):
    def unknown(token):
        raise jwt.PyJWKClientError("unknown kid")

    setup.jwks.get_signing_key_from_jwt = unknown
    assert setup.client.get("/me", headers=headers(setup)).status_code == 401


def test_profile_is_created_once_and_updates_survive_signin(setup):
    h = headers(setup)
    first = setup.client.get("/me", headers=h)
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-store"
    assert first.json()["id"] == str(setup.owner)
    assert first.json()["display_name"] == "Test Person"
    assert first.json()["timezone"] == "UTC"
    response = setup.client.patch("/me", headers=h, json={"display_name": "  Updated  "})
    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated"
    assert response.json()["timezone"] == "UTC"
    later = setup.client.get("/me", headers=headers(setup, user_metadata={"full_name": "Old Name"}))
    assert later.json()["display_name"] == "Updated"
    assert later.json()["created_at"] == first.json()["created_at"]
    with Session(setup.engine) as session:
        assert session.scalar(select(func.count()).select_from(Profile)) == 1


def test_two_users_cannot_change_each_others_profiles(setup):
    alice = headers(setup)
    bob_id = uuid4()
    bob = headers(setup, sub=str(bob_id), email="bob@example.com")
    setup.client.get("/me", headers=alice)
    setup.client.patch("/me", headers=bob, json={"display_name": "Bob"})
    assert setup.client.get("/me", headers=alice).json()["display_name"] == "Test Person"
    assert setup.client.get("/me", headers=bob).json()["display_name"] == "Bob"
    assert setup.client.patch("/me", headers=bob, json={"id": str(setup.owner)}).status_code == 422
    assert setup.client.get(f"/profiles/{setup.owner}", headers=bob).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"display_name": ""},
        {"display_name": "   "},
        {"display_name": "a" * 101},
        {"display_name": None},
        {"timezone": None},
        {"timezone": "Not/AZone"},
        {"timezone": "../UTC"},
        {"email": "other@example.com"},
        {"owner_id": str(uuid4())},
    ],
)
def test_profile_validation(setup, body):
    assert setup.client.patch("/me", headers=headers(setup), json=body).status_code == 422


def test_verified_subject_owns_ledger_not_the_request_body(setup):
    alice = {**headers(setup), "Idempotency-Key": str(uuid4())}
    friend = setup.client.post("/friends", headers=alice, json={"display_name": "Alex"})
    assert friend.status_code == 201
    bob = headers(setup, sub=str(uuid4()), email="bob@example.com")
    assert setup.client.get(f"/friends/{friend.json()['id']}", headers=bob).status_code == 404
    assert setup.client.get("/friends", headers=bob).json()["items"] == []
    assert (
        setup.client.get("/friends", headers=alice).json()["items"][0]["id"] == friend.json()["id"]
    )


def test_timezone_update(setup):
    response = setup.client.patch(
        "/me", headers=headers(setup), json={"timezone": "America/Los_Angeles"}
    )
    assert response.status_code == 200
    assert response.json()["timezone"] == "America/Los_Angeles"
