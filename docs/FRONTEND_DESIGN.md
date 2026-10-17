# Hall of Fame & Hall of Shame — design reference

## Typography

All page text uses **Iosevka**, including headings, navigation, usernames, award names, scores, and footer text. The fallback is `monospace`.

- Regular: weight 400, `frontend/public/assets/iosevka-400.woff2`
- Bold: weight 700, `frontend/public/assets/iosevka-700.woff2`
- Fonts are bundled locally and loaded with `@font-face` and `font-display: swap`; no external font request is needed when viewing the page.
- Source: https://github.com/be5invis/Iosevka
- Distribution: https://www.npmjs.com/package/@fontsource/iosevka
- License: SIL Open Font License 1.1; see frontend/public/assets/IOSEVKA-LICENSE.txt.

## Flexoki dark palette

Source: https://stephango.com/flexoki

| Token | Flexoki value | Hex | Usage |
| --- | --- | --- | --- |
| `--bg` | black | `#100F0F` | Page background |
| `--panel` | base-950 | `#1C1B1A` | Hall panels |
| Surface | base-900 | `#282726` | Secondary surfaces |
| `--line` | base-850 | `#343331` | Dividers and borders |
| Strong border | base-800 | `#403E3C` | Emphasized outlines |
| `--text` | base-200 | `#CECDC3` | Primary text and scores |
| `--muted` | base-500 | `#878580` | Captions, ranks, labels |
| `--green` | green-400 | `#879A39` | Fame headings, award names, brand |
| `--yellow` | yellow-400 | `#D0A215` | First-place rank emphasis |
| `--red` | red-400 | `#D14D41` | Shame headings and award names |

Dark backgrounds use Flexoki's dark base colors and 400-level accents. Texture and decorative rings use transparent variants of the base colors. The supplied illustration artwork retains its original colors; the page UI uses the Flexoki palette.

## Assets and components

Fonts, illustration screenshots, and the font license are bundled in `frontend/public/assets`. The illustrations use CSS background windows into the user-provided reference images; they retain their original colors. Each illustration has an accessible award label.

- `frontend/src/components/Leaderboards.jsx`: renders the illustrative Hall of Fame and Hall of Shame as semantic ordered lists.
- `frontend/src/services/leaderboards.js`: non-mutating ranking, alphabetical tie breaking, and the Public Enemy #1 override.
- `frontend/src/components/Leaderboards.css`: both panels, title hierarchy, and responsive icon positioning.
- `frontend/src/App.jsx` and `App.css`: shared left sidebar, active navigation state, and account flow.
- `frontend/src/components/ReturnTracker.jsx`: authenticated ledger overview, titled “Still lent out vs. returned to you”.
- `frontend/src/index.css`: local Iosevka declarations and global dark theme.

## Layout and typography

The IOU / wordmark appears above vertical Overview and Hall of Fame navigation in the same left sidebar. Main content is offset to its right; the sidebar narrows at 700px and 420px. Both halls stay side by side.

Award titles use Iosevka Bold at 25px (20px at widths up to 1000px). Muted names use 16px / 14px; score values use 16px / 13px. Artwork is 64px / 42px. Rows accommodate wrapping. Fame uses Flexoki green-400; Shame uses red-400.

## Ranking and data

Fame ranks credit scores highest first. Shame pins Public Enemy #1 at rank 01, then sorts the remaining records lowest score first. Equal scores sort alphabetically. A person's name, award, illustration, and score move together.

Leaderboard records are clearly labeled illustrative samples, with no backend scoring connection. The overview continues to use authenticated backend loan records, including pagination, refresh, and cancellation. Authentication and profile editing remain available on Overview.

## Verification

Component tests cover both ranking orders, the pinned first entry, artwork association, input immutability, tie breaking, and navigation between the authenticated overview and sample halls. Existing authentication and ledger tests remain in place. Use `py -3.12 scripts/dev.py check` for the standard lint, unit/API, tooling, frontend test, and build checks. Database integration tests are separate.


## Home dashboard framework

After Google sign-in, `Dashboard.jsx` opens the private debt ledger. A 4:3 CSS grid frame contains the top IOU wordmark (green O), add-friend button, friend sidebar, and independently scrolling content. The frame keeps its ratio at narrower widths while rows reflow.

Dashboard is the default view; Progress renders the existing authenticated item-return chart; Ranks renders the sample halls; History lists current and completed borrowing records in the owner's ledger. Clicking a friend or counterparty name opens their contact details, notes, open/completed counts, outstanding balance, and borrowing history. Account editing and sign-out remain available through the top account button.

`dashboard.js` authenticates friend requests, disables caching, reads every page, includes archived friend names for historical records, and sends an idempotency key when adding a friend. Backend records currently represent money/items lent by the owner to a friend, not liabilities the owner owes someone else. History reflects that supported model. No credit score is invented for a live friend profile.

Nudge opens a native modal dialog with Sweet bestie, Direct, and Playful tones, editable reminder text, and clipboard copying with a manual-copy fallback. Item reminders request an item return; money reminders use outstanding USD cents. Nothing is transmitted to friends automatically. Dialog focus returns to the triggering control when closed.

`npm run build:preview` builds `dashboard-preview.html` into `dist-preview` with labeled sample records. Preview-only friend additions remain in memory; the signed-in app uses the backend. The preview shares the actual React dashboard components, CSS, Iosevka fonts, and Flexoki artwork assets. Main production builds retain the normal Google sign-in entry point.

### Surrounding text adjustment

Header account text and friend-sidebar names, counts, and footer text are enlarged. The top tagline is removed. Progress and Ranks content and tab typography remain unchanged.

### Account profile consistency

The own-account page uses the same identity header, avatar, stats cards, and borrowing-history layout as friend profiles. It summarizes the full private ledger and retains account settings and sign-out below history. The sample preview user is Anca; live users retain their actual account names.

### Account summary totals

The own-account summary shows active friend count, money outstanding, money repaid (including partial repayments), items still out, and items returned. Money is summed in integer USD cents; each item loan counts as one item. Borrowing history remains below these cards. These are totals from the owner’s lending ledger, not personal asset ownership or unsupported borrower-side debts.
