# Level 5.0 — manually approved template email (Gmail API)

The signed-in Tracker connects to the manual reminder backend. One centrally
authorized Gmail account sends for IOU; users never
choose providers or authorize Gmail in their login. No inbox reading, Gmail SDK,
Gemini, scheduling, or payments. Google currently offers standard Gmail API use at
no extra cost within quotas; a few demo emails are well below those quotas. Account
sending limits/anti-abuse restrictions still apply. Do not assume unlimited delivery.

## Safe default and setup

Keep `EMAIL_MODE=disabled` in root `.env`. Credentials alone never enable sending.
The Gmail OAuth client must be separate from Supabase's login client. Authorize the
sending mailbox once with only `https://www.googleapis.com/auth/gmail.send`, offline
access, and your own OAuth Playground credentials. Save these server-only values:

```dotenv
GMAIL_CLIENT_ID=your-sender-client-id
GMAIL_CLIENT_SECRET=your-sender-client-secret
GMAIL_REFRESH_TOKEN=your-sender-refresh-token
GMAIL_SENDER_EMAIL=the-mailbox-you-authorized@gmail.com
EMAIL_MODE=disabled
```

Never commit `.env`, copy these into `VITE_*`, print tokens, or upload credential
screenshots. Restart the backend after changing its environment configuration. Refresh tokens in an External/Testing OAuth app generally expire after
seven days; authorization can be revoked earlier. Supabase login remains unchanged.

Also add a **stable, separate** secret (at least 32 bytes) for unsubscribe links:

```dotenv
REMINDER_SIGNING_KEY=your-new-random-secret
REMINDER_PUBLIC_BASE_URL=http://127.0.0.1:8000
```

Generate the secret privately with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
using your local Python. Paste it directly into `.env`, not chat. All workers must
share it. Keep it stable through the demo; rotating it invalidates old unsubscribe
links. Durable suppressions remain in the database. No expiring unsubscribe tokens.

`REMINDER_PUBLIC_BASE_URL` is the backend API base, including `/api` if mounted there.
For hosted use, set the real HTTPS API base. Loopback links work only on that computer;
the CLI's self-email can use loopback while the same local backend is running.
Non-self recipients are blocked until a non-loopback unsubscribe base is configured.

Additional settings:

```dotenv
GMAIL_RECIPIENT_ALLOWLIST=[]
GMAIL_ALLOW_EXTERNAL_RECIPIENTS=false
REMINDER_QUIET_HOURS_ENABLED=true
```

By default only the configured sender can receive actual mail. Additional consenting
test recipients can be listed as a JSON array; set `GMAIL_ALLOW_EXTERNAL_RECIPIENTS=true`
only after reviewed live acceptance to remove that restriction. The recipient still
needs consent and a current obligation. Standard API sends enforce 09:00–18:00 in
the owner's current timezone (recipient timezone is not stored). Environment-only
quiet-hour overrides are for consenting test scenarios, never autonomous chasing.

## Live email demo through Tracker

1. Set `EMAIL_MODE=gmail` with the existing sender credentials/signing key and restart
   the backend. No frontend provider keys or Gmail permissions on user login are needed.
2. Sign in at `http://localhost:5173/#tracker`. Use a contact with outstanding money,
   charges, or an unreturned item. For a controlled localhost demo, use the authorized
   Gmail sender's own inbox and a clearly labelled fictional IOU you create yourself.
   Records use the configured database; the UI does not silently seed test data.
3. Click **Nudge**. Opening the dialog only reads permission and delivery history.
4. Confirm recipient permission and choose Friendly, Playful, or Direct but polite.
   Each tone has **three message templates** (nine total). Choose a template, then
   click **Generate email preview**. The backend automatically fills the contact and
   lender names, current total money owed, and unreturned-item count. This saves the attestation if necessary and creates
   a server preview; it does not send. Existing recipient opt-out cannot be overridden.
5. Review the exact To, subject, read-only body/unsubscribe footer, and expiry. Check
   the separate approval checkbox, then click **Send this email** for one real submission.
