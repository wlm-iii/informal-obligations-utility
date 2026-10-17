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

Opt-in simple interest, one-time fees, grace periods/caps, deterministic allocation,
rounding/backdating/waivers, and clear charge breakdowns. Versioned fictional score
with explanations and insufficient-history state. Confirm the provisional formulas
in [SPEC.md](SPEC.md) first. Done when balances/scores reconcile to tested events.

## Level 4 — Dashboard APIs

Principal/charges separated; overdue/upcoming obligations; private friend rankings;
repayment/lending trends and date filters. Item counts are not cash owed. Done when
all chart/ranking metrics have documented definitions and reconcile with the ledger.

## Level 5 — Manually approved reminders

Editable template previews, email-provider integration, permission confirmation,
unsubscribe, shared rate limits, delivery records, duplicate protection and final
status rechecks. Gemini drafting is optional, minimal-context, preview-only, with a
template fallback. No autonomous sending or Gmail access required. Done when opted-out
contacts and duplicate sends are blocked and every send requires explicit approval.

## Level 6 — Automation and operations

External scheduler, durable jobs, quiet hours, retries/reconciliation, stop conditions,
monitoring, retention/deletion workflows, backup restoration and performance tuning.
Done when repeat job runs cannot duplicate reminders and failures are recoverable.

For a short demo prioritize Levels 0–2, then a simple score/dashboard. Template-based
manual reminders may precede advanced charges/charts if they are the main demo hook.
Production safety work is a launch gate, not something to postpone until Level 6.

Deferred: actual payments, banking, public rankings, shared friend networks, compound
interest, and autonomous AI messages. All credit scores are fictional and private.
