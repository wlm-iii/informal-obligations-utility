# Terminal login

The React entry point displays the standalone terminal design in a same-origin
frame. The design remains independently viewable at `/IOU-Terminal-Login.html`.
Connected mode uses `?connected=1`; the parent verifies both the message origin
and the exact frame window before starting authentication. Supabase sessions and
access tokens stay in the React parent. Passwords are cleared from the form as
soon as submitted and are never persisted by the login page.

Google sign-in and Open an account use the existing Supabase Google provider and
`/auth/callback` PKCE flow. Email/password sign-in uses Supabase password auth for
existing accounts when enabled in the project; this does not enable password
registration or configure providers. After authentication the existing account
view loads `/api/me` using the session access token, including its existing
profile editing, retry, expiry, and logout behavior. See [AUTH.md](AUTH.md) for
provider/environment setup. No backend schema or authorization changes are needed.

Explore demo remains a separate local, fictional workspace. It does not sync
records with the backend. The animated graph is decorative and updates once per
second; it pauses for reduced motion, hidden documents, and its pause control.

Run `npm test`, `npm run test:login`, `npm run lint`, and `npm run build` from `frontend`. Standalone
dependency-free checks can also run from the repository root:

```
node scripts/tests/test-login-background.cjs
node scripts/tests/test-login-auth.cjs
```

Live Google consent and hosted database connectivity require the project's
configured test accounts and environment; mocked tests do not verify that setup.
