# Local development

Run commands from the repository root. **Native Windows, Linux, and macOS do not
require Nix.** Windows uses PowerShell; no WSL, Bash, Make, Docker, virtual-environment
activation, or PowerShell execution-policy change is needed. Use fake data only.
The app supports Google sign-in/private profiles and a backend lending ledger; the
frontend still has account UI only. Follow [auth setup](AUTH.md) to configure login
and hosted PostgreSQL, [ledger contracts](LEDGER.md) for lending, and
[Level 2 setup](HISTORY_PROOF.md) for audited corrections, private proof, and cursors.
[Level 3](CHARGES_SCORES.md) covers optional periodic charges, waivers, and scores.
[Level 4](DASHBOARD.md) defines dashboard metrics, rankings, and chart date filters.
[Level 5.0](REMINDERS.md) covers manual Gmail reminders, private credentials, and a
local-only preview/self-email demo. No real email runs in automated tests.

## Default setup (without Nix)

Required tools: **Python 3.12**, **Node 22 (at least 22.12) + npm**, **uv**, **Git**,
and **PostgreSQL 17** server/client binaries. The repository's standard-library
Python task runner works on all three platforms. Application dependencies are
installed into `backend/.venv` and `frontend/node_modules`, not your system Python.

### Windows (PowerShell)

