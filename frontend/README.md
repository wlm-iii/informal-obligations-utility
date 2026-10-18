# IOU frontend

## Real email reminders

On the signed-in `#tracker` page, **Nudge** opens recipient permission → preset tone →
server-generated read-only preview → explicit approval → **Send this email**. This
offers three templates per tone (nine total), automatically filled by the backend
with names, money owed, and item counts. It uses real Gmail when configured/enabled;
no email is sent just by
opening the dialog or enabling a setting. Pending/uncertain results only offer status
checks, never automatic re-submission. Recent attempt history and backend policy errors
are shown. The public/offline demo and standalone Statistics drafts stay copy-only.

See [setup, allowlists, quiet hours, and live demo](../docs/REMINDERS.md#live-email-demo-through-tracker).
No Gmail secret or refresh token belongs in `VITE_*` or client code. No schema change
or Gemini key is required by this frontend connection.


Use the [terminal design system](../docs/DESIGN_SYSTEM.md) when styling additional
pages. It documents the shared React theme, font assets, components, and animation rules.

React 19 + Vite 7, JavaScript/JSX. Google sign-in, session restoration/logout, and
profile editing are implemented; lending features are not. Copy `.env.example` to
`.env.local` inside `frontend/` and follow [auth setup](../docs/AUTH.md).

From the repository root:

```powershell
py -3.12 scripts/dev.py install
py -3.12 scripts/dev.py backend    # terminal 1
py -3.12 scripts/dev.py frontend   # terminal 2
```

On Linux/macOS replace `py -3.12` with `python3`, or use `make <task>`.
Nix is optional; see the [setup instructions](../docs/DEVELOPMENT.md).

UI: <http://localhost:5173>. Vite proxies `/api/*` to FastAPI on port 8000 and removes
the prefix. The Docker deployment mounts the API under `/api` as well.

- `src/App.jsx`: session-aware React entry point, account UI, and profile form.
- `src/components/TerminalLogin.jsx`: native React login; no iframe or HTML bundle.
- `src/components/MarketChart.jsx`: decorative SVG and lifecycle-managed animation.
- `src/styles/tokens.css`: shared mint-and-emerald palette and Iosevka font definitions.
- `src/assets/fonts/`: binary WOFF2 assets; see `docs/licenses/` for the SIL license.
- `src/demo/`: lazy-loaded React demo with separate local storage.
- `src/services/`: Supabase PKCE/session integration and authenticated profile requests.
- `npm run lint`, `npm test`, `npm run build` inside `frontend/` (`npm.cmd` in PowerShell).
- Vitest covers account flows with mocked Supabase/network; a real Google browser
  round-trip remains part of manual acceptance.

See [development docs](../docs/DEVELOPMENT.md). Never put secrets in `VITE_*` values;
they become part of the public browser bundle.
