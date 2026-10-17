# Level 4 — dashboard APIs

Backend-only, owner-private views of the existing ledger. No charts/UI, payment
processing, email, Gemini calls, new API keys, or scheduled jobs are introduced.
The terminal login and `/me` contracts are unchanged. Level 5 reminders remain next.

## Routes and shared scope

All routes require the existing bearer authentication and return `Cache-Control:
no-store`. Browser paths have `/api` before the paths below. OpenAPI lists full
response schemas. Every response includes `metrics_version=iou-dashboard-v1`,
`calculated_at` (one UTC instant per request), `timezone` (current profile timezone),
`currency=USD`, and the applied `friend_id`/`archived` filters.

| GET route | Purpose / additional query parameters |
|---|---|
| `/dashboard/summary` | Current balance/count overview |
| `/dashboard/obligations` | `group=overdue\|upcoming\|returned_unpaid`, `upcoming_days=7`, `limit=20`, `offset=0` |
| `/dashboard/rankings` | `sort_by=score\|outstanding`, `direction=desc\|asc`, `limit=20`, `offset=0` |
| `/dashboard/trends` | `start_date`, `end_date`, `bucket=day\|week\|month` |

Shared optional filters:
- `friend_id`: restrict to one owned contact; unknown or another owner's UUID gives
  404, not an empty success revealing whether that contact exists elsewhere.
- `archived=include|exclude|only`, default **include**. Archiving a contact should not
  silently hide their outstanding balance or historical cash. Filtering an owned
  archived contact with `exclude` returns an empty scope, not 404.

Invalid/unknown query parameters return 422. `limit` is 1–100 and `offset` 0–100,000.
Pages report `total`, `limit`, `offset`, and `items`. Pagination is live offset
pagination, not a historical snapshot or signed audit cursor. Re-fetch after edits;
concurrent changes between page requests can move entries.

An account without a profile/history gets a zero/empty dashboard with UTC defaults;
GET does not provision a profile. Rankings still include selected contacts with no
loans (zero balance, insufficient score history). Names and archive flags are exposed,
not contacts' email addresses or notes.

## Summary and per-friend metrics

Summary contains `friend_count`, `excluded_voided_count`, and `metrics`. Each ranking
entry has the same `metrics` definition for that friend. Voided obligations contribute
nothing to metrics, charts, or obligation lists. Their exclusion count remains visible
in summary and in the existing score breakdown.

| Metric | Definition |
|---|---|
| `loan_count` | Nonvoid obligations, completed or open |
| `money_loan_count`, `item_loan_count` | That count split by kind |
| `open_count`, `completed_count` | Full ledger status, including financial settlement |
| `overdue_count` | Current ledger borrowing-overdue flag; includes grace days |
| `items_outstanding`, `items_returned` | Nonvoid items split by actual return |
| `returned_items_unpaid_count` | Returned items with fees still owing |
| `principal_lent_cents` | Original money principal across all selected nonvoid loans |
| `interest_accrued_cents` | Gross interest earned under snapshotted Level 3 terms |
| `fees_assessed_cents` | Actual gross fees assessed, after caps; not configured fees |
| `outstanding` | Remaining principal, interest, fees, and their total |
| `cash_received` | Active recorded cash payments allocated to principal/interest/fees |
| `waived` | Active interest/fee forgiveness; principal component is always zero |

Each component object has `principal_cents`, `interest_cents`, `fees_cents`, and
`total_cents`. All are integer USD cents. Item values are **never estimated as money**;
item fees are included in fee components. Waivers are not cash received or principal
repayments. Cash received is manually recorded, not provider-verified.

Reconciliation across the same scope at the same instant:

```text
principal_lent_cents + interest_accrued_cents + fees_assessed_cents
  - cash_received.total_cents - waived.total_cents
  = outstanding.total_cents
```

These are **lifetime/current stocks**, not date-filtered loan cohorts. Summary and
rankings reject date filters; use trends for interval cash/lending activity. Gross
charges may exceed unpaid charges because some were paid or waived. Nothing here
reimplements accrual, reopens charge caps, or changes original allocations.

## Obligation groups

- `overdue`: existing `LoanRead.overdue`, sorted by overdue boundary then UUID,
  ascending. Due day is inclusive; grace delays fees/scoring penalties, not this flag.
- `upcoming`: borrowing is outstanding, not already overdue, with due date from today
  through today + `upcoming_days` inclusive. Today is calculated in **each loan's
  recorded timezone**, even if the profile timezone has since changed. Horizon is
  0–90 days; zero shows due-today obligations. Sorting uses overdue boundary then UUID.
- `returned_unpaid`: returned items still owing fees, with the same sorting. These
  items are neither currently borrowing-overdue nor upcoming, but their money is
  still included in outstanding totals. This extra group prevents them disappearing.

