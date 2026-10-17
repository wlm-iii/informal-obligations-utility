# Terminal login in React

The production entry point renders `src/components/TerminalLogin.jsx` directly.
It uses controlled React form fields and calls `src/services/login.js` with the
shared Supabase client. There is no iframe, `postMessage` listener, injected HTML,
or embedded application payload. The old `public/IOU-Terminal-Login.html` bundle
has been removed. `frontend/index.html` remains Vite's small normal entry document.

## Shared styling

`src/index.css` imports `src/styles/tokens.css`, which declares the Flexoki palette,
Iosevka font faces, and shared geometry. WOFF2 files are ordinary binary assets in
`src/assets/fonts/`; Vite builds cacheable hashed URLs. `terminal.css` contains the
login-specific layout, backgrounds, and dialog classes. The signed-in profile and
lazy-loaded React demo use the same tokens. See [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).

## Authentication

Google sign-in and Open an account use the existing Google provider and
`/auth/callback` PKCE flow. Email/password supports existing Supabase accounts if
enabled in the project. Password registration is not added. Submissions clear the
controlled password value, prevent duplicate requests, and show safe inline errors.
The SDK owns session storage and restoration. No access tokens pass through UI
messages. After sign-in, the existing account view uses the authenticated `/api/me`
service, including editing, retries, expired sessions, and logout. No backend
schema or authorization contract has changed. See [AUTH.md](AUTH.md) for setup.

## Graph and demo

`MarketChart.jsx` renders an SVG from seeded sample state. It advances once per
second and uses CSS for leftward movement between samples. React effects manage
the interval, visibility listener, and reduced-motion listener, with cleanup on
unmount. Pattern selection and pause controls are React state. The graph is
decorative, clipped behind the headline, and hidden from assistive technology.

Explore demo lazy-loads `src/demo/DemoWorkspace.jsx` as React UI. Its model is an
ES module with no global variables. The demo retains the `iou-demo-v1` storage key
and sample-record schema, with validated restore and storage failure handling.
Core demo flows include money/item records, edits, repayment and returns,
cancellation/history, editable reminder tones and copy, search/status filters,
summary reports, fictional rankings, profile editing, and JSON backup/restore.
It does not authenticate users, send messages, move money, or sync demo loans with
the backend. Personal browser-only workspace creation, custom circles, period
filtering, and extra social-sharing controls from the old standalone prototype
are not exposed in this React demo; stored record fields are retained.

## Verification

From `frontend` run `npm test`, `npm run test:login`, `npm run lint`, and
`npm run build`. React integration tests exercise visible form interactions,
authentication/token forwarding, profile editing/logout/errors, timer cleanup,
pause/reduced motion, and local demo mutations. Provider errors remain generic.
The removed Node harnesses inspected an inline HTML script and are superseded by
component/model tests. Live Google consent, hosted database connectivity, and
browser visual acceptance still require a configured environment.