1. Install [Git for Windows](https://git-scm.com/downloads/win),
   [Python 3.12](https://www.python.org/downloads/windows/) (include the Python
   launcher), and [Node 22](https://nodejs.org/en/download). Select the required
   versions, not a newer major version just because it is the website's default.
2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/):
   `winget install --id=astral-sh.uv -e`.
3. Install **PostgreSQL 17** from the [Windows downloads page](https://www.postgresql.org/download/windows/).
   Include the server and command-line tools; pgAdmin/Stack Builder are not needed.
   The installer may create a separate Windows service on port 5432. IOU does not
   use it or its installer password; it manages its own cluster on port 54329.
   Alternatively, extract the linked PostgreSQL 17 binary ZIP without installing
   a service (install any runtime prerequisites specified by its distributor).
4. Add PostgreSQL's `bin` directory to your **user PATH**. For the installer this is
   normally `C:\Program Files\PostgreSQL\17\bin`; for a ZIP use its extracted `bin`.
   Reopen PowerShell after installing tools or changing PATH. A session-only example:

   ```powershell
   $env:Path = "C:\Program Files\PostgreSQL\17\bin;$env:Path"
   ```

Verify in a **normal, non-administrator** terminal:

```powershell
py -3.12 --version
node --version
npm.cmd --version
uv --version
initdb --version
pg_ctl --version
psql --version
createdb --version
```

Keep the clone in a user-owned local folder, not `Program Files` or a network share.
`npm.cmd` avoids PowerShell blocking `npm.ps1`; the task runner resolves the `.cmd`
shim itself. You do not need to relax your execution policy.

### Linux/macOS

Install the same versions through your usual package manager. Ensure `python3`
(Python 3.12), `node`, `npm`, `uv`, `initdb`, `pg_ctl`, `psql`, and `createdb` are on
`PATH`. Some PostgreSQL packages are keg-only or put binaries in a version-specific
directory; add that directory to `PATH`. Do not start a system-wide PostgreSQL
service just for this project, and do not run the project commands as root.

Use **`python3` instead of `py -3.12`** in all examples below. Make is optional:
`make <task>` delegates to the same Python runner. Override its interpreter with
`make PYTHON=python3.12 <task>` if necessary.

## First setup

```powershell
py -3.12 scripts/dev.py install
py -3.12 scripts/dev.py db-init
py -3.12 scripts/dev.py db-start
py -3.12 scripts/dev.py migrate
```

`install` uses `uv pip sync` against the complete development lock and `npm ci`.
It copies `.env.example` to `.env` **only if `.env` is missing**, preserving existing
secrets on subsequent runs. It does not initialize or start a database. The example
URL is also the local default. Environment variables override `.env`. The starter's
old local `.env` may contain only `PYTHONPATH`; it is not required now.

## Daily use

```powershell
py -3.12 scripts/dev.py db-start
py -3.12 scripts/dev.py backend    # terminal 1, http://127.0.0.1:8000
py -3.12 scripts/dev.py frontend   # terminal 2, http://localhost:5173
```

Backend imports are set explicitly by the task. Stop frontend/backend with Ctrl-C;
run `py -3.12 scripts/dev.py db-stop` to stop PostgreSQL. Closing a shell does not
stop the database. Run the `help` task for the full command list.

Frontend calls `/api/*`. Vite forwards to port 8000 and removes `/api`; call backend
routes directly without that prefix. `/health` is liveness only and does not query
the database. `/hello` and `/random?maximum=1000` are temporary starter demonstrations.
OpenAPI docs live at `/docs`.

## Optional Nix shell (Linux/macOS)

Install [Nix](https://nixos.org/download/), enable `nix-command` and `flakes`, and run
`nix develop` before following the same setup tasks. Enter the shell in both server
terminals. The committed `flake.lock` pins nixpkgs. Shell packages are Node 22,
Python 3.12, PostgreSQL 17, uv, Make, and Git. Linux x86_64/aarch64 and Apple Silicon
macOS outputs are defined; only the current host is locally exercised. The pinned
nixpkgs no longer supports Intel macOS; use the default non-Nix setup there.

The shell changes environment variables but installs no project dependencies,
creates no files/databases, and starts no background processes. Python lives in
`backend/.venv`; do not install packages into the Nix store or system Python.
When intentionally updating tooling, run `nix flake update`, enter a new shell,
run the checks, and commit `flake.lock`. Linux native wheels use the shell's library
path. If using direnv, opt in yourself; no automatic `.envrc` execution is required.

## PostgreSQL lifecycle and safety

The following are `scripts/dev.py` tasks (also available as `make <task>` on Unix):

- `db-init`: creates `.local/postgres/data` with role `iou`. Re-running preserves
  the existing cluster. On Unix the base directory is owner-only; on Windows use a
  private user-owned folder with appropriate inherited filesystem permissions.
- `db-start`: starts that cluster on **127.0.0.1:54329** and creates database `iou`
  if missing. Re-running is safe; a different service on that port causes failure.
- `db-status`: reports status; a stopped server returns a nonzero exit code.
- `db-stop`: fast, clean shutdown of only this project's cluster.
- Logs: `.local/postgres/server.log`. Data/logs are ignored by Git.

Local authentication is **trust** on loopback only: any local OS user may connect.
This is for disposable data on a trusted development machine, never shared hosting
or production. Do not port-forward/expose it. The local `iou` role is a cluster
superuser for setup; production must use a least-privilege app role and separate
migration credentials where available. Unix sockets are disabled to avoid long
repository paths exceeding socket path limits. Lifecycle tasks always target this
local cluster; `DATABASE_URL` changes the app/migration/test connection, not these tasks.

No database deletion command runs automatically. To deliberately reset **all local
project data**, stop it, verify you are at the repo root, and only then:

```powershell
py -3.12 scripts/dev.py db-stop
# DESTRUCTIVE: permanently removes this project's local PostgreSQL data and logs.
Remove-Item -Recurse -Force .local/postgres
py -3.12 scripts/dev.py db-init
py -3.12 scripts/dev.py db-start
py -3.12 scripts/dev.py migrate
```

On Linux/macOS use `python3` and `rm -rf .local/postgres` instead. Do not reuse an
existing data directory with a different PostgreSQL major version. Dump/restore or
deliberately reset disposable data instead.

## Migrations

```powershell
py -3.12 scripts/dev.py migration --message "add loans"  # after defining/importing models
# Review generated file; it is not automatically correct.
py -3.12 scripts/dev.py migrate
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini current
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini check
```

On Linux/macOS the virtual environment's Python is `backend/.venv/bin/python`.
The initial `0001_baseline` is empty; `0002_profiles` creates private
`iou_app.profiles` storage; `0003_ledger` adds private friends, loans, settlement
events, and retry receipts; `0004_history_proof` adds audit/evidence storage and
reversal metadata; `0005_charges_scores` backfills zero-charge legacy terms and
principal-only allocations, adds optional periodic terms, and tracks settlement.
`0006_event_action_width` widens the action column for Level 3 item fee payments;
its rollback is guarded against truncating financial history. Dashboard APIs have
no additional schema requirements.
Downgrades are guarded once new feature data exists. These
migrations revoke browser-role access. Alembic autogeneration
only inspects the application schema, not Supabase-managed tables. `DATABASE_URL` applies to both the app
and Alembic. Never generate migrations against production or rely on API startup
to mutate the schema.

## Checks

```powershell
py -3.12 scripts/dev.py check      # frontend lint/build, Ruff, unit/API + tooling tests
py -3.12 scripts/dev.py test-db    # connectivity, upgrade twice, schema drift check
```

`test` needs no running database. **`test-db` does apply migrations to `DATABASE_URL`**,
so use the disposable local database or an explicitly isolated test database.
CI provisions its own PostgreSQL 17 service with throwaway credentials, and checks
the native task runner on Windows too. No tests send email. Frontend Vitest tests
cover account flows with mocked Supabase/network; real Google login is a manual
acceptance check, not something the offline suite proves.

Format Python with `backend/.venv/Scripts/python.exe -m ruff format --config
backend/pyproject.toml backend scripts` (one line; use `bin/python` on Unix).
Run Ruff's `check --fix` only after reviewing the intended changes.

## Dependency updates

Edit `backend/requirements.in` or `requirements-dev.in` and run the `lock` task.
Both generated UTF-8 requirement files pin transitive dependencies using
`uv pip compile --universal`, preserving platform markers (for example, excluding
`uvloop` on Windows and including Windows timezone data). Do not regenerate a
Linux-only lock for teammates on Windows. Dev resolution is constrained to the
runtime lock. Docker installs the runtime lock; local/CI
installs the complete dev lock. For intentional upgrades, use `uv pip compile
--upgrade` with the same arguments shown in the lock headers, runtime first.

Use `npm install` (`npm.cmd install` in PowerShell) for intentional frontend dependency
changes, then commit both package files. Use `npm ci` for ordinary reproducible
installs. Review audit findings; do not apply blanket `npm audit fix --force` upgrades.

## Environment contract

| Variable | Default / behavior |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://iou@127.0.0.1:54329/iou`; server only |
| `SUPABASE_URL` | Server-side project origin; missing means protected routes fail closed |
| `DATABASE_POOL_MODE` | `session` by default; `transaction` disables client pooling/prepared statements |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` | Public frontend config in `frontend/.env.local` |
| `CURSOR_SIGNING_KEY` | Optional server-only random secret, at least 32 bytes; stable across workers |
| `SUPABASE_STORAGE_KEY` | Optional server-only secret/service_role key for private evidence |
| `EVIDENCE_BUCKET` | `iou-evidence`; must be private, PNG/JPEG only |
| `EVIDENCE_SIGNED_URL_SECONDS` | 60 by default; 30–300 allowed |
| `EMAIL_MODE` | `disabled` by default; `gmail` requires complete sender/signing configuration |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_SENDER_EMAIL` | Backend-only central sender; never VITE variables |
| `REMINDER_SIGNING_KEY`, `REMINDER_PUBLIC_BASE_URL` | Stable secret and backend base for public unsubscribe |
| `GMAIL_RECIPIENT_ALLOWLIST`, `GMAIL_ALLOW_EXTERNAL_RECIPIENTS` | Self-only default; explicit consenting demo recipients / wider release gate |
| `REMINDER_QUIET_HOURS_ENABLED` | Default true; 09:00–18:00 in owner timezone |
| `PORT` | Docker runtime port, defaults to 8000; local backend task uses 8000 |

There is no mail provider configuration, job scheduler, or delivery code yet. Do not put database or email credentials in frontend `VITE_*` variables.
For hosted PostgreSQL, use a Psycopg SQLAlchemy URL (`postgresql+psycopg://...`),
percent-encode special characters in credentials, and use provider-required TLS.

## Troubleshooting

- **`py` missing:** install Python 3.12 with the launcher and reopen PowerShell.
  If `python --version` reports 3.12, `python scripts/dev.py <task>` works too.
- **PowerShell blocks `npm.ps1`:** use the task runner or `npm.cmd`, not an execution-policy bypass.
- **PostgreSQL tools missing:** add PostgreSQL 17's `bin` to `PATH` and reopen the
  terminal; on supported Unix hosts, `nix develop` is another option.
- **Backend cannot import `iou`:** use the `backend` task, or set `PYTHONPATH=backend/src`.
- **UI waits for the backend:** start the `backend` task, inspect its logs, then reload.
- **Port 54329 is busy:** stop the conflicting service; do not kill unknown processes.
- **Dependencies/imports fail:** check tool versions and run `install` again. If
  switching OSes (including Windows/WSL) or Python installations, recreate
  `backend/.venv` and `frontend/node_modules`; do not share them between OSes.
- **Nix ignores a new file:** flakes in Git repos see tracked/staged files; `git add`
  the relevant Nix files before evaluating them.
- **Nix download failure:** retry with network access; don't delete the lockfile to
  silently change tool versions.