Items contain a minimal `friend` label and the complete existing `loan` response.
A fully paid/completed money loan never appears as upcoming or overdue. An unreturned
item with no fees has zero cash owed but remains an open borrowing obligation.

## Private rankings

The `reliability` object is exactly the existing fictional score v1 breakdown at the
request instant. It uses all selected loans for that friend, not a recent date window.
There is no second scoring formula, public leaderboard, or inferred real credit score.
Always retain its disclaimer in UI:

> Fictional IOU score — for fun, not a real credit score.

Default score ordering is descending; insufficient-history scores stay null and sort
last in **both** directions. For score sorting their `rank` is null, not a fake 600.
`sort_by=outstanding` orders total USD owed (including item fees, never item values).
All such entries receive a numeric position, including zero balances. Ties use friend
UUID ascending, with unique ordinal positions rather than shared competition ranks.
Ranks apply to the full filtered list before pagination, not just the current page.

Score timeliness respects grace: item return is completion even when fees remain;
money requires full settlement. Thus score completion counts need not equal the
financial `completed_count` in metrics. See [Level 3](CHARGES_SCORES.md).

## Trends: corrected effective-time flows

Dates are strict `YYYY-MM-DD`, inclusive, in the **current profile timezone**. End
is today by default; start defaults to 29 days before the selected end. A range must
span 1–366 calendar days; future end dates and dates before year 2 return 422.
Days are calendar days, including DST transitions, not fixed 24-hour durations.

Buckets are dense/zero-filled:
- `day`: one calendar date.
- `week`: Monday through Sunday.
- `month`: actual calendar month, **not** the 30-day interest-rate period.

`period_start`/`period_end` label natural bucket boundaries. First/last labels can
extend outside the requested range; only events within the requested inclusive range
are counted. Returned `start_date`/`end_date` identify that actual filter.

Each bucket and `totals` contain:
- `principal_lent_cents`: money principal at **lent_at**, not created/recorded time.
- `items_lent`: item obligations at lent_at.
- `items_returned`: active return events at effective time.
- `cash_received`: active repayment/item-fee-payment allocation components.
- `waived`: active waiver components, separate from cash.

Only events at or before `calculated_at` count. Reversed events are excluded;
replacement events count at their own effective time. Corrections/reversals restate
past buckets, **not** negative cash flows on their audit recording date. For audit
history use Level 2 timelines; these charts are not certified historical statements.
Changing profile timezone can rebucket chart dates without changing loan terms.

Totals equal the sum of all returned buckets. A window covering all active lending/
events reconciles to summary's principal lent, cash received, waived amounts, and
item lending/return counts. A short window generally does **not** equal lifetime
summary totals. Trends do not plot daily earned interest, hypothetical future charges,
net profit, or historical outstanding balances.

## Consistency, deployment, and acceptance

Dashboard reads take a shared lock on the existing owner profile, while ledger
mutations take its exclusive lock. This keeps profile, contact, loan, void, and event
reads consistent inside one response, without writing aggregates or blocking other
owners. Shared readers can coexist. The lock ends with the request transaction;
there is no external I/O under it. Separate endpoint requests are separate snapshots.
The existing runtime profile-update permissions cover PostgreSQL shared-row locking.
A new SELECT-only reporting role would need that locking permission too.

This implementation intentionally calculates from an owner's selected ledger in
memory with eager-loaded events, suitable for the friends-app scale. Output pagination
bounds response sizes, not total calculation work. It has no N+1 score queries or
silently truncated aggregates. Larger datasets should add measured, reconciled read
projections rather than approximate sums or new rules in the frontend.

The dashboard needs no schema additions or new credentials. This PR also fixes a
Level 3 PostgreSQL compatibility bug with migration **`0006_event_action_width`**:
`fee_payment` needs 11 characters, while the old action column allowed 10. Migration
widens it to 16 without editing previously shipped `0005`. Downgrade refuses while
any longer action exists, including reversed records; history is never truncated.
Run reviewed `alembic ... upgrade head` before enabling item fee payments. Existing
Level 3 setup/permissions still apply. Hosted Supabase is not changed by tests.

Tests cover reconciliation, ownership/auth, voids/corrections/reversals, fees/waivers,
archive scope, score parity/null ordering, paging, date validation, inclusive ranges,
calendar buckets, timezone/DST behavior, and unchanged login/build checks. Disposable
PostgreSQL tests additionally verify real item fee payments, migration rollback guards,
read-only results, and concurrent owner-lock behavior in both connection modes.

Release acceptance: apply reviewed migrations, use fake owned money/item examples,
compare dashboard totals with loan/history responses, test archive/date filters, and
verify another account sees none of those records. Dashboard UI and hosted acceptance
are separate steps; no email is sent by this level.
