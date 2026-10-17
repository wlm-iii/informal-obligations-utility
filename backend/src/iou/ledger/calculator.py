"""Pure, deterministic periodic simple interest and payment allocation (rule v1).

Periods are fixed calendar-day lengths, not APRs: monthly=30, biweekly=14.
No floats, daily job, compounding, or external payment processor is involved.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from fractions import Fraction
from uuid import UUID
from zoneinfo import ZoneInfo

PERIOD_DAYS = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "quarterly": 90,
    "yearly": 365,
}


class CalculationError(ValueError):
    pass


@dataclass(frozen=True)
class Allocation:
    principal: int = 0
    interest: int = 0
    fees: int = 0


@dataclass(frozen=True)
class Terms:
    kind: str
    principal: int
    lent_at: datetime
    timezone: str
    fee_at: datetime
    rate_bps: int = 0
    period: str = "weekly"
    late_fee: int = 0
    cap: int = 0


@dataclass(frozen=True)
class Entry:
    id: UUID
    action: str
    amount: int | None
    effective_at: datetime
    component: str | None = None
    allocation: Allocation | None = None
    order: int = 0


@dataclass
class Balance:
    principal: int
    interest_accrued: int = 0
    fee_assessed: int = 0
    interest_paid: int = 0
    fees_paid: int = 0
    principal_paid: int = 0
    interest_waived: int = 0
    fees_waived: int = 0
    returned_at: datetime | None = None
    completed_at: datetime | None = None
    fee_assessed_at: datetime | None = None
    allocations: dict[UUID, Allocation] = field(default_factory=dict)

    @property
    def interest(self):
        return self.interest_accrued - self.interest_paid - self.interest_waived

    @property
    def fees(self):
        return self.fee_assessed - self.fees_paid - self.fees_waived

    @property
    def total(self):
        return self.principal + self.interest + self.fees


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def calculate(terms: Terms, entries: list[Entry], at: datetime, *, verify=True) -> Balance:
    return _calculate(terms, entries, utc(at), verify)


def _calculate(terms: Terms, entries: list[Entry], at: datetime, verify: bool) -> Balance:
    zone = ZoneInfo(terms.timezone)
    result = Balance(terms.principal)
    raw_interest = Fraction(0)
    cursor = utc(terms.lent_at)
    fee_at = utc(terms.fee_at)
    fee_considered = False

    def accrue(end):
        nonlocal cursor, raw_interest
        if end < cursor:
            raise CalculationError("Effective time cannot precede lending time.")
        days = (end.astimezone(zone).date() - cursor.astimezone(zone).date()).days
        if terms.kind == "money" and result.completed_at is None and days > 0:
            earned = Fraction(
                result.principal * terms.rate_bps * days, 10000 * PERIOD_DAYS[terms.period]
            )
            headroom = max(Fraction(0), Fraction(terms.cap - result.fee_assessed) - raw_interest)
            raw_interest += min(earned, headroom)
            # Exact half-up rounding, even when recurring fractions land on a half cent.
            n, d = raw_interest.numerator, raw_interest.denominator
            result.interest_accrued = (2 * n + d) // (2 * d)
        cursor = end

    def advance(end):
        nonlocal fee_considered
        if not fee_considered and fee_at <= end:
            accrue(fee_at)
            borrowing = (
                result.completed_at is None if terms.kind == "money" else result.returned_at is None
            )
            if borrowing and terms.late_fee:
                available = max(Fraction(0), Fraction(terms.cap) - raw_interest)
                result.fee_assessed = min(terms.late_fee, int(available))
                result.fee_assessed_at = fee_at
            fee_considered = True
        accrue(end)

    for entry in sorted(entries, key=lambda e: (utc(e.effective_at), e.order, e.id)):
        effective = utc(entry.effective_at)
        if effective > at:
            continue
        if (entry.action == "repayment" and terms.kind != "money") or (
            entry.action in ("return", "fee_payment") and terms.kind != "item"
        ):
            raise CalculationError("Action is not valid for this loan kind.")
        if entry.action == "waiver" and entry.component not in ("interest", "fees"):
            raise CalculationError("Only interest and fees may be waived.")
        advance(effective)
        amount = entry.amount or 0
        allocation = Allocation()
        if entry.action in ("repayment", "fee_payment"):
            if result.completed_at is not None or amount <= 0 or amount > result.total:
                raise CalculationError("Payment exceeds the balance at its effective time.")
            fees = min(amount, result.fees)
            interest = min(amount - fees, result.interest)
            principal = amount - fees - interest
            if principal > result.principal:
                raise CalculationError("Payment exceeds outstanding principal.")
            allocation = Allocation(principal, interest, fees)
            result.fees_paid += fees
            result.interest_paid += interest
            result.principal_paid += principal
            result.principal -= principal
        elif entry.action == "waiver":
            available = result.interest if entry.component == "interest" else result.fees
            if amount <= 0 or amount > available:
                raise CalculationError("Waiver exceeds unpaid charges at its effective time.")
            if entry.component == "interest":
                result.interest_waived += amount
                allocation = Allocation(interest=amount)
            else:
                result.fees_waived += amount
                allocation = Allocation(fees=amount)
        elif entry.action == "return":
            if result.returned_at is not None:
                raise CalculationError("Item already has an active return.")
            result.returned_at = effective
        else:
            raise CalculationError("Unsupported financial event.")
        if entry.action != "return":
            result.allocations[entry.id] = allocation
            if verify and entry.allocation is not None and allocation != entry.allocation:
                raise CalculationError(
                    "This changes an existing allocation; reverse affected later events first."
                )
        complete = result.total == 0 and (terms.kind == "money" or result.returned_at is not None)
        if complete:
            result.completed_at = effective
    advance(at)
    return result
