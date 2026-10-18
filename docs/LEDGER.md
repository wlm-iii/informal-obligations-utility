# Level 1 — private friends and basic borrowing API

This page documents the baseline ledger. The current authenticated frontend also
has an additive `#tracker` view; see [tracker compatibility notes](DAILY_INTEREST_MERGE.md). [Level 2](HISTORY_PROOF.md) now extends it with corrections,
voids, proof images, and signed cursors. [Level 3](CHARGES_SCORES.md) adds optional
periodic charges, waivers, and fictional scores. [Level 5.0](REMINDERS.md) adds manually
approved email; tracker clipboard drafts do not invoke it. A shared social network
is not implemented.

## Setup and release

Use the [Level 0 auth setup](AUTH.md) and install updated locked dependencies with
`py -3.12 scripts/dev.py install` (`python3` on Unix). No new API keys are needed.

Migration **`0003_ledger`** adds `friends`, `loans`, `loan_events`, and
`mutation_receipts` in private schema `iou_app`. It preserves existing profiles and
Supabase-managed tables. Before running `scripts/dev.py migrate`, verify which DB
your root `.env` selects. Apply once through the release/setup process, not on startup.
A downgrade to `0002_profiles` **deletes all Level 1 records**, so it is not a safe
production undo once lending data exists. Back up before any destructive rollback.

All routes require the same Supabase bearer token as `/me`. Local backend paths
below omit `/api`; frontend calls use `/api/friends`, `/api/loans`, etc. Interactive
OpenAPI docs are at `http://127.0.0.1:8000/docs` after starting the backend.

Every operation derives the owner from the verified token. There is no writable
`owner_id`, public contact lookup, invitation, email delivery, or friend request.
Missing and other owners' records both return 404. Private responses are `no-store`.
First ledger creation automatically provisions a profile; calling `/me` first is
not required.

Current head `0008_repayment_preferences` adds optional `repayment_type` and
`repayment_other` metadata to creation/read responses. `other` requires details;
other choices reject details. These preferences never convert loan kind, waive
principal, alter rates, or change settlement actions. Existing loans default to null.
Apply the linear head, not the incoming PR's retired `0004_iou_preferences` fork.

## Contacts

| Method/path | Behavior |
|---|---|
| `POST /friends` | Create contact; requires idempotency header |
| `GET /friends` | Paginated contacts; `archived=exclude` (default), `only`, or `include` |
| `GET /friends/{id}` | Contact detail, including archived contacts |
| `PATCH /friends/{id}` | Update any subset of display name/email/notes |
| `POST /friends/{id}/archive` | Naturally idempotent; no body/header required |
| `GET /friends/{id}/history` | Paginated lending/repayment/return timeline |

Create example:

```json
{"display_name": "Alex", "email": "alex@example.com", "notes": "Likes hoodies"}
```

Names are trimmed, nonempty, at most 100 characters. Email is optional, validated,
and at most 320 characters; notes are optional and at most 2,000 characters. PATCH
can clear email/notes with null, but cannot clear the name. Duplicate names/emails
are allowed: these are owner-private contacts, not globally unique identities.
Archiving preserves all records and allows ongoing loans to be repaid/returned.
It blocks new lending. Archived contacts can still be edited. Restore/delete is not
part of Level 1.

## Lending

| Method/path | Behavior |
|---|---|
| `POST /loans` | Record money or one item lent; requires idempotency header |
| `GET /loans` | Paginated/filterable current loan state |
| `GET /loans/{id}` | Current loan state |
| `POST /loans/{id}/repayments` | Record money repayment; requires idempotency header |
| `POST /loans/{id}/return` | Record full item return; requires idempotency header |

Money example:

```json
{
  "friend_id": "FRIEND_UUID",
  "kind": "money",
  "description": "Lunch money",
  "principal_cents": 5000,
  "currency": "USD",
  "lent_at": "2026-01-01T12:00:00Z",
  "due_date": "2026-01-20",
  "notes": "Optional context"
}
```

Item example:

```json
{
  "friend_id": "FRIEND_UUID",
  "kind": "item",
  "description": "Blue hoodie",
  "due_date": "2026-01-20"
}
```

- Description is trimmed, nonempty, at most 500 characters; notes max 2,000.
- Currency is USD only (default USD for money). Amounts are **integer cents**,
  1–1,000,000,000,000 inclusive. Floats, numeric strings, and booleans are rejected.
- Item loans represent exactly one item and reject principal/interest/currency inputs. No
  reference valuations, quantities, loss/damage, or partial item returns yet.
- `lent_at` defaults to server time. Supplied timestamps require an explicit offset
  and are normalized to UTC. Future lending/settlement timestamps are rejected.
- Due date is required and cannot precede the lending date in the profile's timezone.
  The loan snapshots the timezone and the following midnight as `overdue_at` in UTC.
  The due date is inclusive; overdue starts at that boundary, including DST changes.
  Later profile timezone edits never rewrite an existing loan's boundary.
- No loan PATCH/DELETE exists. Use the explicit [Level 2 correction/void
  workflows](HISTORY_PROOF.md) rather than editing historical financial fields.
  Original loan terms still require void/recreate. Level 3 adds charge waivers.

## Repayments and item returns

Repayment example (partial or full):

