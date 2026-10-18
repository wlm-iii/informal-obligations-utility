# Level 2 — corrections, audit history, private proof, and cursors

Backend-only implementation. The frontend still contains account/profile UI, not
lending/evidence screens. [Level 3](CHARGES_SCORES.md) now adds optional periodic
charges, waivers, and fictional scores; reminders and AI remain later work.
See [Level 1](LEDGER.md) for the base contracts and bearer/idempotency conventions.

## Migration and deployment safety

`0004_history_proof` adds `ledger_audit` and `evidence`, nullable reversal/replacement
metadata on settlement events, composite ownership keys, and a one-**active**-item-
return index. Existing profiles, loans, repayments, returns, and receipts are retained.
Supabase-managed Auth/Storage schemas and buckets are not modified by this migration.
PUBLIC/anon/authenticated access to the new private tables is revoked.

Review the target `DATABASE_URL`, back up shared data, stop old API writers, run
`py -3.12 scripts/dev.py migrate` (or `python3` on Unix), and deploy/restart **all**
workers before enabling corrections. Do not mix Level 1 and Level 2 writers once
reversals exist: old code counts reversed payments. A code-only rollback is unsafe.
The migration downgrade refuses to erase any Level 2 audit, evidence, or reversal
records. Empty Level 2 metadata can be downgraded/reapplied without losing Level 1
records. After real Level 2 use, prefer a forward fix or a reviewed backup restore.

No Supabase migration, bucket creation, or live Storage acceptance test happens
implicitly when installing dependencies or starting the server.

## Correction workflows

All paths below are direct FastAPI paths; browser requests use `/api`. All require
an authenticated owner. Mutating financial/audit operations require a UUID
`Idempotency-Key`, with the same atomic receipts/replay behavior as Level 1.

| Method/path | Behavior |
|---|---|
| `GET /loans/{loan}/events/{event}` | Read an original/replacement settlement, including reversal/link metadata |
| `POST /loans/{loan}/events/{event}/reverse` | Cancel one active repayment/return, preserving the source |
| `POST /loans/{loan}/events/{event}/correct` | Atomically reverse and replace one active settlement |
| `POST /loans/{loan}/void` | Void an incorrectly created loan, preserving the record |

A reversal or void requires `{ "reason": "Entered in error" }`; reasons are trimmed,
nonempty, at most 1,000 characters. Actor, ownership, and recorded time are server-
controlled. There is no reversal of an audit record or silent deletion of history.

Correction example:

```json
{
  "reason": "Repayment was ten dollars, not twenty",
  "replacement": {
    "action": "repayment",
    "amount_cents": 1000,
    "effective_at": "2026-01-03T12:00:00Z",
    "note": "Corrected entry"
  }
}
```

For an item return use `"replacement": { "action": "return", "effective_at": "..." }`.
Replacement action must match the original kind. If effective time is omitted/null,
it defaults to the original event's effective time, **not now**. Replacement note
defaults to null; the original note is still preserved on the original event.
All other settlement validation (positive integer cents, USD, date bounds) applies.

Original amount/note/effective/recorded fields never change. Level 3 additionally
preserves payment allocation snapshots and may reject corrections that change a
later allocation; reverse those dependent events first. `reversed_at` is a
mutable projection updated in the **same transaction** as the append-only reversal
audit. The replacement is a new settlement with `replaces_event_id`; the audit links
both event IDs. An active replacement can itself be corrected, forming an explicit
chain. Already reversed events return 409 with a new key; an identical retry with
the original key replays the original 201 snapshot.

Balances and completion times use only active (not reversed) settlements. Reversing
a full repayment or return reopens the loan. Later repayments are never silently
changed: if a replacement would make their combined total exceed principal, the
whole correction returns 409, restoring the original event and leaving no audit,
replacement, or receipt. Correct the later entries explicitly before retrying.

Voiding requires **no active repayments or returns**; reverse those explicitly first.
A voided money loan retains its original principal but has zero outstanding debt;
it is not reported as repaid. Status is `voided`, overdue is false, and the reason
and timestamp remain visible. New settlement/correction attempts are blocked.
Original principal, borrower, item identity, and due terms are still not editable:
void/recreate for those mistakes. Voids do not imply that money actually changed hands.
Future scores/dashboard totals must exclude voided loans and reversed settlements.

## Timeline and audit semantics

Friend history now includes `lent`, `repayment`, `return`, `reversal`, `void`,
`evidence_added`, and `evidence_removed`. Entries retain effective/recorded times and
embed **current** loan state. Original settlements expose `reversed_at` and
`replaces_event_id`; audit entries expose reason/target/replacement/evidence IDs
and actor (`owner`, or `system` for cleanup).

