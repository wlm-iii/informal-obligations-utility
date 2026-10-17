# Level 3 — optional periodic charges and fictional reliability

This is a **friends' bookkeeping app**, not a payment processor, bank, debt collector,
or real credit bureau. Repayments/returns are still recorded manually. No payment
SDK, account connection, transfer, or payment-provider integration is introduced.
There are no new API keys. Reminders/Gemini and dashboard charts remain later work.

## Simple loan creation

Existing fields stay the same. For money, optionally add a rate and its period;
for either money or items, optionally add a one-time late fee:

```json
{
  "friend_id": "FRIEND_UUID",
  "kind": "money",
  "description": "Lunch money",
  "principal_cents": 10000,
  "due_date": "2026-11-15",
  "interest_rate_bps": 500,
  "interest_period": "weekly",
  "late_fee_cents": 200
}
```

This means $100 lent, **5% per week**, and an optional $2 late fee—not 5% APR.
`interest_rate_bps` is an integer: 100 basis points = 1%; 500 = 5%; 125 = 1.25%.
Allowed rates are 0–10,000 basis points (0–100%) per selected period. Floats,
booleans, and numeric strings are rejected for rates and money amounts.

| Period | Calendar days used for proration |
|---|---:|
| `daily` | 1 |
| `weekly` (default) | 7 |
| `biweekly` | 14 |
| `monthly` | 30 |
| `quarterly` | 90 |
| `yearly` | 365 |

These are **fixed-day periods**, not variable calendar-month anniversaries. A 10%
monthly loan earns 5% after 15 calendar days. Weekly, monthly, and biweekly rates
are not converted to annual rates behind the scenes.

Both features are optional and independent: omitted/zero rate means no interest;
omitted/zero `late_fee_cents` means no late fee. An item loan accepts a late fee but
rejects interest fields. Items are still one item each, not estimated cash debts.

Optional advanced fields:
- `grace_days`: integer 0–365, default 0.
- `charge_cap_cents`: integer 0–1,000,000,000,000; normally omit it. When any charge
  is enabled, the default is `max(original principal, configured late fee)` for money,
  or the configured fee for items. With no enabled charges the default is zero.
  An explicit zero cap suppresses all charges. This limits **combined gross lifetime
  interest and fees**, not principal. Waivers/payments do not restore headroom.

Rates, period, fee, cap, grace, fee deadline, timezone, and rule version are immutable
loan snapshots. Changing profile settings never changes old terms. There is no
terms-edit endpoint; void/recreate for mistakes, following Level 2 restrictions.

## Interest, fees, rounding, and timing

For each interval on outstanding principal:

```text
interest cents = principal cents × rate_bps / 10000 × calendar days / period days
```

Interest begins on the lending date, including time before the due date. It is
simple interest: no compounding and no interest on interest/fees. Payments split
intervals and reduce principal from their effective date. Owner-local calendar days
use the loan's snapshotted timezone: start inclusive, end exclusive. A DST day still
counts as one calendar day, not 23/24 or 25/24 of a day.

Calculations use exact rational arithmetic, retain fractional cents between intervals, and
round cumulative earned interest using decimal **half-up**. A prior rounded payment
or waiver is accounted for when calculating what remains; segments are not rounded
independently and added. No float money math or background accrual job is used.

Due dates remain inclusive. `overdue_at` is the following midnight in the recorded
timezone. `fee_at` is midnight on due date + grace days + 1; the fee is considered
once at that boundary while the money loan remains unsettled or the item remains
unreturned. A return/settlement exactly at the boundary is late. Grace delays fee
eligibility and score penalties, **not** the basic overdue flag or interest start.

The cap is consumed chronologically by earned interest and the fee. At the fee
boundary, the configured fee is limited to remaining whole-cent headroom; already
earned interest is not retroactively removed. A configured $10 fee might therefore
be assessed as $5 if only $5 of cap remains. Future interest uses only remaining
headroom. Response fields distinguish configured fee from actual assessed/unpaid fee.
Once settled, money loans accrue no further charges. Returning an item prevents a
future late fee; an already assessed fee remains until paid or waived.

## Payments, waivers, and loan states

Existing `POST /loans/{id}/repayments` records money-loan payments. Allocation is:

1. Unpaid late fees.
2. Unpaid accrued interest.
3. Principal.

Added routes (browser paths have `/api` prefix):

| Method/path | Purpose |
|---|---|
| `POST /loans/{id}/fee-payments` | Record an item fee payment; same body as repayment |
| `POST /loans/{id}/waivers` | Forgive unpaid interest/fees with a reason |
| `GET /friends/{id}/score` | Private, explained fictional reliability |

These mutations require UUID `Idempotency-Key` headers and use the existing
owner-serialized, READ COMMITTED transactions. Recorded/effective timestamps and
atomic retry receipts work as before. No server-side action moves actual money.

Waiver example:

```json
{"component": "fees", "amount_cents": 200, "reason": "No worries this time"}
```

Components are `interest` or `fees`; principal write-offs are not supported.
Waivers need a nonempty reason (max 1,000 characters), and can optionally supply
`effective_at` and `note`. A waiver cannot exceed charges unpaid at that effective
time, pre-waive a future fee, or refund a payment. The gross cap is not reset.
Waivers appear in history as `waiver` events and can be reversed/corrected through
Level 2 endpoints. A replacement waiver includes its own reason. Replacement
`action` also now supports `fee_payment`. Voiding requires reversing **all** active
financial/return events, including waivers and item fee payments.

Payments cannot exceed the balance at their effective time. If a backdated payment
would overpay a later event or change its recorded allocation, the entire action
is rejected with 409. Inspect current GET state rather than blindly retrying with
a new idempotency key.

