# IOU — Informal Obligations Utility

**Your friends forget. We don’t.**

A hackathon app for tracking money and items friends borrow, recording repayments
and returns, calculating optional fees/interest, sending playful reminders, and
assigning clearly fictional credit scores.

**Status:** The backend supports Google sign-in/profiles, private lending, audited
corrections/voids, private proof-image workflows, and signed cursor pagination.
The backend also supports optional periodic interest/late fees, charge waivers,
explained fictional reliability scores, and private dashboard APIs for summaries,
obligations, rankings, and trends. Level 5.0 adds preset-tone, manually approved
Gmail reminders with consent, unsubscribe, and duplicate protection; real email is
disabled by default. Hosted acceptance and frontend API integration remain separate.
Use fake demo data.
See [auth setup](docs/AUTH.md), [ledger API](docs/LEDGER.md),
[Level 2 setup and safety](docs/HISTORY_PROOF.md),
[Level 3 charges and scores](docs/CHARGES_SCORES.md), and
[Level 4 dashboard metrics](docs/DASHBOARD.md), and
[Level 5.0 setup and self-email demo](docs/REMINDERS.md).

The authenticated **Tracker** link (`#tracker`) adds friend/loan creation, returns,
and charge-aware settlement without replacing the existing account/statistics pages.
Apply reviewed `0008_repayment_preferences` first. Live Tracker nudges now provide
recipient permission, server preview, explicit approval, and real Gmail submission.
Offline demos stay clipboard-only; email remains disabled by default. See the
[live email demo steps](docs/REMINDERS.md#live-email-demo-through-tracker). See [merge/contract notes](docs/DAILY_INTEREST_MERGE.md).

## Stack

- React 19 + Vite 7, JavaScript/JSX
- Python 3.12 + FastAPI
- PostgreSQL 17 + SQLAlchemy 2 + Psycopg + Alembic
- npm lockfile, pinned Python requirements, optional Nix flake dev shell

## Quick start

### Windows (PowerShell, no WSL or Nix required)

Install **Python 3.12, Node 22 (22.12+), uv, and PostgreSQL 17** using the
[Windows setup instructions](docs/DEVELOPMENT.md#windows-powershell). Then, from
the repository root in a normal (non-administrator) PowerShell terminal:

```powershell
py -3.12 scripts/dev.py install   # creates .env only if missing
py -3.12 scripts/dev.py db-init
py -3.12 scripts/dev.py db-start
py -3.12 scripts/dev.py migrate
py -3.12 scripts/dev.py backend   # terminal 1
```

In another PowerShell terminal at the repo root:

```powershell
py -3.12 scripts/dev.py frontend
```

### Linux/macOS

Install the same tools through your package manager (see [setup](docs/DEVELOPMENT.md)),
then use the same commands with `python3` instead of `py -3.12`. If Make is installed,
`make install`, `make db-init`, `make db-start`, `make migrate`, `make backend`, and
`make frontend` are equivalent shortcuts.

**Nix is optional:** `nix develop` supplies the tools on supported Linux/macOS hosts;
then follow the same setup commands. It does not install dependencies or start services.

- UI: <http://localhost:5173>
- Backend docs: <http://127.0.0.1:8000/docs>
- Liveness: <http://127.0.0.1:8000/health>
- UI API requests use `/api/*`; Vite proxies to the backend without that prefix.
- The `db-stop` task explicitly stops the development database; leaving the shell does not.

See [development instructions](docs/DEVELOPMENT.md) for database safety, configuration,
checks, and troubleshooting. Bash, Make, Docker, and Nix are not required on Windows.

## Common commands

```powershell
py -3.12 scripts/dev.py help
py -3.12 scripts/dev.py check     # linters, tests, frontend build
py -3.12 scripts/dev.py test-db   # disposable PostgreSQL required; applies migrations
py -3.12 scripts/dev.py migration --message "add loans"
py -3.12 scripts/dev.py migrate
py -3.12 scripts/dev.py lock      # recompile pinned Python dependencies
```

On Linux/macOS, replace `py -3.12` with `python3`, or use the optional Make shortcuts
(`make check`, `make migration message="add loans"`, etc.).

## Repository map

```text
frontend/               React application and npm lockfile
backend/src/iou/        FastAPI app, server config, database foundation
backend/migrations/     Alembic migrations (currently an empty baseline)
backend/tests/          API/config tests and PostgreSQL smoke test
scripts/dev.py          Cross-platform setup, tasks, and local PostgreSQL lifecycle
.github/                PR template and CI
```

## Working together

Use short-lived feature branches, Conventional Commits, and GitHub PRs into `main`.
Squash merge with a conventional PR title. Read [CONTRIBUTING.md](CONTRIBUTING.md).

- [Backend feature roadmap](docs/BACKEND_ROADMAP.md)
- [Google sign-in and private profiles](docs/AUTH.md)
- [Terminal design system: colors, fonts, components, and page styling](docs/DESIGN_SYSTEM.md)
- [Level 1 ledger API and migration](docs/LEDGER.md)
- [Level 2 corrections, proof images, and cursors](docs/HISTORY_PROOF.md)
- [Level 3 periodic charges, waivers, and fictional scores](docs/CHARGES_SCORES.md)
- [Level 4 dashboard APIs and metric definitions](docs/DASHBOARD.md)
- [Level 5.0 manual Gmail reminders and local self-test](docs/REMINDERS.md)
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