A reversal's effective time matches the cancelled event; recorded time is when the
correction happened. In the timeline its amount is the negative original repayment
(or null for item returns). Voids and evidence actions use the actual action time.
This is application audit history, **not** a tamper-proof journal, real credit record,
or proof that a borrower actually paid. Privileged administrators can still change
DB data outside the supported API and must not bypass these services.

## Private evidence setup (optional feature)

Financial corrections work without a storage key. Image endpoints fail closed
with 503 until storage is configured. Install the updated dependency lock (includes
Pillow) with `scripts/dev.py install`.

1. In Supabase Storage create a bucket named **`iou-evidence`**, **private**, allowing
   only `image/jpeg` and `image/png`, with a maximum file size of **5 MiB / 5,242,880 bytes**.
2. Do not add browser read/insert/update/delete policies for this bucket. Review
   existing broad `storage.objects` policies too: private buckets are not a substitute
   for correct RLS. All file operations go through our backend so validation cannot
   be bypassed. The migration does not alter Storage policies automatically.
3. Add a **server-only** secret API key (or legacy service_role key) to the root `.env`:

   ```dotenv
   SUPABASE_STORAGE_KEY=YOUR_SERVER_ONLY_STORAGE_KEY
   EVIDENCE_BUCKET=iou-evidence
   EVIDENCE_SIGNED_URL_SECONDS=60
   ```

   Never put this privileged key in frontend/VITE variables, Git, request logs, or
   chat. Google client secrets and frontend publishable keys are not storage keys.
   It grants elevated access; protect and rotate it accordingly. New `sb_secret_*`
   keys are sent only as `apikey`; legacy JWT keys also use Bearer authorization.
4. Keep the project's existing `SUPABASE_URL`. Bucket and project origin are stored
   per intent so changing `EVIDENCE_BUCKET` does not orphan existing files. Operations
   on old records still target their original bucket. If the configured project
   changes, the adapter refuses to send credentials to the old origin; migrate the
   objects/metadata explicitly or restore the matching configuration.
5. Restart the backend and verify the bucket is private. Upload/view operations
   check the bucket metadata and refuse public/unknown buckets.

### Upload, view, remove

| Method/path | Behavior |
|---|---|
| `POST /loans/{loan}/evidence` | Create a 24-hour pending upload intent; idempotency key required |
| `PUT /evidence/{id}/content` | Upload raw image bytes, not multipart; naturally retry-safe |
| `GET /loans/{loan}/evidence` | Paginated metadata, optional state filter |
| `GET /evidence/{id}` | Current metadata/status; never returns an object path or secret |
| `POST /evidence/{id}/view-url` | Issue a short-lived viewing URL only for ready, owner-owned evidence |
| `POST /evidence/{id}/remove` | Logically remove with a reason/idempotency key; queue binary cleanup |

Create an intent with:

```json
{"filename": "repayment.png", "content_type": "image/png", "event_id": "OPTIONAL_SETTLEMENT_UUID", "note": "Receipt"}
```

Omit `event_id` for evidence of the original lending. A supplied event must belong
to this owner/loan; reversed events and voided loans can retain supporting evidence.
Filename is a bounded display label only (path components/control characters are
rejected/stripped); the backend generates the actual immutable object key.

PUT the image body with `Content-Type` matching the intent, using the normal bearer
token. Input and normalized output are each limited to 5 MiB. Chunked uploads are
also bounded before buffering beyond the limit. Only static PNG/JPEG is accepted:
actual decode/verification, matching MIME, at most 16 megapixels/8,000 pixels per
side, no SVG/GIF/APNG. Corrupt and truncated images are rejected before storage.

Images are orientation-corrected and re-encoded, with EXIF/GPS, text, ICC, and
trailing data stripped. JPEG is re-encoded at quality 90. We store the original
and normalized SHA-256 fingerprints, dimensions, and sizes, but **not the original
binary**. This is privacy-oriented supporting evidence, not forensic preservation.
No content is sent to Gemini or interpreted as proof of actual repayment.

The backend commits a durable object reference before provider I/O. States are
`pending` → `uploading` → `ready`, or `removed`. Once an upload claims a file hash,
a different file requires a new intent. Same-file retries verify an existing object
rather than overwrite it. After an ambiguous provider/DB failure, retry the same
file or inspect GET status; do not create blind duplicate intents. A single ready
transition records one `evidence_added` event even under concurrent uploads.

No external provider request runs under an owner lock/DB transaction. Completion
and signing recheck state afterward: a concurrent removal cannot publish an image
or return a newly requested viewing link. Signed links are **bearer capabilities**:
anyone who obtains one can use it until expiry (default 60 seconds; allowed 30–300).
They are never cached in mutation receipts or logs. Removal immediately blocks new
links/uploads; previously issued links may work until expiry or physical deletion.

### Cleanup and retention