6. The result distinguishes Gmail acceptance, definite failure, cancellation, pending,
   and uncertain delivery. Check Inbox/Spam. **Check delivery status** uses GET only;
   an interrupted/uncertain send is never automatically retried. Do not create another
   send to investigate an uncertain result. An expired/changed preview needs fresh approval.

The dialog prevents duplicate clicks and closing while submission is pending. If the
page/navigation disconnects, closing does not guarantee cancellation; backend durable
claims/history remain authoritative. Recent attempts/24-hour cooldown are shown, and
permission/address changes force review again. The backend always rechecks current
eligibility, consent, quiet hours, configured recipients, and opt-out before dispatch.

A real email demo is supported, not simulated. However, the **public/offline demo stays
clipboard-only** and cannot call email APIs. Existing standalone Statistics clipboard
drafts are unchanged; use Tracker or Tracker → Progress → Draft reminder for real email.
No Gemini drafting is included.

### If the live demo is blocked

- **Email disabled:** use `EMAIL_MODE=gmail` and restart the backend; editing `.env`
  alone does not refresh the cached configuration.
- **Demo allowlist:** the sender's own inbox is allowed by default. Other consenting
  test recipients require `GMAIL_RECIPIENT_ALLOWLIST=["address@example.com"]` (or a
  separately reviewed wider release). Never add a recipient without permission.
- **Public unsubscribe URL:** non-self recipients need a reachable public HTTPS
  `REMINDER_PUBLIC_BASE_URL`. Localhost is suitable only for self-testing on that computer.
- **Quiet hours:** regular API sends use 09:00–18:00 in the owner's profile timezone.
  For an explicitly consenting demo, the operator may set
  `REMINDER_QUIET_HOURS_ENABLED=false` and restart. The UI never bypasses this check.
- **Cooldown:** a sent or uncertain reminder blocks that address for 24 hours, across
  duplicate contacts and owners. Enabling email does not reset it or send anything.

All network mutation errors are surfaced; no automatic send retries occur. A 202 or
Gmail `sent` record is acceptance, not proof of inbox delivery. Do not paste client
secrets, refresh tokens, or signing keys into frontend environment variables or UI.

## Fast local self-email demo (no frontend/JWT setup)

This developer CLI uses only a loopback PostgreSQL URL, creates a fresh fake owner,
contact, permission confirmation, and fictional $5 loan, and addresses **only the
configured sender**. It bypasses HTTP authentication for local seeding, not the
service's consent/eligibility checks. It cannot target Supabase and is not a public
route. Existing accounts, loans, and hosted data are not used.

From the repository root with Nix:

```sh
nix develop
python scripts/dev.py db-init
python scripts/dev.py db-start
export PYTHONPATH=backend/src
backend/.venv/bin/python -m iou.reminders.demo --migrate
```

That explicitly applies migrations to the local database and prints a preview.
**It makes no Google request and sends no email.** It overrides the hosted URL from
`.env` only inside the CLI process. Default local URL:
`postgresql+psycopg://iou@127.0.0.1:54329/iou`. `--database-url` may select another
loopback PostgreSQL database, never a remote host.

In a second terminal, run a local backend using that **same database and signing key**
so the unsubscribe link can work (the `.env` hosted URL must not take precedence):

```sh
nix develop
DATABASE_URL=postgresql+psycopg://iou@127.0.0.1:54329/iou python scripts/dev.py backend
```

When ready for **one real, self-addressed email**, in the first terminal:

```sh
backend/.venv/bin/python -m iou.reminders.demo --send
```

Inspect the exact recipient/subject/body, then type `SEND`. This enables Gmail only
inside that process and disables quiet hours only for this self-addressed demo;
it does not change `.env` or enable the API globally. Gmail receives exactly one
submission attempt. Check Inbox/Spam/Sent. The 24-hour recipient cooldown remains
in effect, including across fresh fake owners; repeated CLI runs cannot bypass it.

For native Windows, use `py -3.12 scripts/dev.py db-init`/`db-start`, set
`$env:PYTHONPATH='backend/src'`, and replace the interpreter with
`backend\.venv\Scripts\python.exe`. In the backend terminal set `$env:DATABASE_URL`
to the local URL before running the backend task.

