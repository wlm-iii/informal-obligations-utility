# IOU — rough product specification

**Informal Obligations Utility** · Draft v0.1 · Decisions below are provisional.

This primarily describes intended behavior. Google sign-in/private profiles and
the zero-charge backend ledger, audited corrections/voids, private proof workflows,
signed cursors, periodic charges, waivers, and fictional scores are implemented;
see [auth setup](AUTH.md), [ledger contracts](LEDGER.md), [Level 3](CHARGES_SCORES.md),
[Level 2 safety/setup](HISTORY_PROOF.md), and the [backend roadmap](BACKEND_ROADMAP.md).
Hosted provider setup/acceptance, reminders, and frontend lending/score screens
remain separate work.
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
| Money terms | Currency, original principal, simple rate/period, grace days, late fee/cap |
| Item terms | Item description, quantity, optional reference value, optional fixed late fee |
| Repayment | Loan ID, amount, effective timestamp, recorded timestamp, optional note |
| Activity | Owner/loan IDs, event type, effective/recorded timestamps, safe event details |
| Reminder delivery | Loan ID, scheduled date, idempotency key, status, provider ID, attempts |

IDs may be UUIDs. Enforce ownership with foreign keys and server-side queries; never
trust a client-supplied owner ID. Keep history private to the owner. Archive friends
with history rather than silently deleting related transactions. Domain migrations
arrive with their feature PRs; this document is not a committed database schema.

## Calculation contract — implemented Level 3

The user-facing choice is an optional rate **per selected term**, plus an independently
optional one-time late fee. The earlier annual-only proposal is superseded by
[the complete implemented contract](CHARGES_SCORES.md).

- USD integer cents and integer rate basis points; no float money math.
- Daily/weekly/biweekly/monthly/quarterly/yearly fixed periods of 1/7/14/30/90/365
  calendar days. Rates are not silently annualized. Zero/omitted rates and fees are off.
- Simple, prorated interest on remaining principal from lending; no compounding or
  interest on charges. Calendar boundaries use the snapshotted timezone, not elapsed hours.
- Round cumulative interest half-up while retaining fractional cents across intervals.
- Fees first, interest second, principal last; reject overpayment at effective time.
- Inclusive due date, next-day overdue flag, optional grace before a one-time fee.
  Interest continues during grace. Fee eligibility is derived without a cron job.
- Default combined gross-charge cap is automatic when charges are enabled; optional
  overrides are supported. Paid/waived charges don't restore lifetime cap headroom.
- Item loans have no percentage interest. Return and payment/waiver of item fees are
  separate states. Charge waivers never forgive principal or represent cash received.
- Terms, rule version, timezone, and original allocation snapshots are immutable.
  Existing loans remain version 0 and zero-charge. New loans use calculation version 1.
- Effective timestamp, per-loan allocation order, then UUID determine financial order;
  corrections retain the original slot. Reject changes that would rewrite later allocations.
- Effective/recorded times, reasons, reversals, and replacement links preserve history.
  Settlement/voiding stop further charges. No real payment integration is planned.

Examples: $100 at 10% weekly earns $10 after seven days; 10% monthly earns $5 after
15 days. A $5 late fee remains $5 across refreshes/retries. Existing zero-charge
repayments remain principal-only after migration.

## Fake credit scores

Clearly display **“Fictional IOU score — for fun, not a real credit score.”**

Implemented v1: range 300–850, base 600, +25 per on-time completed obligation,
−40 per late completed obligation, −20 per currently overdue obligation, clamped
to the range. Return null / “not enough history” until at least three obligations have
completed. Exclude voided records; a late completion is not also counted as currently
overdue. Apply the recorded grace boundary. Item timeliness uses return time even
when fees remain unpaid; money timeliness uses full settlement time.

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

- Charge/score rules are now implemented and versioned; future changes must preserve
  existing loan terms/allocations and require explicit versioning.
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
