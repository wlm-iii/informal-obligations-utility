# IOU — Codex handoff

This package contains the latest saved project source, including changes after commit 7e3ad06 on feat/return-tracker-work. Open source/ as your project folder in Codex. Read docs/FRONTEND_DESIGN.md; its last sections describe the current reference styling.

## Run the sample dashboard

Requires Node.js 22.12+ and npm. In source/frontend run:

    npm ci
    npm run dev

Open http://localhost:5173/dashboard-preview.html for the sample dashboard. The normal / route is the production Google sign-in flow. The included preview/ is prebuilt; serve that folder with any static HTTP server (for example python -m http.server 5178 --bind 127.0.0.1) and open /dashboard-preview.html. Do not double-click the built HTML; its JavaScript modules need HTTP.

## Current behavior

- Post-login debt ledger, searchable loans, friend sidebar, add-friend form, profiles and account settings.
- Nudge opens editable reminder text with tone choices and clipboard copying. Nothing sends automatically.
- Progress matches the repayment reference: bar, summary totals, date-filtered cumulative graph, Record repayment and Draft reminder. The pie chart has been removed from Progress.
- History matches the Past payments reference: UTC date, description, amount, Recorded badge, newest first. Borrowed/open/returned records remain below.
- Ranks has both halls and new centered award icons. Public Enemy #1 is pinned first in Shame.
- Shared style: pale mint/paper surfaces, fine green borders, compact Iosevka, restrained green/red data values.

## Important boundaries

The preview uses fictional Anca/friends and the eight reference payments: $260 repaid, $385 lent, $125 outstanding. Preview mutations reset on reload. Live app requests remain authenticated and use backend ledger data. Backend loans represent lending by the owner to friends; borrower-side liabilities are not implemented. Rankings are still sample data, not a connected score service.

## Files to continue editing

frontend/src/components/Dashboard.jsx and Dashboard.css: shell, ledger, profiles, dialogs.
frontend/src/components/ReferenceTheme.css: final shared style overrides.
frontend/src/components/Progress.jsx and Progress.css: repayment summary and chart.
frontend/src/components/History.jsx and History.css: records tables.
frontend/src/components/Leaderboards.jsx and Leaderboards.css: ranks and sprites.
frontend/src/services/dashboard.js: authenticated requests/history and reminder formatting.
frontend/src/services/dashboardDemo.js: separate preview fixtures.
frontend/public/assets/: fonts, font license and award artwork.

## Validation

From source/frontend: npm test; npm run lint; npm run build; npm run build:preview.
Latest results: 46 frontend tests, lint, and production build passed. Backend tests previously passed (117), and tooling tests previously passed (11); they were not rerun for the latest visual changes. Database integration tests were not run.

For full backend setup, read docs/DEVELOPMENT.md, docs/AUTH.md and docs/LEDGER.md. Supply your own environment values using the included .env.example templates. No environment secrets, dependencies, databases or Git credentials are included.

## Git and handoff

Original repository: https://github.com/wlm-iii/informal-obligations-utility
Original branch: feat/return-tracker-work
The export includes newer uncommitted changes and omits .git. To retain upstream history, clone the repository, create a working branch, overlay source/ onto it, review, and commit. This export was not pushed.

Suggested Codex prompt: Read HANDOFF.md and docs/FRONTEND_DESIGN.md. Continue this IOU project from the saved source. Preserve the supplied Progress graph and History table layouts, Iosevka font, pale mint/paper theme, and working flows. Keep sample data separate from authenticated records. Run frontend tests before editing.
