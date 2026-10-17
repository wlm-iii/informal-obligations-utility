# IOU backend

Python 3.12 + FastAPI, with SQLAlchemy/Psycopg and Alembic scaffolding for PostgreSQL 17.
Google sign-in token verification, private profiles, and the Level 1 ledger API are
implemented. Follow [auth setup](../docs/AUTH.md) and [ledger contracts](../docs/LEDGER.md)
for configuration, migrations, idempotency headers, and endpoint examples. No new
API keys are needed for basic lending. Level 2 adds audited corrections/voids,
private proof images, durable cleanup, and signed cursors; see
[setup and safety](../docs/HISTORY_PROOF.md). Storage and cursor mode need optional
server-only configuration; existing auth/offset APIs do not.

From the repository root:

```powershell
py -3.12 scripts/dev.py install
py -3.12 scripts/dev.py db-init
py -3.12 scripts/dev.py db-start
py -3.12 scripts/dev.py migrate
py -3.12 scripts/dev.py backend
```

On Linux/macOS replace `py -3.12` with `python3`, or use `make <task>`.
Nix is optional; see the [setup instructions](../docs/DEVELOPMENT.md).

`auth.py` verifies Supabase tokens; `profiles.py` owns `GET/PATCH /me` and the
private `iou_app.profiles` table. `ledger/` owns contacts, loans, settlement events,
and retry receipts in the same private schema. `evidence/` validates images, talks
to private Supabase Storage, and provides a dry-run-first cleanup command. Ownership
comes only from verified JWT subjects. Ledger creation/settlement requires UUID `Idempotency-Key` headers.

The app is `backend/src/iou/api.py`; API docs are at <http://127.0.0.1:8000/docs>.
`src/api.py` is a compatibility entry point. `src/main.py` mounts the API and built
frontend for the Docker deployment. Importing the API does not connect to PostgreSQL.

Tasks: `test` (no database), `test-db` (disposable database required), and `lint`.
See [development docs](../docs/DEVELOPMENT.md) and
[product spec](../docs/SPEC.md).