Money completes when principal and charges are cleared. Item borrowing completes
on return, while financial settlement may remain unpaid. Thus an item can have:

```text
borrowing_status = returned
settlement_status = unpaid
status = open
```

A returned item is not currently overdue simply because fees remain. Once its fees
are paid/waived it becomes `status=completed`. Borrowing and financial status are
reported separately; an unreturned fee-free item has zero cash owed but remains open.

## Breakdowns, ordering, and correction policy

Loan responses add:
- Rate, period/day count, grace, cap, rule version, calculation time, fee deadline.
- Accrued interest and actual assessed fee, plus remaining interest/fees.
- Cash paid and charges waived by component.
- `total_outstanding_cents` (principal + unpaid charges) and `charges_currency=USD`.
- Separate borrowing/settlement status.

For compatibility, `outstanding_cents` still means **remaining principal** for money
and null for items; `repaid_cents` is actual money-loan cash recorded, including paid
charges. Item principal/currency fields remain null; item charge amounts are USD.
Don't display an item's value as money owed or add waived amounts to cash received.

Each non-return event has immutable `principal_applied_cents`,
`interest_applied_cents`, and `fees_applied_cents`, summing to its amount. For a waiver
these identify the component forgiven, **not cash received**. History exposes the
same fields, reason, component, and `allocation_order`.

Financial processing order is effective timestamp, then stable per-loan
`allocation_order`, then UUID. The server assigns increasing orders under the owner
lock; a replacement inherits the original slot. This makes same-time recording and
correction predictable. History display still sorts by effective/recorded time/ID.

Original financial fields and allocations are never silently rewritten. Before a
new/backdated event, reversal, or correction commits, the calculator verifies all
remaining active recorded allocations. If any would change, the whole action rolls
back with 409. Reverse the affected later payments/waivers first, correct the earlier
entry, then explicitly re-enter them. Existing zero-charge out-of-order workflows
still work when allocations remain unchanged. Settlement projection updates happen
in the same transaction; query filtering uses that projection, never an arbitrary
client-set status.

GET calculations derive charges without writing fee/interest events. The one-time
fee is an idempotent derivation from snapshotted terms and the event timeline;
refreshes/retries cannot multiply it. There is no daily cron requirement or public
historical-as-of API. History embeds current balances, not a certified historical
statement. Signed cursor pagination retains its Level 2 live-data caveats.

## Fictional reliability v1

The private score endpoint returns its version, disclaimer, calculation time,
sufficiency, contributing counts, and point deltas:

```text
600 + 25 × on-time completions − 40 × late completions − 20 × currently overdue
```

Clamp to 300–850. Score is **null** with `sufficient_history=false` until at least
three obligations have completed. No meaningful credit score is implied for a new
contact. The disclaimer is always:

> Fictional IOU score — for fun, not a real credit score.

Money timeliness uses full settlement; item timeliness uses actual return time,
not when its remaining fees are settled. On-time means completion **before `fee_at`**
(the grace-adjusted boundary, even if fees are disabled). Only an obligation without
such completion can be currently overdue for scoring. Late completed obligations
are never also counted as currently overdue. Voided loans are excluded. Reversals
and corrections immediately affect classifications; sufficiency can fall below three.

Count obligations, not payments; money amounts, photos, sensitive traits, email
engagement, and other owners' records have no effect. Archived contacts keep private
history/scores. Scores are explainable product jokes, not actual credit reporting,
public rankings, payment verification, or an AI inference. Dashboard rankings/charts
and Gemini reminders are not implemented by this slice.

## Migration, compatibility, and release

Apply migrations through `0006_event_action_width`: it fixes PostgreSQL storage of
11-character `fee_payment` actions (the prior column allowed 10). The forward fix
preserves `0005`; rollback refuses to truncate longer action names, even reversed ones.

`0005_charges_scores` adds terms, settlement projection, per-event ordering, and
allocation columns/constraints. It does not add a payment provider, API secret, or
Supabase-managed schema change. **Existing loans remain version 0**, with zero
interest, late fees, cap, and grace. Existing repayments (including reversed ones)
are backfilled as principal-only; amounts/timestamps are unchanged. Existing settled
status is backfilled from active legacy events. New loans use calculation version 1,
even when their optional charges are zero.

Default zero-charge creation retries can replay pre-Level-3 receipts. Adding new
terms to an old key returns 409; no new loan is created. Other cached responses stay
original snapshots and may lack new fields—GET the resource for current state.

Review/back up the selected database, stop old financial writers, apply migrations,
and deploy/restart all API workers together. Old writers don't populate allocation
snapshots, and old readers don't understand charge payments/waivers. Do not mix
versions or roll back just code after Level 3 data exists. Downgrade refuses once
new-version loans or charge allocations exist. With only legacy records, rollback/
reapply preserves data; later failures should use a forward fix or reviewed restore.

Runtime roles additionally need **UPDATE(settled_at) on iou_app.loans**. Keep original
loan terms and event allocations immutable to that role; existing UPDATE(reversed_at)
on events is still needed. Do not grant browser-role access or expose `iou_app` in
the Data API. Auth, the terminal login page, and `/me` contracts are unchanged.

Offline tests cover period math, rounding, caps, fees, allocations, waivers,
corrections, scores, and ownership. Disposable PostgreSQL tests cover migrations,
legacy preservation, constraints, guarded downgrade, and concurrent payments/waivers
in both connection modes. `check` also runs the merged terminal login checks.
Hosted migration and real-data acceptance remain explicit release steps; don't run
integration tests against a shared/production Supabase database.
