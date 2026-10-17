# Deployment — retained starter scaffolding

**No hosted deployment has been verified.** This repository retains the organizer's
Docker/Render and Vercel options, with updates for the IOU package and pinned runtime
requirements. The Docker build and local container routes are smoke-tested; this does
not prove either hosted platform works.

The app has no authentication, loan features, email delivery, or scheduler yet.
Do not expose a real-data or publicly writable app until authentication, owner
isolation, privacy controls, and rate limits are implemented. Use fake data for demos.

## Shared requirements

- Provision managed PostgreSQL separately. The Nix/local database is not production infrastructure.
- Set `DATABASE_URL` to a SQLAlchemy Psycopg URL (`postgresql+psycopg://...`) with the
  provider's required TLS settings. Do not embed credentials in source or a Docker image.
- Keep `EMAIL_MODE=disabled`; there is no delivery implementation yet.
- Run `alembic -c backend/alembic.ini upgrade head` once in the release process with
  appropriate credentials, not in every API worker or serverless request.
- Plan backups, least-privilege runtime credentials, connection limits, and secrets storage.
- Liveness is `/api/health` on hosted mounts; it deliberately does not check database readiness.

## Docker / Render-style hosting

The multi-stage `Dockerfile` builds Vite with Node 22 and installs the runtime Python
lock on Python 3.12. It serves built static files and mounts the API at `/api`.
`.dockerignore` excludes `.env`, local PostgreSQL data, dependencies, and Git history.

```sh
docker build -t informal-obligations-utility .
docker run --rm -p 8000:8000 \
  --env DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require' \
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

Before choosing this route, validate Python runtime selection, source inclusion,
rewrites, backend dependencies, managed database connectivity, connection pooling,
and API 404s on the actual platform. Confirm build-generated `requirements.txt` is
used by the Python function packaging. Do not infer success from a Vite build alone.
If the platform supplies a generic `postgres://` URL, convert it to the explicitly
supported SQLAlchemy Psycopg form in server-side configuration.

Serverless functions can scale to many independent database pools. Tune pool/connection
limits or use a provider-compatible pooler before public deployment. Scheduled reminders
need a separately configured scheduler invoking an authenticated job; an API process
or serverless request is not a durable timer.

Once the team chooses and verifies one host, remove unused deployment scaffolding
in a focused PR and replace these notes with the tested release procedure.
