# Backend roadmap

Proposed delivery levels agreed during planning. A level is complete only after
its acceptance checks pass; implementation alone does not verify hosted behavior.

Architecture: FastAPI owns domain rules and authorization; Supabase provides Auth,
PostgreSQL, and later private image storage; Vercel hosts the frontend. Backend
hosting and scheduler remain deployment decisions. Friends are private ledger
contacts, not necessarily registered users or a shared social graph.

## Level 0 — Accounts and private access

Implemented: Google sign-in via Supabase, PKCE/session/logout UI, backend JWT
verification, private profiles with names/timezones, migrations and ownership tests.
See [auth setup and acceptance checklist](AUTH.md). Hosted migration and real browser
Google login must be verified for each environment before marking this level complete.
Email/password UI is deferred; we do not manage passwords ourselves.

## Level 1 — Friends and basic borrowing

Implemented in the backend: friend create/edit/list/archive; optional email/notes;
money/item obligations with lent/due times and snapshotted timezone; partial/full
repayments, item returns, and per-friend history. Interest/fees remain zero. Basic
pagination, atomic writes, owner-row locking, and replay-safe idempotency were pulled
forward from Level 2 because settlement cannot safely ship without them. API and real
PostgreSQL tests cover the $50/hoodie lifecycle, owner isolation, and concurrency.
See [ledger API and acceptance notes](LEDGER.md). Hosted migration/acceptance and
frontend lending screens remain pending; the frontend currently has account UI only.

## Level 2 — Trustworthy history and proof

Implemented in the backend: append-preserving reversals/replacement corrections,
restricted loan voiding, expanded audit timelines, signed cursor pagination, and
private proof-image intents/validation/viewing/removal with durable orphan cleanup.
Financial timestamps and original records are preserved, and mutations remain
owner-serialized and replay-safe. PostgreSQL/fake-provider tests cover races and
failures. See [Level 2 contracts and deployment safety](HISTORY_PROOF.md).
Hosted migration, Storage bucket/server key/cursor-secret configuration, and real
provider acceptance remain release steps; frontend lending/evidence UI is separate.

## Level 3 — Charges and fictional reliability

Implemented in the backend: optional simple interest per daily/weekly/biweekly/
monthly/quarterly/yearly fixed-day period (not annual-only), optional one-time late
fees, automatic/optional caps, grace, immutable allocation breakdowns, and audited
charge waivers. Corrections reject changes to later allocations rather than silently
rewriting history. Item return and fee settlement are separate. Versioned fictional
scores explain counts/points and return null until enough history exists. Legacy
loans stay zero-charge. See [Level 3 contracts](CHARGES_SCORES.md); hosted migration
and frontend terms/score UI remain explicit release/product work.

## Level 4 — Dashboard APIs

Implemented in the backend: owner-private summaries, overdue/upcoming obligations,
returned items with unpaid fees, private friend rankings, and zero-filled lending/
repayment/waiver trends with calendar date filters. Principal, charges, actual cash,
and waivers are separate; items are counted, not valued as money. Metrics reuse the
ledger calculator and score rules and reconcile to their source events. Shared owner
locks keep each response consistent during financial writes. See [dashboard contracts](DASHBOARD.md).
Includes forward migration `0006_event_action_width` for Level 3's item fee-payment
PostgreSQL column-width bug. Dashboard UI and hosted acceptance remain separate.

## Level 5 — Manually approved reminders

Level 5.0 is implemented in the backend: fixed friendly/playful/direct-but-polite
template previews, explicit approval of recipient/message, central Gmail send-only
OAuth, recipient permission, global unsubscribe/cooldown, durable claims, delivery
history, stale-preview/final eligibility checks, and conservative uncertain outcomes.
Only currently owing contacts qualify; no arbitrary text or autonomous sending.
Default email mode is disabled and live recipients are restricted to the sender.
See [reminder setup and the live demo](REMINDERS.md). Hosted migration and full
hosted Gmail acceptance remain explicit release steps. Signed-in Tracker now
connects to this API for consent, immutable previews, explicit sending, and status/history;
public/offline demos remain copy-only. A single approved transport test was received,
but automated UI tests never send real email.

Level 5.1 will add optional minimal-context Gemini drafting behind the same approval
flow, with template fallback. No inbox reading or user-by-user Gmail authorization.

## Level 6 — Automation and operations

External scheduler, durable jobs, quiet hours, retries/reconciliation, stop conditions,
monitoring, retention/deletion workflows, backup restoration and performance tuning.
Done when repeat job runs cannot duplicate reminders and failures are recoverable.

For a short demo prioritize Levels 0–2, then a simple score/dashboard. Template-based
manual reminders may precede advanced charges/charts if they are the main demo hook.
Production safety work is a launch gate, not something to postpone until Level 6.

Deferred: actual payments, banking, public rankings, shared friend networks, compound
interest, and autonomous AI messages. All credit scores are fictional and private.