`authorization_failed` means no message submission occurred: check authorized account,
client credentials, refresh token expiry, and Gmail API enablement. `provider_rejected`
is a definite Gmail rejection. `delivery_uncertain` means Gmail may have accepted;
check Sent manually and **do not blindly resend**. Failed previews are terminal;
create/approve a fresh one only after a definite rejection or pre-submit failure.

Automated tests never send actual email. A separately approved one-off Gmail
transport test was accepted and the recipient confirmed receipt, with no retries
or ledger changes. This verifies that sender's OAuth/delivery setup, not the full
hosted reminder workflow. Unsubscribe acceptance used disposable PostgreSQL and the
configured signing key without actual email. Hosted migration and full reminder-flow
acceptance remain explicit release steps; email stays disabled by default.

## API flow

Browser paths add `/api`; direct FastAPI paths do not. All private routes require the
existing bearer JWT and return `Cache-Control: no-store`. Mutations require UUID
`Idempotency-Key` headers. Client-supplied owner IDs and arbitrary message text are
not accepted. Tones are `friendly`, `playful`, `direct` (direct remains polite).

1. Friend must have an email and not be archived.
2. `PUT /friends/{id}/reminder-preferences` with:
   `{"recipient_email":"friend@example.com","permission_confirmed":true}`.
   This is the lender's explicit attestation that the recipient agreed to reminders;
   owing someone alone is not consent. Use false to revoke that sender's permission.
3. `POST /friends/{id}/reminder-previews` with `{"tone":"friendly","template_id":2}`.
   `template_id` is a strict integer 1–3 and defaults to 1 for older tone-only clients.
   Returns immutable recipient, subject, complete body/footer, ID, and 10-minute expiry.
4. Show that exact preview. `POST /reminders/{id}/send` with
   `{"approved":true,"recipient_email":"friend@example.com"}` and a new key.
5. Inspect the returned delivery state; use `GET /reminders/{id}` or
   `GET /reminders?friend_id=...&limit=25&offset=0` for owner-only history.
6. `GET /friends/{id}/reminder-preferences` reports current permission/opt-out state.

Preview creation and permission receipts use the existing ledger receipt namespace.
Send keys have a separate owner-scoped namespace, bind exactly one preview and approved
recipient, and replay **current status**, not a second submission. Another key cannot
resend the same preview. Send returns 202 for a durable attempt, including immediate
terminal outcomes; 202 alone does not mean delivery succeeded. Mode disabled returns
503 before reservation; sent/failed/pending key replays remain readable while disabled.
`sent` means Gmail accepted submission, not proof of inbox delivery. Replies go to
the shared sending mailbox; IOU does not read or forward them. History limits are
1–100 (default 25), with offset 0–100,000.

GET history is private offset pagination; cached mutation receipts remain original
snapshots. Use GET for current permission/preview state after edits.

## Eligibility, facts, and message safety

Currently owing means unpaid principal/interest/fees **or an unreturned item**.
Upcoming obligations are eligible; being overdue is not required. A zero-cash item
still qualifies. A returned item with unpaid fees qualifies only for those fees.
Fully settled/returned and voided obligations do not qualify. Other owners' contacts,
missing email, archived contacts, expired previews, unconfirmed permission, and opted-out
recipients cannot be sent reminders.

Each of the three tones has three distinct, short templates (nine total). The
chosen template is rendered on the server, not from client-supplied amounts or names.
The selected ID is preview input only; the immutable subject/body already preserve
exactly what was approved, so no new database column or migration is needed. Default
variant 1 retains old tone-only receipt hashes; changing variants requires a new key.
Changing tone/template clears the displayed preview and approval in the UI.

The short template uses owner/contact names, current total USD owed, and unreturned
item count. It does not send notes, proof images, scores, other lenders' history, or
claims about real credit/legal consequences. Footer and unsubscribe URL are included
in the displayed preview. MIME is plain text, the subject is fixed, and header email
addresses are validated. The sender name is IOU; its mailbox is the configured account.

