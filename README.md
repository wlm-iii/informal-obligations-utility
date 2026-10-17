# IOU — Informal Obligations Utility

**Your friends forget. We don’t.**

A hackathon app for tracking money and items friends borrow, recording repayments
and returns, calculating optional fees/interest, sending playful reminders, and
assigning clearly fictional credit scores.

**Status:** repository foundation only. Loan management, authentication, reminder
sending, scheduling, and scores are not implemented. Use fake data for demos.

## Stack

- React 19 + Vite 7, JavaScript/JSX
- Python 3.12 + FastAPI
- PostgreSQL 17 + SQLAlchemy 2 + Psycopg + Alembic
- npm lockfile, pinned Python requirements, optional Nix flake dev shell

## Quick start

On Linux/macOS (Windows: use WSL), install [Nix](https://nixos.org/download/)
with `nix-command` and `flakes` enabled, then:

```sh
nix develop
cp .env.example .env             # first setup only; do not overwrite your secrets
make install
make db-init
make db-start
make migrate
make backend                    # terminal 1
```

In another terminal at the repo root:

```sh
nix develop
make frontend
```

- UI: <http://localhost:5173>
- Backend docs: <http://127.0.0.1:8000/docs>
- Liveness: <http://127.0.0.1:8000/health>
- UI API requests use `/api/*`; Vite proxies to the backend without that prefix.
- `make db-stop` explicitly stops the development database; leaving the shell does not.

Nix does **not** install app dependencies or start services automatically. See
[development instructions](docs/DEVELOPMENT.md) for non-Nix setup, database safety,
configuration, checks, and troubleshooting.

## Common commands

```sh
make help
make check                       # linters, unit/API tests, frontend build
make test-db                     # disposable PostgreSQL required; applies migrations
make migration message="add loans"
make migrate
make lock                        # recompile pinned Python dependencies
```

## Repository map

```text
frontend/               React application and npm lockfile
backend/src/iou/        FastAPI app, server config, database foundation
backend/migrations/     Alembic migrations (currently an empty baseline)
backend/tests/          API/config tests and PostgreSQL smoke test
scripts/db.sh           Explicit, project-local PostgreSQL lifecycle
.github/                PR template and CI
```

## Working together

Use short-lived feature branches, Conventional Commits, and GitHub PRs into `main`.
Squash merge with a conventional PR title. Read [CONTRIBUTING.md](CONTRIBUTING.md).

- [Product specification and provisional rules](docs/SPEC.md)
- [Local development](docs/DEVELOPMENT.md)
- [Deployment notes and limitations](DEPLOYMENT.md)

## Starter attribution and licensing

Bootstrapped from [HackAtUCI's full-stack starter](https://github.com/HackAtUCI/starter-pack-full-stack-web-app),
revision `7eecea0acb671ce1fed410961992dfad1ea60599`. The organizer starter includes
React/Vite, FastAPI examples, and Render/Vercel deployment scaffolding.

No license file was present in the cloned starter. Attribution is not a license;
confirm the organizers' reuse terms before choosing a license or redistributing
outside the hackathon. No new license is asserted by this repository.
