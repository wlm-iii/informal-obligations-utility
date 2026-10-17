# IOU — rough product specification

**Informal Obligations Utility** · Draft v0.1 · Decisions below are provisional.

This primarily describes intended behavior. Google sign-in/private profiles and
the zero-charge backend ledger, audited corrections/voids, private proof workflows,
and signed cursors are implemented; see [auth setup](AUTH.md), [ledger contracts](LEDGER.md),
[Level 2 safety/setup](HISTORY_PROOF.md), and the [backend roadmap](BACKEND_ROADMAP.md).
Hosted provider setup/acceptance, interest, fees, scores, reminders, and frontend
lending screens remain future work.
The ledger contracts specify the narrower behavior that actually ships today.

## Product and audience

A private, playful ledger for people lending money and possessions to friends.
Record what was borrowed, remember what happened, and gently remind the forgetful.
**Your friends forget. We don’t.**

This is not a bank, debt collector, payment processor, or credit bureau. Amounts,
fees, and scores are personal bookkeeping and humor, not enforceable financial
advice or real credit assessments. Jokes must not become harassment.

## MVP user journeys

1. Add a friend with a display name and optional email.
2. Record money lent or an item borrowed, a lending date, due date, and optional terms.
3. See outstanding principal, accrued charges, and overdue status on a dashboard.
4. Record partial/full repayments, or an item's return; preserve the event history.
5. Open a friend's history and explainable fictional score.
6. Preview and explicitly send a playful reminder.
7. Enable scheduled reminders only after preferences and duplicate protection exist.

A borrower does not need an account in the MVP. An email address is optional unless
reminders are enabled. The lender manually records repayments/returns; no bank or
payment-provider integration is involved.

## Proposed screens

- Dashboard: open obligations, overdue filter, totals separated by money vs items.
- Friend list/detail: contact/preferences, current obligations, history, fake score.
- Loan create/detail: terms, charge breakdown, repayment/return actions, activity.
- Reminder preview/settings: tone, recipient, consent/opt-out status, delivery history.

Use friendly empty/error/loading states. Do not imply that estimated item values
are money actually owed, and do not mix original principal with fees in summaries.

## Provisional domain model

| Entity | Main fields / relationships |
|---|---|
| Owner | ID, login identity, timezone; owns every friend/obligation |
| Friend | ID, owner ID, display name, optional email, reminder preferences, archived time |
| Loan | ID, owner/friend IDs, kind, description, lent/due dates, terms snapshot, status |
| Money terms | Currency, original principal, annual simple rate, grace days, late fee/cap |
| Item terms | Item description, quantity, optional reference value, optional fixed late fee |
| Repayment | Loan ID, amount, effective timestamp, recorded timestamp, optional note |
| Activity | Owner/loan IDs, event type, effective/recorded timestamps, safe event details |
| Reminder delivery | Loan ID, scheduled date, idempotency key, status, provider ID, attempts |

IDs may be UUIDs. Enforce ownership with foreign keys and server-side queries; never
trust a client-supplied owner ID. Keep history private to the owner. Archive friends
with history rather than silently deleting related transactions. Domain migrations
arrive with their feature PRs; this document is not a committed database schema.

## Calculation contract — proposed MVP defaults

Agree on these before implementing calculators and UI independently.

- Single currency: USD initially. Store payments/principal in integer cents and
  rates in an exact decimal or integer basis-point representation. Never use float.
- Interest and fees default to **zero** and require explicit opt-in per loan.
- Money interest is **simple annual interest**, not compounding. It accrues from
  the lending date on outstanding principal, with an actual-days/365 denominator.
  Repayments split accrual into intervals; they do not retroactively reduce earlier interest.
- Lending/repayment events use the owner's calendar dates for accrual boundaries:
  start inclusive, end exclusive. A payment changes principal from its effective date;
  same-day events are ordered by effective timestamp, then stable event ID.
- Round the total calculated interest to cents using decimal half-up rounding,
  not each intermediate multiplication. Preserve sufficient internal precision.
- Payment allocation: fixed late fees first, accrued unpaid interest second,
  principal last. Never charge interest on interest or on fees.
- Overpayment is rejected for now. Settlement means principal and all agreed charges
  are cleared; no accrual occurs after settlement. Voiding also stops accrual and
  preserves an audit event rather than erasing history.
- A due date is inclusive through the end of that day in the owner's configured
  timezone. Overdue starts on the next calendar day. Grace defaults to zero days;
  with N grace days the fixed late fee is assessed on due date + N + 1.
- The fixed late fee is assessed **once**, not daily, and has a recorded applied event
  or equivalent idempotent derivation. No fee-on-fee or compounding.
- The terms snapshot includes an explicit maximum total charge amount (interest +
  late fees) when either is enabled. Exact UI limits/rate presets need team agreement.
- Item loans have no percentage interest. Optional fixed late fee follows the same
  overdue/grace rule. Returning the item closes the borrowing interval; unpaid fees
  remain visible separately until paid or waived.
- Snapshot rates, fees, caps, and timezone on the loan. Later preference changes must
  not silently rewrite historical obligations. Terms changes require an explicit event.
- Store timestamps in UTC and retain the timezone needed for calendar-date rules.
  Keep both effective time and recorded time for backdated events.

Example acceptance fixtures:

- $100 at 36.5% simple annual interest for 10 days = $1.00 interest.
- $100 at that rate for 5 days, followed by a payment of $50.50 allocating $0.50
  interest and $50 principal, then 5 more days = $0.25 new interest, $50 principal.
