# Deployment — retained starter scaffolding

**No hosted deployment has been verified.** This repository retains the organizer's
Docker/Render and Vercel options, with updates for the IOU package and pinned runtime
requirements. The Docker build and local container routes are smoke-tested; this does
not prove either hosted platform works.

Google authentication, private profiles, and the backend lending ledger are
implemented; frontend lending screens, email delivery, and a scheduler are not. Complete [auth setup and acceptance](docs/AUTH.md),
hosted owner-isolation checks, privacy controls, and rate limits before any real-data
public release. Use fake data for demos.

## Shared requirements

- Provision managed PostgreSQL separately. The Nix/local database is not production infrastructure.
- Set `DATABASE_URL` to a SQLAlchemy Psycopg URL (`postgresql+psycopg://...`) with the
  provider's required TLS settings. Do not embed credentials in source or a Docker image.
- Set server-only `SUPABASE_URL` and the frontend's `VITE_SUPABASE_URL` /
  `VITE_SUPABASE_PUBLISHABLE_KEY`. Google client secrets stay in Supabase, not the app.
- Configure exact Google/Supabase callback origins for the hosted frontend.
- Keep `EMAIL_MODE=disabled`; there is no delivery implementation yet.
- Review [Level 1's migration and retry contract](docs/LEDGER.md) before deploying
  the lending API. All new ledger tables remain private; no direct browser SQL access.
- Run `alembic -c backend/alembic.ini upgrade head` once in the release process with
  appropriate credentials, not in every API worker or serverless request.
- Plan backups, least-privilege runtime credentials, connection limits, and secrets storage.
- Liveness is `/api/health` on hosted mounts; it deliberately does not check database readiness.

## Docker / Render-style hosting

The multi-stage `Dockerfile` builds Vite with Node 22 and installs the runtime Python
lock on Python 3.12. It serves built static files and mounts the API at `/api`.
`.dockerignore` excludes `.env`, local PostgreSQL data, dependencies, and Git history.

```sh
docker build -t informal-obligations-utility \
  --build-arg VITE_SUPABASE_URL='https://YOUR_PROJECT_REF.supabase.co' \
  --build-arg VITE_SUPABASE_PUBLISHABLE_KEY='YOUR_PUBLISHABLE_KEY' .
docker run --rm -p 8000:8000 \
  --env DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require' \
  --env SUPABASE_URL='https://YOUR_PROJECT_REF.supabase.co' \
  --env EMAIL_MODE=disabled informal-obligations-utility
```

Open <http://localhost:8000>. Replace the example URL; do not use local trust
credentials for a remote database. Inside a container, `127.0.0.1` is the container,
not the developer's PostgreSQL service.

The Docker image includes the backend source and Alembic files under `/code/backend`.
Run migrations as a separate release job, for example:

```sh
docker run --rm --env DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require' \
  informal-obligations-utility alembic -c backend/alembic.ini upgrade head
```

A release job from a checked-out repository with the runtime lock installed works too.
Do not run this automatically in every web container.

For Render or similar: connect the new GitHub repository, choose Docker, configure
server-side environment variables and managed PostgreSQL, and verify the build,
`/api/health`, `/api/docs`, frontend routes, and unknown API 404 behavior. Configure
`PORT` as required by the provider (Docker defaults to 8000). Do not assume free-tier
limits, background jobs, or release commands are available without checking your plan.

## Vercel-style hosting

`vercel.json` and `api/index.py` are retained as **unverified** starter configuration.
The build creates frontend assets and copies the runtime requirements to the root
for Python dependency discovery. `PYTHONPATH=backend/src` makes `iou` importable.
The wrapper mounts the backend at `/api`.

Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` in Vercel's build
environment; these are compiled into the public frontend. Configure `SUPABASE_URL`,
`DATABASE_URL`, and `DATABASE_POOL_MODE` separately for the server runtime. Redeploy
after changing frontend configuration.

Before choosing this route, validate Python runtime selection, source inclusion,
rewrites, backend dependencies, managed database connectivity, connection pooling,
and API 404s on the actual platform. Confirm build-generated `requirements.txt` is
used by the Python function packaging. Do not infer success from a Vite build alone.
If the platform supplies a generic `postgres://` URL, convert it to the explicitly
supported SQLAlchemy Psycopg form in server-side configuration.

Serverless functions can scale to many independent database pools. Tune pool/connection
limits or use a provider-compatible pooler before public deployment. With Supabase's
transaction pooler, set `DATABASE_POOL_MODE=transaction` for `NullPool` and disabled
Psycopg prepared statements; direct/session connections default to `session`. Scheduled reminders
need a separately configured scheduler invoking an authenticated job; an API process
or serverless request is not a durable timer.

Once the team chooses and verifies one host, remove unused deployment scaffolding
in a focused PR and replace these notes with the tested release procedure.
