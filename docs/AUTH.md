# Level 0 — Google sign-in and private profiles

Implemented: Google OAuth via Supabase, PKCE callback/session handling, logout,
FastAPI bearer-token verification, and a private profile API. Level 1 now adds a
[backend friends/loans ledger](LEDGER.md); email/password UI, account deletion,
and reminders are not implemented.

## Environment

Install dependencies with `py -3.12 scripts/dev.py install` (use `python3` on Unix).
Copy `frontend/.env.example` to **`frontend/.env.local`** and fill in:

```dotenv
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
```

These are public browser configuration. Never put a Google client secret, database
password, or Supabase secret/service-role key in a `VITE_*` variable.

Add to the **root `.env`**, preserving existing values:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
DATABASE_URL=postgresql+psycopg://USER:ENCODED_PASSWORD@HOST:5432/postgres?sslmode=require
DATABASE_POOL_MODE=session
EMAIL_MODE=disabled
```

Use the Supabase **Connect** dialog's actual host, user, database, and port.
Percent-encode special characters in the password. A session pooler works with IPv4
for local development. The root `.env` is server-only; Vite loads the frontend file.
Restart the relevant server after changing environment files.

- Direct or session pooler: `DATABASE_POOL_MODE=session` (default); the app uses a
  small SQLAlchemy pool (three connections, two overflow connections per process).
- Transaction pooler (commonly port 6543): `DATABASE_POOL_MODE=transaction`; the app
  uses `NullPool` and disables Psycopg prepared statements. Choose connection limits
  appropriate for the hosted plan and number of API workers.
- Local PostgreSQL remains supported. A hosted Supabase identity can authenticate
  against our API while application profiles live in the local development DB.
- If `SUPABASE_URL` is missing, protected routes fail closed with 503; public health
  checks and offline tests still work.

No Google secret, JWT signing secret, or Supabase secret/service-role key is needed
by FastAPI. Google client credentials belong only in Supabase's provider settings.

## Dashboard setup

1. Enable Google in Supabase Authentication and configure its Google client ID/secret.
2. In Google Auth Platform, use a Web application client with origin
   `http://localhost:5173` and redirect URI
   `https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback`.
3. In Supabase URL Configuration, set the local Site URL to `http://localhost:5173`
   and allow `http://localhost:5173/auth/callback`.
4. Add teammates as Google test users if the consent app is in testing mode.
5. Use only `openid`, email, and profile scopes. Gmail access is not required.
6. Before deployment, add the stable Vercel origin in Google and the exact frontend
   callback URL in Supabase, and update the Supabase Site URL. Avoid broad production
   redirect wildcards. Public Google availability may require publishing/verification.

The browser returns to **our frontend** callback, not the backend's `/api` routes.
Supabase's JavaScript client exchanges the PKCE code and restores/refreshes sessions.
Our callback removes auth query parameters from browser history after initialization.
PKCE must finish in the browser/origin where login started (the verifier is local).

## Migrate and run

**Check which database your root `.env` selects before running migrations.** The
`migrate` task targets that URL, not necessarily the disposable local cluster.
Migration `0002_profiles` creates private profile storage; it does not alter Supabase
Auth or Storage tables. Run migrations once as a release/setup step, never on API startup.

```powershell
py -3.12 scripts/dev.py migrate
py -3.12 scripts/dev.py backend   # terminal 1
py -3.12 scripts/dev.py frontend  # terminal 2
```

For a local application DB, first run `db-init` and `db-start` and use the local URL
from `.env.example`. Do not use production as the database for automated tests.

Local `/api/*` requests are proxied by Vite to FastAPI; hosted scaffolding mounts
FastAPI at `/api`. Separate-origin frontend/API hosting would require an explicit
CORS and API URL configuration, which is not part of this slice.

## Profile API

Routes below are direct FastAPI paths; browser calls use `/api/me`.