- A $5 fixed late fee assessed twice by retries still totals $5.
- A zero-rate loan returned/repaid on time has no charges and no overdue penalty.

Backdating, waivers, cancellations, and rounding edge cases need explicit tests.
Do not mutate historical repayment records without a correction/audit event.

## Fake credit scores

Clearly display **“Fictional IOU score — for fun, not a real credit score.”**

Proposed v1: range 300–850, base 600, +25 per on-time completed obligation,
−40 per late completed obligation, −20 per currently overdue obligation, clamped
to the range. Show “not enough history” until at least three obligations have been
completed. Exclude voided records; a late completion is not also counted as currently
overdue. Apply the loan's recorded grace period consistently.

Each score shows its version and a breakdown of the contributing counts/events.
Compute from recorded history; money amount, sensitive traits, email engagement,
and relationships outside this owner's ledger do not affect it. Friends are not
ranked publicly. The scoring rule is a product choice to revisit, not financial logic.

## Reminder behavior and delivery

- Start with preview/manual send; scheduled delivery is a later MVP slice.
- Development defaults to `EMAIL_MODE=disabled`, which sends nothing. Only that
  mode is supported by the foundation. A future preview/sink must not contact recipients.
- Explicitly confirm the recipient and have the lender confirm permission to contact.
- Use a small curated template set; no need for AI-generated messages initially.
- Friendly/example tone: “Your hoodie has filed a missing-person report.” Avoid threats,
  humiliation, public CC lists, or language suggesting actual legal/credit consequences.
- At most one reminder per friend per 24 hours across all loans; manual sends count
  toward the same limit. Apply quiet hours in the recipient timezone where known,
  otherwise the owner's timezone. Default proposed window: 09:00–18:00.
- Every real message includes a working opt-out. Opt-out disables future manual and
  automatic sends, not just one loan. Design signed, opaque unsubscribe tokens.
- Stop scheduling for settled/voided loans. Recheck status and preferences immediately
  before sending. Store minimal delivery metadata; avoid logging full email bodies.
- A scheduler periodically runs a one-shot command against PostgreSQL. Do not run
  timers in every API worker. Select eligible deliveries transactionally and record
  unique idempotency keys per friend/date; use provider idempotency where available.
- Use bounded retries for transient errors. Exactly-once external delivery is not
  guaranteed; provider acceptance and database failures require reconciliation.
- Serverless deployment needs an external scheduler; a web process alone is not one.

## Provisional full-product API outline

Browser URLs use `/api`; local FastAPI route paths omit that mount prefix.
This is a product sketch, not the shipped route list: see ledger/Level 2 contracts
for implemented routes. In particular, arbitrary loan PATCH is not supported.

```text
GET/POST        /api/friends
GET/PATCH       /api/friends/{id}
GET             /api/friends/{id}/history
GET             /api/friends/{id}/score
GET/POST        /api/loans
GET/PATCH       /api/loans/{id}
POST            /api/loans/{id}/repayments
POST            /api/loans/{id}/return
POST            /api/loans/{id}/void
GET             /api/loans/{id}/activity
POST            /api/loans/{id}/reminder-preview
POST            /api/loans/{id}/reminders
GET             /api/reminders
```

Define pagination, filters, error shape, and date/money serialization together before
implementation. Suggested boundary: integer cents, ISO-8601 timestamps with timezone,
explicit status enums. Mutating retries need idempotency keys where duplicate actions
would change balances or send messages. Use transactions for repayment/status/activity.
Keep charge/scoring functions pure and test them independently from HTTP/storage.

## Security, privacy, and deployment gate

A local fake-data demo can postpone login. **Do not expose a real-data or publicly
writable deployment without authentication and server-side owner isolation.**
Validate inputs, use parameterized ORM queries, escape email content, avoid public
borrower lookup, and never place secrets in browser bundles. Public deployment also
needs rate limits, appropriate session/CSRF protections, TLS, and a clear deletion/
retention policy. No actual payment processing or real credit reporting is planned.

## Delivery slices / proposed feature branches

1. `feat/friends`: friend API, owner boundary contract, list/detail UI.
2. `feat/loans`: money/item records, dashboard, migrations, validation.
3. `feat/repayments`: event history, returns, pure charge calculator and fixtures.
4. `feat/scores`: versioned fictional scoring with explanation UI.
5. `feat/reminders`: disabled/preview adapter, preferences, manual send safeguards.
6. `feat/scheduled-reminders`: durable command, scheduler integration, retry/idempotency tests.
7. Authentication and deployment hardening before any public real-data release.

These are slices, not a requirement to serialize all work; agree on contracts to
parallelize frontend/backend safely. Do not let both branches invent the same model.

## Open decisions

- Team confirmation of interest timing, allocations, charge caps, and score formula.
- Auth choice: Supabase Google sign-in is implemented; email/password UI is deferred.
  Hosted acceptance and the decision to expose anything beyond fake demo data remain open.
- Email provider, how permission is collected, and unsubscribe/reconciliation design.
- Hosting choice, managed PostgreSQL, scheduler, and migration release process.
- Handling item loss/damage, multiple items, waivers, and edited/backdated records.
- Accessibility polish and whether any feature should be cut for demo time.

## Stretch / non-goals

Item/proof photos now have a Level 2 backend workflow (hosted setup still required).
Stretch: template choices, charts, CSV export, mobile polish.
Not MVP: payment collection, bank links, actual credit reporting, debt collection,
public shame leaderboards, multi-currency conversion, compound interest, Redis/Celery,
or borrowers needing accounts just to receive a reminder.