```json
{"amount_cents": 2000, "effective_at": "2026-01-03T12:00:00Z", "note": "Paid back at lunch"}
```

Item return body is optional, or accepts:

```json
{"effective_at": "2026-01-05T12:00:00Z", "note": "Hoodie returned"}
```

`effective_at` defaults to server time and must be between lending time and now.
`recorded_at` always comes from the server; backdating does not change it. Notes
are max 2,000 characters. Unknown fields (including owner IDs, fees, or interest)
are rejected.

Settlement returns `{ "event": ..., "loan": ... }`. The event includes its ID,
loan ID, action, amount (null for returns), note, and effective/recorded timestamps.
Loan state includes principal/currency, repaid/outstanding cents, due date/timezone,
`overdue_at`, `status` (`open`/`completed`/`voided`), `overdue`, `returned_at`, and
`completed_at`. Item principal fields are null, not an estimated cash debt. Charges
default to zero; optional Level 3 terms introduce separate fee/interest/total fields.
An item return may leave charges unpaid; see its separate borrowing/settlement states.

Money balances derive from active (not reversed) repayment records, not editable balance fields. Full
repayment of principal and agreed charges completes the loan. Item return completes
the borrowing interval; any assessed fees must be paid/waived for financial completion. A new request that overpays, repeats an already completed loan, or applies the
wrong action to a loan kind returns 409 without recording an event.

## Retry and concurrency contract

**Required on every create/repayment/return:**

```http
Idempotency-Key: CLIENT_GENERATED_UUID
```

Generate one key per intended action (e.g. browser `crypto.randomUUID()`) and reuse
it on retries with the same endpoint and payload. Keys are owner-scoped across all
these endpoints, not merely per loan. Don't generate a fresh key to retry a payment
whose result is unknown.

- Success is 201, with `Idempotency-Replayed: false`.
- An identical retry is 201 with `Idempotency-Replayed: true`, returning the original
  response snapshot, not newly calculated current balances. Use GET for current state.
- Reusing a key with different input or another endpoint/loan returns 409.
- Failed operations leave no receipt or settlement; validation errors are 422.
- Equivalent validated input/defaults and timezone offsets normalize before hashing.
- Receipts currently do not expire. Any future retention policy must preserve safe
  financial retry behavior; receipt payloads may contain historical contact details.
- Contact PATCH sets fields directly; repeated archive returns the same archive time.
  These operations are naturally repeatable and do not use mutation receipts.

All ledger mutations use READ COMMITTED isolation and take a PostgreSQL row lock
on the owner's profile. Each balance/receipt read after acquiring the lock sees
the previous writer's commit. This
serializes an owner's writes across API workers, coordinating archive/lend races
as well as concurrent payments. Records and retry receipt commit atomically. There
is no external I/O while holding the lock. Independent owners do not share a lock.
This intentionally simple Level 1 design can later narrow locks if throughput
requires it; a process-local mutex or SQLite test alone is not sufficient evidence.

Composite foreign keys enforce loan/contact ownership and event/loan ownership and
kind. Check constraints reject invalid terms/amounts; a partial unique index permits
only one item return. Aggregate overpayment protection relies on the transactional
service, not arbitrary administrative SQL writes. All application lending writes
must go through this service.

## Listing and history

List/history envelope:

```json
{"items": [], "limit": 25, "offset": 0, "has_more": false, "next_cursor": null}
```

`limit` defaults to 25 (1–100); `offset` defaults to 0 (0–100,000). Lists sort by
creation time descending, then ID. Loan filters: `friend_id`, `kind=money|item`,
`status=open|completed|voided`, and `overdue=true|false`. Archived friends' existing loans
remain visible. A supplied foreign/missing friend filter returns 404.

History sorts by effective time descending, then recorded time and event ID. Entries
have action `lent`, `repayment`, or `return`; include amount/note/timestamps; and
embed **current** loan state. A lending entry uses the original loan ID and amount.
Backdated events appear in effective-time order. This is a basic ledger timeline,
extended by [Level 2's audit actions and cursor mode](HISTORY_PROOF.md). Offset
pagination remains available; concurrent inserts may shift offset pages.

## Security, testing, and launch limits

The migration revokes PUBLIC, `anon`, and `authenticated` access on each new table,
including when Supabase default privileges would otherwise grant access. Never
expose `iou_app` in the Data API. Use separate migration/runtime credentials for
production. A runtime role needs SELECT/INSERT on loans, events, and receipts,
and SELECT/INSERT/UPDATE on friends/profiles; not schema CREATE, record DELETE, or
UPDATE on immutable lending/event financial fields. Level 2 additionally needs
SELECT/INSERT on audit, SELECT/INSERT/UPDATE on evidence, and only UPDATE(reversed_at)
on settlement events; see its setup guide. SQLAlchemy does not inherit browser RLS.

`check` covers contract validation, both loan lifecycles, owner isolation, archival,
retry snapshots, rollback on failure, pagination, backdating, and timezone boundaries.
`test-db` additionally applies migrations and verifies drift, constraints/ACLs, and
real concurrent requests. **Use only a disposable DB**: integration tests insert and
clean up synthetic owners/ledger records. Do not run against production/shared data.

Before release, review/apply the migration and perform a real authenticated API
smoke test against the intended environment. Hosted migration, browser-based lending
UI, and production launch hardening are separate from these local automated results.