Removal preserves audit/metadata, not an immediately guaranteed physical deletion.
Run the one-shot cleanup command regularly (e.g. an external hourly job):

```powershell
$env:PYTHONPATH = "backend/src"
# Dry run by default; requires current migration and server DB configuration.
backend/.venv/Scripts/python.exe -m iou.evidence.cleanup --limit 100
# Explicitly expire intents and delete tombstoned binaries:
backend/.venv/Scripts/python.exe -m iou.evidence.cleanup --apply --limit 100
```

Run from the repo root with `PYTHONPATH=backend/src` set in the process environment;
on Unix use `backend/.venv/bin/python`. The regular `scripts/dev.py` tasks set import
paths for their own commands, not arbitrary Python invocations.

Cleanup expires abandoned pending/uploading intents after 24 hours, records a system
removal, and deletes their objects. Ready evidence is **not** automatically expired.
Deletion failures retain the reference for retry. Tombstones are never automatically
dropped and are rechecked hourly, even after a successful deletion: a paused worker
or provider may complete an upload after a concurrent delete. Repeated idempotent
deletes ensure such late writes remain recoverable. Batches are bounded (1–1,000),
with per-record attempt timestamps so failures don't permanently starve other work.
A dry run changes nothing. No timers are started in API processes.

Metadata, audit reasons, filenames, notes, fingerprints, and original idempotency
snapshots currently have no automatic deletion policy. Image removal is **not**
account/data erasure. Define that separate retention workflow before real-data
public launch. Do not drop metadata/tombstones without reconciling provider files.

## Cursor pagination (optional feature)

Keep legacy offset pagination, or set **server-only** `CURSOR_SIGNING_KEY` to a stable
random secret containing at least 32 bytes. Generate privately with Python's
`secrets.token_urlsafe(32)`; don't paste the output into Git/chat. Share the same key
across API workers; rotation invalidates outstanding cursors. Missing configuration
returns 503 only for cursor mode; legacy offset mode still works.

First page: `GET /friends?pagination=cursor&limit=25`. Continue using `next_cursor`
on `/friends?cursor=...`; similarly for `/loans`, friend history, and evidence lists.
Keep the same filters/endpoint/owner. Cursors are HMAC-signed, owner/filter-bound,
expire after one hour, and cannot be combined with nonzero offset. Invalid/expired/
mismatched tokens return 422. Payloads are opaque API tokens, not encrypted secrets.

Ordering uses timestamps plus UUID tie-breakers. A recorded-time cutoff excludes
most later inserts (including newly backdated events), but this is **not a frozen
MVCC snapshot**: previously in-flight transactions may commit later, and current
loan states/reversal labels/filter membership can change. Refresh when reconciling
live data; do not treat cursor pages as a certified historical export.

## Permissions and acceptance

Use a separate least-privilege DB runtime login. In addition to Level 1 privileges,
it needs SELECT/INSERT on `ledger_audit`, SELECT/INSERT/UPDATE on `evidence`, and
**UPDATE(reversed_at)** on `loan_events`. Replacement links are set on insertion;
amounts, dates, and notes are not updated. Do not grant UPDATE/DELETE on audit rows
or financial fields. Keep migration/schema-creation credentials separate. For an
already-provisioned runtime role, the permissions tested locally are:

```sql
GRANT USAGE ON SCHEMA iou_app TO iou_runtime;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA iou_app TO iou_runtime;
GRANT UPDATE ON iou_app.profiles, iou_app.friends, iou_app.evidence TO iou_runtime;
GRANT UPDATE (reversed_at) ON iou_app.loan_events TO iou_runtime;
```

This is not a grant to Supabase's browser `authenticated` role. Configure the
runtime connection separately and retain elevated credentials only for migrations.
After Level 3 migration, also grant UPDATE(settled_at) on iou_app.loans for its
settlement projection; original financial terms remain immutable.

Automated tests use local signing secrets, real PostgreSQL locks/constraints, and
fake Storage adapters. They test corrections after later payments, rollback on
failure, reopened loans, void restrictions, signed cursors, private ownership,
image validation/normalization, provider ambiguity, upload/removal races, durable
cleanup, guarded downgrade, and privilege revocation. Provider I/O lock probes and
concurrent requests verify that storage operations don't hold owner locks.

Before release, apply the migration with a backup and no mixed-version writers,
configure the private bucket/server key/cursor secret, back up DB **and Storage
objects** (a database dump alone does not contain the image binaries), run authenticated upload,
view, removal and cleanup checks, and verify browser roles cannot directly access
files. Confirm the actual backend host's request-body/timeout/memory limits; a host
may impose a lower limit than 5 MiB. Supabase Storage and hosted deployments are
not proven by mocked tests. Public launch also needs per-user quotas/rate limits,
monitoring, retention/deletion policy, and a security review.
