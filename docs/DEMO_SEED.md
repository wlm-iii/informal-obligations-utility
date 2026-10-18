# Sender-owned production demo data

The opt-in seeder targets **only the existing Supabase/IOU profile whose Auth email
matches the configured Gmail sender**. Gmail sending authorization does not itself
create an IOU account: sign into the deployed app as that Google account and open
Tracker once. School or other existing accounts are not changed.

## Dataset

Six explicitly `[DEMO]` friends, 23 loans, 18 settlement events (including one
reversed payment and its replacement), and two audit records:

- **Alex:** three on-time completions and a fresh, zero-penalty money IOU.
- **Blair:** mixed on-time/late history; overdue money with weekly interest, a late
  fee, grace, and an explicit combined lifetime charge cap.
- **Casey:** monthly interest and partial repayment; a separate overdue IOU still
  within grace; an on-time item return; daily interest with an audited correction.
- **Drew:** overdue and upcoming items, plus a returned item whose fee is only
  partially paid. Returning property does not erase financial charges.
- **Emery:** four on-time completions and no remaining obligations (not nudge-eligible).
- **Finley:** a waived late fee with principal still owed, a late return without
  penalties, a metadata-only other repayment preference, and a voided duplicate.

Lending dates span yesterday to about 180 days ago; due dates include past and future.
Amounts, interest, allocations, fees, statuses, scores, and trends use normal domain
calculators, not patched totals. Fictional scores have sufficiently completed friends
as well as insufficient-history friends. Existing score disclaimers still apply.

All six contact email addresses point to the sender's own inbox. **No reminder
permission is granted, no preview/delivery record is fabricated, and no email is
sent.** Any real message still requires normal preview and approval. The global
recipient cooldown/opt-out applies across these duplicate self-addressed contacts
and other owners; seeding never clears an earlier accepted/uncertain send.

Proof files and authentication are not fabricated. Automated delivery, Gemini,
and production email delivery troubleshooting are separate from this dataset.

## Dry run and apply

Run from the repository root using the project's Python environment. Check that
`DATABASE_URL` and Supabase configuration target the intended project. Do not paste
connection strings, tokens, or sender secrets into logs or PRs.

```sh
# Read-only owner/revision check. Prints the sender profile UUID, not its email/secrets.
EMAIL_MODE=disabled PYTHONPATH=backend/src backend/.venv/bin/python -m iou.demo_seed

# Explicit production write, only after verifying the printed owner UUID.
EMAIL_MODE=disabled PYTHONPATH=backend/src backend/.venv/bin/python -m iou.demo_seed \
  --apply --confirm-owner <SENDER_AUTH_UUID>
```

The `EMAIL_MODE` override affects only this command; it does not change deployed
runtime settings or `.env`. `nix develop -c env ...` can supply the project tools.

The command checks for migration `0008_repayment_preferences` but **never applies
migrations**, creates Auth users/profiles, changes permissions, overwrites records,
or deletes data. It refuses a mismatched confirmation UUID.

All operations run in one outer PostgreSQL transaction; normal ledger commits only
release nested savepoints. A failure rolls the entire new batch back. Stable,
owner-scoped UUIDv5 receipt keys and a stored date/timezone anchor make exact reruns
replay the same records even days later. Dates are not silently shifted forward and
existing financial history is never rewritten. Changed seed definitions need a new,
reviewed dataset version rather than reusing old keys.

Tests cover complete coverage, date-stable replay, owner isolation, no mail/consent,
and rollback after several committed savepoints, including both PostgreSQL connection
modes on a disposable database. Never run `test-db` against production.
