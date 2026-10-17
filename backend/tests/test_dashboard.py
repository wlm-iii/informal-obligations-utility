"""Dashboard definitions reconcile against ledger responses, not separate finance rules."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_ledger import NOW, new_friend, new_loan, post
from test_ledger import api as api

from iou.auth import Identity, get_current_user
from iou.profiles import Profile

ROUTES = ("summary", "obligations", "rankings", "trends")


def get(api, route="summary", **params):
    response = api.client.get(f"/dashboard/{route}", params=params)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def paid(api, loan, amount, **changes):
    result = post(api, f"/loans/{loan['id']}/repayments", {"amount_cents": amount, **changes})
    assert result.status_code == 201, result.text
    return result.json()["event"]


def test_empty_dashboard_is_read_only_without_provisioning_profile(api):
    for route in ROUTES:
        result = get(api, route)
        assert result["metrics_version"] == "iou-dashboard-v1"
        assert result["calculated_at"] == NOW.isoformat().replace("+00:00", "Z")
        assert result["timezone"] == "UTC" and result["currency"] == "USD"
    assert get(api)["metrics"]["outstanding"]["total_cents"] == 0
    assert get(api, "rankings")["items"] == []
    assert len(get(api, "trends")["items"]) == 30
    with Session(api.engine) as session:
        assert session.scalar(select(func.count()).select_from(Profile)) == 0


@pytest.mark.parametrize("route", ROUTES)
def test_dashboard_requires_auth(api, route):
    from iou.api import app

    del app.dependency_overrides[get_current_user]
    assert api.client.get(f"/dashboard/{route}").status_code == 401


def test_summary_separates_cash_waivers_principal_and_items(api):
    friend = new_friend(api)
    money = new_loan(
        api,
        friend["id"],
        principal_cents=10000,
        lent_at="2026-01-03T12:00:00Z",
        due_date="2026-01-09",
        interest_rate_bps=1000,
        interest_period="weekly",
        late_fee_cents=200,
    )
    paid(api, money, 700)  # 200 fee + 500 interest; no principal.
    assert (
        post(
            api,
            f"/loans/{money['id']}/waivers",
            {"component": "interest", "amount_cents": 500, "reason": "Friends"},
        ).status_code
        == 201
    )
    item = new_loan(api, friend["id"], "item", due_date="2026-01-09", late_fee_cents=300)
    assert post(api, f"/loans/{item['id']}/return").status_code == 201
    assert post(api, f"/loans/{item['id']}/fee-payments", {"amount_cents": 100}).status_code == 201
    state = get(api)["metrics"]
    assert state["loan_count"] == 2 and state["open_count"] == 2
    assert state["overdue_count"] == 1 and state["returned_items_unpaid_count"] == 1
    assert state["items_returned"] == 1 and state["items_outstanding"] == 0
    assert state["outstanding"] == dict(
        principal_cents=10000, interest_cents=0, fees_cents=200, total_cents=10200
    )
    assert state["cash_received"] == dict(
        principal_cents=0, interest_cents=500, fees_cents=300, total_cents=800
    )
    assert state["waived"]["total_cents"] == 500
    assert (
        state["principal_lent_cents"]
        + state["interest_accrued_cents"]
        + state["fees_assessed_cents"]
        - state["cash_received"]["total_cents"]
        - state["waived"]["total_cents"]
        == state["outstanding"]["total_cents"]
    )
    flows = get(api, "trends", start_date="2026-01-01")["totals"]
    assert flows["cash_received"] == state["cash_received"]
    assert flows["waived"] == state["waived"]
    assert flows["principal_lent_cents"] == state["principal_lent_cents"]
    assert flows["items_lent"] == flows["items_returned"] == 1


def test_obligation_buckets_boundaries_and_returned_fees(api):
    friend = new_friend(api)
    late = new_loan(api, friend["id"], due_date="2026-01-09", grace_days=2)
    today = new_loan(api, friend["id"], due_date="2026-01-10")
    week = new_loan(api, friend["id"], due_date="2026-01-17")
    new_loan(api, friend["id"], due_date="2026-01-18")
    returned = new_loan(api, friend["id"], "item", due_date="2026-01-09", late_fee_cents=200)
    assert post(api, f"/loans/{returned['id']}/return").status_code == 201
    assert [item["loan"]["id"] for item in get(api, "obligations")["items"]] == [late["id"]]
    upcoming = get(api, "obligations", group="upcoming")
    assert [item["loan"]["id"] for item in upcoming["items"]] == [today["id"], week["id"]]
    assert get(api, "obligations", group="upcoming", upcoming_days=0)["total"] == 1
    assert (
        get(api, "obligations", group="returned_unpaid")["items"][0]["loan"]["id"] == returned["id"]
    )
    page = get(api, "obligations", group="upcoming", limit=1, offset=1)
    assert page["total"] == 2 and page["items"][0]["loan"]["id"] == week["id"]
    assert get(api, "obligations", group="upcoming", offset=100)["items"] == []


def test_upcoming_uses_loan_timezone_not_current_profile(api, monkeypatch):
    from iou.ledger import service

    assert api.client.patch("/me", json={"timezone": "America/Los_Angeles"}).status_code == 200
    loan = new_loan(api, new_friend(api)["id"], due_date="2026-01-10")
    assert api.client.patch("/me", json={"timezone": "UTC"}).status_code == 200
    monkeypatch.setattr(
        service, "now_utc", lambda: NOW + timedelta(hours=13)
    )  # Jan 11 UTC, Jan 10 LA
    assert get(api, "obligations")["total"] == 0
    assert (
        get(api, "obligations", group="upcoming", upcoming_days=0)["items"][0]["loan"]["id"]
        == loan["id"]
    )


def test_archive_and_friend_filters_apply_consistently(api):
    first = new_friend(api)
    other = new_friend(api)
    new_loan(api, first["id"])
    new_loan(api, other["id"])
    assert api.client.post(f"/friends/{first['id']}/archive").status_code == 200
    assert get(api)["friend_count"] == 2
    assert get(api, archived="exclude")["metrics"]["loan_count"] == 1
    assert get(api, archived="only")["metrics"]["loan_count"] == 1
    assert get(api, "rankings", archived="only")["items"][0]["friend"]["archived"]
    assert (
        get(api, "obligations", group="upcoming", upcoming_days=90, archived="exclude")["total"]
        == 1
    )
    assert get(api, "trends", archived="only")["totals"]["principal_lent_cents"] == 5000
    assert get(api, friend_id=first["id"])["metrics"]["principal_lent_cents"] == 5000
    assert get(api, friend_id=first["id"], archived="exclude")["friend_count"] == 0


@pytest.mark.parametrize("route", ROUTES)
def test_owner_isolation_and_unknown_friend_not_found(api, route):
    friend = new_friend(api)
    new_loan(api, friend["id"])
    api.user = Identity(uuid4(), None, "Other")
    own = new_friend(api)
    new_loan(api, own["id"], principal_cents=100)
    result = get(api, route)
    assert friend["id"] not in str(result)
    assert (
        api.client.get(f"/dashboard/{route}", params={"friend_id": friend["id"]}).status_code == 404
    )
    assert (
        api.client.get(f"/dashboard/{route}", params={"friend_id": str(uuid4())}).status_code == 404
    )
    assert get(api)["metrics"]["principal_lent_cents"] == 100


def test_voids_reversals_and_corrections_restate_effective_time_trends(api):
    friend = new_friend(api)
    loan = new_loan(api, friend["id"])
    event = paid(api, loan, 1000, effective_at="2026-01-02T12:00:00Z")
    correction = post(
        api,
        f"/loans/{loan['id']}/events/{event['id']}/correct",
        {
            "reason": "Wrong amount/date",
            "replacement": {
                "action": "repayment",
                "amount_cents": 1500,
                "effective_at": "2026-01-03T12:00:00Z",
            },
        },
    )
    assert correction.status_code == 201, correction.text
    trends = get(api, "trends", start_date="2026-01-01")
    assert trends["items"][1]["cash_received"]["total_cents"] == 0
    assert trends["items"][2]["cash_received"]["total_cents"] == 1500
    assert get(api)["metrics"]["cash_received"]["total_cents"] == 1500
    replacement = correction.json()["replacement"]["id"]
    assert (
        post(
            api, f"/loans/{loan['id']}/events/{replacement}/reverse", {"reason": "Not paid"}
        ).status_code
        == 201
    )
    assert post(api, f"/loans/{loan['id']}/void", {"reason": "Mistake"}).status_code == 201
    assert get(api)["excluded_voided_count"] == 1
    assert get(api)["metrics"]["principal_lent_cents"] == 0
    assert get(api, "trends")["totals"]["principal_lent_cents"] == 0
    assert get(api, "rankings")["items"][0]["reliability"]["excluded_voided"] == 1


def test_rankings_use_existing_score_nulls_last_and_stable_ties(api):
    sufficient = new_friend(api, display_name="On time")
    other = new_friend(api, display_name="Insufficient")
    empty = new_friend(api, display_name="No history")
    for _ in range(3):
        loan = new_loan(api, sufficient["id"])
        paid(api, loan, 5000)
    new_loan(api, other["id"])
    ranking = get(api, "rankings")
    assert ranking["total"] == 3
    top = ranking["items"][0]
    assert top["friend"]["id"] == sufficient["id"] and top["rank"] == 1
    assert top["reliability"] == api.client.get(f"/friends/{sufficient['id']}/score").json()
    assert top["reliability"]["score"] == 675
    assert all(item["rank"] is None for item in ranking["items"][1:])
    assert [item["friend"]["id"] for item in ranking["items"][1:]] == sorted(
        [other["id"], empty["id"]]
    )
    assert get(api, "rankings", direction="asc")["items"][0]["friend"]["id"] == sufficient["id"]
    cash = get(api, "rankings", sort_by="outstanding", limit=1)
    assert cash["items"][0]["friend"]["id"] == other["id"]
    assert get(api, "rankings", offset=3)["items"] == []


def test_dense_trends_daily_weekly_monthly_and_inclusive_dates(api):
    loan = new_loan(api, new_friend(api)["id"])
    paid(api, loan, 1000, effective_at="2026-01-02T00:00:00Z")
    paid(api, loan, 2000, effective_at="2026-01-04T23:59:59Z")
    daily = get(api, "trends", start_date="2026-01-02", end_date="2026-01-04")
    assert len(daily["items"]) == 3
    assert daily["items"][1]["cash_received"]["total_cents"] == 0
    assert daily["totals"]["cash_received"]["total_cents"] == 3000
    assert daily["totals"]["principal_lent_cents"] == 0
    weekly = get(api, "trends", start_date="2026-01-01", bucket="week")
    assert [row["period_start"] for row in weekly["items"]] == ["2025-12-29", "2026-01-05"]
    assert weekly["items"][0]["principal_lent_cents"] == 5000
    monthly = get(api, "trends", start_date="2025-12-01", bucket="month")
    assert monthly["items"][0]["period_end"] == "2025-12-31"
    assert monthly["totals"]["cash_received"]["principal_cents"] == 3000
    assert get(api, "trends", end_date="2026-01-04")["start_date"] == "2025-12-06"


def test_trend_dates_use_profile_timezone_and_dst_calendar_days(api, monkeypatch):
    from iou.ledger import service

    loan = new_loan(api, new_friend(api)["id"])
    paid(api, loan, 1000, effective_at="2026-01-02T00:30:00Z")
    assert api.client.patch("/me", json={"timezone": "America/Los_Angeles"}).status_code == 200
    trend = get(api, "trends", start_date="2026-01-01", end_date="2026-01-01")
    assert trend["totals"]["cash_received"]["total_cents"] == 1000
    monkeypatch.setattr(service, "now_utc", lambda: NOW.replace(month=3, day=10))
    result = get(api, "trends", start_date="2026-03-07", end_date="2026-03-09")
    assert len(result["items"]) == 3


@pytest.mark.parametrize(
    "route,params",
    [
        ("summary", {"archived": "yes"}),
        ("summary", {"friend_id": "bad"}),
        ("summary", {"owner_id": str(uuid4())}),
        ("summary", {"start_date": "2026-01-01"}),
        ("obligations", {"limit": 0}),
        ("obligations", {"limit": 101}),
        ("obligations", {"offset": -1}),
        ("obligations", {"upcoming_days": 91}),
        ("obligations", {"group": "all"}),
        ("rankings", {"sort_by": "email"}),
        ("rankings", {"direction": "random"}),
        ("rankings", {"offset": 100001}),
        ("trends", {"start_date": "2026-01-11"}),
        ("trends", {"end_date": "2026-01-11"}),
        ("trends", {"start_date": "2024-01-01"}),
        ("trends", {"bucket": "year"}),
        ("trends", {"start_date": "0"}),
        ("trends", {"start_date": "20260101"}),
        ("trends", {"start_date": "0001-01-01"}),
        ("trends", {"start_date": "2026-02-30"}),
    ],
)
def test_invalid_filters_are_rejected(api, route, params):
    assert api.client.get(f"/dashboard/{route}", params=params).status_code == 422