The approval fingerprint binds relevant loan IDs, kinds, due dates, balances, borrowing
states, email, and names. Balances/permission/opt-out/expiry are checked again after
OAuth token refresh, immediately before authorizing Gmail submission. Contact edits
invalidate permission until reconfirmed. Changing facts requires a fresh preview and
approval, rather than silently changing an approved message.

## Delivery states, races, and cooldown

```text
preview -> reserved -> sending -> sent / failed / uncertain
                   -> cancelled (eligibility changed)
```

Reservation commits a durable key and a recipient-wide claim. OAuth refresh happens
with no transaction/owner lock held. Final validation briefly locks owner and recipient,
then commits `sending` before the one Gmail POST. Final result recording occurs in a
new transaction. There are no provider calls under DB locks and no Gmail send retries.
Access tokens are kept in memory only, never in delivery history.

Recipient rows normalize/casefold email and use a stable SHA-256 lookup key. They are
private, not anonymous or public-searchable. Claims, 24-hour cooldown, and suppression
are **global per normalized address**, covering duplicate contacts and different
owners. Definite rejection or failed OAuth preparation releases the claim/cooldown;
sent and uncertain submissions retain the 24-hour gate. This is deliberately more
conservative than a per-loan limit.

Claims older than five minutes can be recovered on a new send request: pre-submit
reservations become cancelled; attempted submissions become uncertain, retaining
cooldown. Recovery never retries the old message. A failed DB result commit can leave
`sending` until recovery; inspect Gmail Sent manually. Gmail does not supply an
application idempotency key—Message-ID is correlation only, not exactly-once delivery.

A settlement, opt-out, or permission change **before final authorization** cancels
submission. A change after authorization can race the external Gmail request. We do
not hold financial DB locks across network I/O or promise atomicity with Gmail.

## Unsubscribe

Each footer has a signed opaque link without plaintext email, lender identity, or loan
IDs. GET only shows a confirmation form so mail-scanner GETs do not opt people out.
POST performs the durable, idempotent suppression; no login is needed. It stops future
IOU reminders to that address from **all owners/all loans**, not just the original one.
Owners cannot reverse recipient opt-out; recipient resubscription is not in this slice.

Use HTTPS for public links, keep the signing key stable, and redact query tokens from
proxy/access logs. Confirmation uses no third-party resources and sends no referrer.
There is no automated unsubscribe email, so opting out cannot cause more email.

## Migration, permissions, and testing

`0007_manual_reminders` creates three private tables, revokes browser-role/public
access, and refuses downgrade while permission/history/suppression records exist.
Review/back up and apply explicitly; tests use disposable local PostgreSQL, never the
hosted URL from `.env`. Existing financial/history migrations remain unchanged.

Runtime roles need SELECT/INSERT on all three new tables, UPDATE on
`reminder_permissions`, UPDATE(opted_out_at,last_attempt_at,in_flight) on
`reminder_recipients`, and UPDATE(status,send_key,updated_at,attempted_at,sent_at,
provider_message_id,error_code) on `reminders`. Do not grant UPDATE on immutable
preview contents or DELETE on suppression/history. Retain prior profile locking
permissions. Keep `iou_app` outside browser roles/Data API exposure.

Tests cover tones, eligibility, consent, stale/expired approvals, ownership, unsubscribe,
allowlists, quiet hours, failures, replay, global cooldown, MIME, secret-safe errors,
redirect/network/malformed responses, and no retry on uncertain acceptance. Real
PostgreSQL adds concurrent pending replays, blocked duplicate sends, mutation during
OAuth, owner-lock release during provider I/O, schema drift/ACLs, and guarded rollback.

Level 5.1 can add optional Gemini drafting behind the same immutable-preview approval
flow. Tracker reminder controls are implemented with mocked client/API regression
tests. Schedules, webhooks, automatic retries, inbox access, public production hardening,
and Gmail outcome reconciliation are not implemented.
After the demo, revoke the sender grant, delete its separate OAuth client, and remove
stored credentials. Leave the Supabase login client alone.
