from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from iou.ledger.calculator import PERIOD_DAYS, Allocation, CalculationError, Entry, Terms, calculate

START = datetime(2026, 1, 1, tzinfo=UTC)


def terms(**changes):
    return replace(
        Terms(
            "money",
            10000,
            START,
            "UTC",
            START + timedelta(days=60),
            rate_bps=1000,
            period="weekly",
            cap=10000,
        ),
        **changes,
    )


def entry(day, amount, *, action="repayment", component=None, snapshot=None, id=1):
    return Entry(UUID(int=id), action, amount, START + timedelta(days=day), component, snapshot)


@pytest.mark.parametrize("period,days", list(PERIOD_DAYS.items()))
def test_rate_is_per_selected_period_not_annual(period, days):
    result = calculate(terms(period=period), [], START + timedelta(days=days))
    assert result.interest_accrued == 1000
    assert result.total == 11000


def test_monthly_is_thirty_days_and_partial_periods_are_prorated():
    result = calculate(terms(period="monthly"), [], START + timedelta(days=15))
    assert result.interest == 500


def test_interest_never_compounds_or_charges_on_fees():
    result = calculate(
        terms(late_fee=500, fee_at=START + timedelta(days=7)), [], START + timedelta(days=14)
    )
    assert result.interest_accrued == 2000 and result.fee_assessed == 500


def test_partial_payment_splits_interest_on_outstanding_principal():
    value = terms(rate_bps=3650, period="yearly")
    result = calculate(value, [entry(5, 5050)], START + timedelta(days=10))
    assert result.allocations[UUID(int=1)] == Allocation(5000, 50, 0)
    assert result.principal == 5000 and result.interest_accrued == 75
    assert result.interest == 25 and result.total == 5025


def test_fees_then_interest_then_principal():
    result = calculate(
        terms(late_fee=500, fee_at=START + timedelta(days=7)),
        [entry(7, 2000)],
        START + timedelta(days=7),
    )
    assert result.allocations[UUID(int=1)] == Allocation(500, 1000, 500)
    assert result.total == 9500


def test_cap_is_gross_lifetime_and_waivers_do_not_restore_headroom():
    value = terms(cap=1500, late_fee=1000, fee_at=START + timedelta(days=7))
    events = [
        entry(7, 500, action="waiver", component="fees"),
        entry(7, 1000, action="waiver", component="interest", id=2),
    ]
    result = calculate(value, events, START + timedelta(days=28))
    assert result.fee_assessed == 500 and result.interest_accrued == 1000
    assert result.fees == result.interest == 0
    assert result.total == 10000


def test_zero_cap_disables_all_charges():
    result = calculate(
        terms(cap=0, late_fee=500, fee_at=START + timedelta(days=1)), [], START + timedelta(days=30)
    )
    assert result.interest == result.fees == 0


def test_rounds_cumulative_interest_half_up_not_each_interval():
    value = terms(principal=1, rate_bps=5000, period="daily", cap=100)
    result = calculate(
        value, [entry(1, 1, action="waiver", component="interest")], START + timedelta(days=2)
    )
    assert result.interest_accrued == 1 and result.interest == 0


def test_recurring_fraction_intervals_land_exactly_on_half_cent():
    value = terms(principal=30, rate_bps=10000, period="quarterly")
    # 30/90 + 10/90 + 5/90 = exactly 0.5 cent, despite recurring fractions.
    result = calculate(value, [entry(1, 20), entry(2, 5, id=2)], START + timedelta(days=3))
    assert result.principal == 5 and result.interest_accrued == 1


def test_fee_is_assessed_once_at_boundary_not_before():
    value = terms(rate_bps=0, late_fee=500, fee_at=START + timedelta(days=10))
    before = calculate(value, [], value.fee_at - timedelta(microseconds=1))
    at = calculate(value, [], value.fee_at)
    much_later = calculate(value, [], value.fee_at + timedelta(days=100))
    assert before.fee_assessed == 0
    assert at.fee_assessed == much_later.fee_assessed == 500


def test_settlement_stops_future_interest_and_late_fee():
    result = calculate(terms(), [entry(7, 11000)], START + timedelta(days=90))
    assert result.completed_at == START + timedelta(days=7)
    assert result.interest_accrued == 1000 and result.total == 0


def test_item_return_is_separate_from_fee_settlement():
    value = terms(
        kind="item", principal=0, rate_bps=0, late_fee=500, fee_at=START + timedelta(days=5)
    )
    returned = calculate(value, [entry(6, None, action="return")], START + timedelta(days=10))
    assert returned.returned_at is not None and returned.completed_at is None
    assert returned.fees == 500
    settled = calculate(
        value,
        [entry(6, None, action="return"), entry(8, 500, action="fee_payment", id=2)],
        START + timedelta(days=10),
    )
    assert settled.total == 0 and settled.completed_at == START + timedelta(days=8)
    on_time = calculate(value, [entry(4, None, action="return")], START + timedelta(days=10))
    assert on_time.fee_assessed == 0


def test_same_time_events_use_stable_id():
    value = terms(rate_bps=0, late_fee=500, fee_at=START + timedelta(days=5))
    events = [entry(5, 300, id=2), entry(5, 300, id=1)]
    result = calculate(value, events, START + timedelta(days=5))
    assert result.allocations[UUID(int=1)] == Allocation(fees=300)
    assert result.allocations[UUID(int=2)] == Allocation(principal=100, fees=200)


def test_dst_counts_calendar_dates_not_elapsed_hours():
    start = datetime(2026, 3, 7, 8, tzinfo=UTC)
    value = terms(
        lent_at=start,
        fee_at=start + timedelta(days=60),
        timezone="America/Los_Angeles",
        rate_bps=100,
        period="daily",
    )
    result = calculate(value, [], datetime(2026, 3, 9, 7, tzinfo=UTC))
    assert result.interest_accrued == 200


@pytest.mark.parametrize(
    "event",
    [
        entry(1, 20000),
        entry(-1, 1),
        entry(1, 1, action="waiver", component="fees"),
        entry(1, 1, action="waiver", component="principal"),
        entry(1, None, action="return"),
        entry(1, 1, snapshot=Allocation(principal=1)),
    ],
)
def test_invalid_actions_overpayment_and_reallocation_rejected(event):
    with pytest.raises(CalculationError):
        calculate(terms(), [event], START + timedelta(days=2))


def test_future_events_do_not_change_current_balance():
    result = calculate(terms(rate_bps=0), [entry(10, 5000)], START + timedelta(days=2))
    assert result.principal == 10000
