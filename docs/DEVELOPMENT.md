# Local development

Run commands from the repository root. Linux/macOS are supported by the shell
scripts; use WSL on Windows. No production credentials or real friend data are
needed. The app currently contains only a branded shell and starter connectivity check.

## With Nix

Enable `nix-command` and `flakes` in your Nix configuration, then run `nix develop`.
The committed `flake.lock` pins nixpkgs. Shell packages are Node 22, Python 3.12,
PostgreSQL 17, uv, Make, and Git. Linux x86_64/aarch64 and Apple Silicon macOS
shell outputs are defined; only the current host is locally exercised. The pinned
nixpkgs no longer supports Intel macOS; use the non-Nix instructions there.

The shell changes environment variables but installs no project dependencies,
creates no files or databases, and starts no background processes. Python lives in
`backend/.venv`; do not install packages into the Nix store or system Python.

When intentionally updating tooling, run `nix flake update`, enter a new shell,
run the checks, and commit `flake.lock`. Linux native wheels use the shell's library
path. If using direnv, opt in yourself; no automatic `.envrc` execution is required.

## Without Nix

Install Node 22 (at least 22.12), npm, Python 3.12, PostgreSQL 17 client/server tools,
[uv](https://docs.astral.sh/uv/), Make, Git, and Bash through your usual package manager.
Ensure `python3.12`, `initdb`, `pg_ctl`, `psql`, and `createdb` are on `PATH`.
Do not start a system-wide PostgreSQL service just for this project.

## First setup

```sh
cp .env.example .env              # only if you do not already have .env
make install
make db-init
make db-start
make migrate
```

`make install` uses `uv pip sync` against the complete development lock and `npm ci`;
it synchronizes the project virtual environment, not your system environment.
The example URL is also the local default. Environment variables override `.env`.
The starter's old local `.env` may contain only `PYTHONPATH`; it is not required now.

## Daily use

```sh
make db-start
make backend                     # terminal 1, http://127.0.0.1:8000
make frontend                    # terminal 2, http://localhost:5173
```

Enter the Nix shell in both terminals if using Nix. Backend imports are set explicitly
by the task, so manual virtual-environment activation is unnecessary. Stop frontend
and backend with Ctrl-C; run `make db-stop` to stop PostgreSQL. Closing a shell does
not stop the database.

Frontend calls `/api/*`. Vite forwards to port 8000 and removes `/api`; call backend
routes directly without that prefix. `/health` is liveness only and does not query
the database. `/hello` and `/random?maximum=1000` are temporary starter demonstrations.
OpenAPI docs live at `/docs`.

## PostgreSQL lifecycle and safety

- `make db-init`: creates `.local/postgres/data`, owned by the current user, with role
  `iou`. Re-running preserves the existing cluster.
- `make db-start`: starts that cluster on **127.0.0.1:54329** and creates database `iou`
  if missing. Re-running is safe; a different service on that port causes failure.
- `make db-status`: reports status; a stopped server returns a nonzero exit code.
- `make db-stop`: fast, clean shutdown of only this project's cluster.
- Logs: `.local/postgres/server.log`. Data/logs are ignored by Git.

Local authentication is **trust** on loopback only: any local OS user may connect.
This is for disposable data on a trusted development machine, never shared hosting
or production. Do not port-forward/expose it. The local `iou` role is a cluster
superuser for setup; production must use a least-privilege app role and separate
migration credentials where available. Unix sockets are disabled to avoid long
repository paths exceeding socket path limits.

No database deletion command runs automatically. To deliberately reset **all local
project data**, stop it, verify you are at the repo root, and only then:

```sh
make db-stop
# DESTRUCTIVE: permanently removes this project's local PostgreSQL data and logs.
rm -rf .local/postgres
make db-init
make db-start
make migrate
```

Do not reuse an existing data directory with a different PostgreSQL major version.
Dump/restore or deliberately reset disposable data instead.

## Migrations

```sh
make migration message="add loans"  # after defining/importing models
# Review generated file; it is not automatically correct.
make migrate
backend/.venv/bin/alembic -c backend/alembic.ini current
backend/.venv/bin/alembic -c backend/alembic.ini check
```

The initial `0001_baseline` creates no product tables; Alembic only records its
revision. Subsequent PRs own schema design. `DATABASE_URL` applies to both the app
and Alembic. Never generate migrations against production or rely on API startup
to mutate the schema.

## Checks

```sh
make check                        # frontend lint/build + Python Ruff + unit/API tests
make test-db                      # connectivity, upgrade twice, schema drift check
```

`make test` needs no running database. **`make test-db` does apply migrations to
`DATABASE_URL`**, so use the disposable local database or an explicitly isolated test
database. CI provisions its own PostgreSQL 17 service with throwaway credentials.
No tests send email. There are no frontend unit/browser tests yet; add them with
interactive product features.

Format Python with `backend/.venv/bin/ruff format backend`. Run Ruff's `check --fix`
only after reviewing the intended changes.

## Dependency updates

Edit `backend/requirements.in` or `requirements-dev.in` and run `make lock`.
Both generated UTF-8 requirement files pin transitive dependencies; dev resolution
is constrained to the runtime lock. Docker installs the runtime lock; local/CI
installs the complete dev lock. For intentional upgrades, use `uv pip compile
--upgrade` with the same arguments shown in the lock headers, runtime first.

Use `npm install` for intentional frontend dependency changes, then commit both
package files. Use `npm ci` for ordinary reproducible installs. Review audit findings;
do not apply blanket `npm audit fix --force` upgrades.

## Environment contract

| Variable | Default / behavior |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://iou@127.0.0.1:54329/iou`; server only |
| `EMAIL_MODE` | Only `disabled` is supported; other values fail validation |
| `PORT` | Docker runtime port, defaults to 8000; local Make target uses 8000 |

There is no mail provider configuration, job scheduler, authentication, or delivery
code yet. Do not put database or email credentials in frontend `VITE_*` variables.
For hosted PostgreSQL, use a Psycopg SQLAlchemy URL (`postgresql+psycopg://...`),
percent-encode special characters in credentials, and use provider-required TLS.

## Troubleshooting

- **Backend cannot import `iou`:** use `make backend`, or set `PYTHONPATH=backend/src`.
- **UI waits for the backend:** start `make backend`, inspect its logs, then reload.
- **Port 54329 is busy:** stop the conflicting service; do not kill unknown processes.
- **PostgreSQL tools missing:** enter `nix develop`, or add PostgreSQL's `bin` to `PATH`.
- **Dependencies/imports fail:** re-enter the shell and run `make install`.
- **Nix ignores a new file:** flakes in Git repos see tracked/staged files; `git add`
  the relevant Nix files before evaluating them.
- **Nix download failure:** retry with network access; don't delete the lockfile to
  silently change tool versions.
