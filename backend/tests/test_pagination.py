from datetime import timedelta
from uuid import uuid4

import pytest
from test_ledger import NOW, new_friend, new_loan, post
from test_ledger import api as api

from iou.config import Settings
from iou.ledger import pagination as cursors
from iou.ledger import service


@pytest.fixture
def configured(api, monkeypatch):
    settings = Settings(_env_file=None, cursor_signing_key="k" * 32)
    monkeypatch.setattr(cursors, "get_settings", lambda: settings)
    return api


def collect(client, path, first):
    rows = list(first["items"])
    token = first["next_cursor"]
    while token:
        response = client.get(path, params={"limit": 2, "cursor": token})
        assert response.status_code == 200, response.text
        page = response.json()
        rows.extend(page["items"])
        token = page["next_cursor"]
    return rows


def test_friend_cursors_handle_ties_and_ignore_newer_inserts(configured, monkeypatch):
    api = configured
    initial = {new_friend(api)["id"] for _ in range(5)}
    first = api.client.get("/friends?pagination=cursor&limit=2").json()
    assert first["next_cursor"] and first["has_more"]
    monkeypatch.setattr(service, "now_utc", lambda: NOW + timedelta(seconds=1))
    new_friend(api)
    rows = collect(api.client, "/friends", first)
    assert len(rows) == 5
    assert {r["id"] for r in rows} == initial


def test_loan_cursors_and_filter_binding(configured):
    api = configured
    friend = new_friend(api)
    for _ in range(5):
        new_loan(api, friend["id"])
    first = api.client.get("/loans?pagination=cursor&limit=2").json()
    assert len(collect(api.client, "/loans", first)) == 5
    token = first["next_cursor"]
    assert api.client.get("/loans", params={"cursor": token, "kind": "money"}).status_code == 422
    assert api.client.get("/friends", params={"cursor": token}).status_code == 422


def test_history_cursors_with_backdated_new_entries(configured, monkeypatch):
    api = configured
    friend = new_friend(api)
    loan = new_loan(api, friend["id"])
    for _ in range(4):
        post(
            api,
            f"/loans/{loan['id']}/repayments",
            {"amount_cents": 1, "effective_at": "2026-01-03T12:00:00Z"},
        )
    path = f"/friends/{friend['id']}/history"
    first = api.client.get(path, params={"pagination": "cursor", "limit": 2}).json()
    monkeypatch.setattr(service, "now_utc", lambda: NOW + timedelta(seconds=1))
    post(
        api,
        f"/loans/{loan['id']}/repayments",
        {"amount_cents": 1, "effective_at": "2026-01-02T12:00:00Z"},
    )
    entries = collect(api.client, path, first)
    assert len(entries) == 5
    assert len({r["id"] for r in entries}) == 5
    assert all(r["effective_at"] != "2026-01-02T12:00:00Z" for r in entries)


def test_tokens_are_owner_bound_and_expire(configured, monkeypatch):
    api = configured
    new_friend(api)
    new_friend(api)
    token = api.client.get("/friends?pagination=cursor&limit=1").json()["next_cursor"]
    original = api.user
    api.user = type(original)(uuid4(), None, "Other")
    assert api.client.get("/friends", params={"cursor": token}).status_code == 422
    api.user = original
    monkeypatch.setattr(service, "now_utc", lambda: NOW + timedelta(minutes=61))
    assert api.client.get("/friends", params={"cursor": token}).status_code == 422


@pytest.mark.parametrize("token", ["", "garbage", "a.b", "a.b.c", "☃.x"])
def test_invalid_tokens_are_validation_errors(configured, token):
    assert configured.client.get("/friends", params={"cursor": token}).status_code == 422


def test_tampered_token_and_offset_rejected(configured):
    api = configured
    new_friend(api)
    new_friend(api)
    token = api.client.get("/friends?pagination=cursor&limit=1").json()["next_cursor"]
    assert api.client.get("/friends", params={"cursor": token[:-1] + "!"}).status_code == 422
    assert api.client.get("/friends", params={"cursor": token, "offset": 1}).status_code == 422


def test_missing_key_fails_closed_but_legacy_paging_works(api, monkeypatch):
    monkeypatch.setattr(
        cursors, "get_settings", lambda: Settings(_env_file=None, cursor_signing_key=None)
    )
    new_friend(api)
    assert api.client.get("/friends?pagination=cursor").status_code == 503
    assert api.client.get("/friends").status_code == 200