- `GET /me`: lazily and idempotently creates/returns the current user's profile.
- `PATCH /me`: accepts any subset of `display_name` and `timezone`; unknown fields
  and explicit nulls are rejected. Names are trimmed, nonempty, and at most 100
  characters. Timezones must be valid IANA names.

```json
{"display_name": "Alex", "timezone": "America/Los_Angeles"}
```

Responses contain `id`, token-derived `email`, `display_name`, `timezone`,
`created_at`, and `updated_at`. Timestamps are UTC ISO-8601; responses are `no-store`.
New profiles default to UTC and use the Google name when available. Later sign-ins
never overwrite an edited name. Email is not editable here and is not an ownership
key. Repeated requests and concurrent first access cannot create duplicate profiles.

The UI calls the API with the Supabase **access token**, not a Google provider token.
JWT checks include signature, an allowlist of ES256/RS256, fixed project issuer,
`authenticated` audience/role, expiry, issued-at time, and a UUID subject. Signing
keys come only from the configured project's JWKS URL, cached for five minutes.
Invalid tokens return 401 with `WWW-Authenticate`; auth configuration/network outages
return 503. No token or database credentials should be logged.

## Ownership and database boundaries

- Profiles live in **`iou_app.profiles`**, outside the usual exposed `public` schema.
- The migration revokes schema/table access from PUBLIC and, when present, Supabase's
  `anon` and `authenticated` roles. **Do not expose `iou_app` through the Data API.**
- FastAPI scopes every profile operation to the verified token subject. There is no
  client-supplied owner ID or arbitrary-user profile endpoint.
- SQLAlchemy connections do not inherit JWT-based Supabase RLS. This slice deliberately
  uses a private, backend-only schema and explicit server-side ownership checks,
  rather than pretending that RLS authenticates the backend connection.
- Use trusted migration credentials for setup. Before production, provision a separate
  least-privilege runtime login with only schema USAGE and required table SELECT,
  INSERT, UPDATE permissions; do not give it migration/schema-creation privileges.
- Profile UUIDs are Supabase subjects, without a cross-schema foreign key to
  `auth.users`, allowing local PostgreSQL and offline tests. Account deletion and
  stale-profile cleanup need an explicit later lifecycle/retention policy.

The SDK persists sessions in browser storage. Protect against XSS and do not log
session contents. Logout clears the browser session/revokes refresh access according
to Supabase behavior, but already-issued JWTs may remain valid until expiry; this
backend does not perform a revocation lookup on every request. Choose an appropriate
Supabase JWT lifetime. Public launch still needs deployment verification, rate limits,
retention/account-deletion policy, and production security review.

## Verification

`check` runs Python unit/API tests, tooling tests, frontend Vitest tests, lint, and
production frontend build. JWT tests use real locally generated signatures and
stub only key discovery; ownership tests exercise independent users. No test needs
a Google account or network access. Frontend tests cover login initiation, session
restoration/callback failures, token forwarding, profile editing, logout, and errors.

`test-db` requires an **explicitly disposable database**. It applies/repeats migrations,
checks schema drift and schema permissions, and exercises profile routes on PostgreSQL.
Do not run it against a shared/production Supabase database.

Manual acceptance before calling hosted Level 0 complete:

1. Start the app and sign in through Google with two test accounts (separate browser
   profiles/private windows); verify both appear in Supabase Authentication Users.
2. Edit each name/timezone and confirm values survive refresh and logout/login.
3. Confirm the accounts have different profiles and no cross-account data appears.
4. Confirm API `/me` without a bearer token returns 401; `/health` remains public.
5. Test denied Google consent and a failed/expired callback; confirm safe errors.
6. Verify the hosted Vercel callback, API routing, database pooling, and migration
   release procedure before public launch. Automated mocked flows do not prove the
   Google dashboard settings or hosted deployment are correct.

Reference: [Supabase Google Auth](https://supabase.com/docs/guides/auth/social-login/auth-google),
[JWT verification](https://supabase.com/docs/guides/auth/jwts),
[database connections](https://supabase.com/docs/guides/database/connecting-to-postgres).
