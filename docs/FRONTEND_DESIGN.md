# Hall of Fame & Hall of Shame — design reference

This is an illustrative design reference, not the authoritative score/rate contract.
The compatibility merge preserves main's login, account, theme tokens, bundled fonts,
and 300–850 fictional score rules. Tracker uses backend periodic balances, not daily
post-due math. See [integration decisions](DAILY_INTEREST_MERGE.md).

## Typography

All page text uses **Iosevka**, including headings, navigation, usernames, award names, scores, and footer text. The fallback is `monospace`.

- Regular: weight 400, `frontend/src/assets/fonts/Iosevka-400.woff2`
- Bold: weight 700, `frontend/src/assets/fonts/Iosevka-700.woff2`
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

## Mint background

The page and dashboard content background use mint green `#A8D5BA`. The original Flexoki green `#879A39` and hover `#A0AF54` accents are restored. Header, sidebar, navigation surfaces, and content panels retain their dark Flexoki colors for readable contrast.

## Current light dashboard palette

The supplied landing-page reference supersedes the dark dashboard surfaces: pale mint `#F1F7ED` page background, sage `#E7F1E3` header/sidebar and inputs, ivory `#FCFEF9` content/modal panels, deep green `#198356` actions, dark forest `#152A22` primary text, muted green `#567168` secondary text, and `#D8E6D8` dividers. Overdue badges use warm amber; Shame titles use muted red. The original chart segment colors and illustration artwork remain. Iosevka, 4:3 framing, navigation and interactions remain. The sidebar slogan has been removed.

### Sunshine and coral accents

Warm yellow `#F5CD68` and pale yellow `#FFF3CD` highlight the add button, record count, nudge actions, Fame heading, and selected statistic cards. Soft coral `#FCE5DD` and red-brown `#A94D42` accent overdue loans, unpaid totals, Shame headings, and statistic cards. Overdue rows retain explicit text alongside their colored border. The mint base and green primary navigation remain.

### Navigation spacing and deeper mint

Main tabs distribute evenly across their bar with bold titles and larger gaps. The mint page/content backdrop is now `#DFECDD`. The interactive-preview banner is removed; preview records remain demonstration data, and the Ranks sample-data disclosure remains.

### Centered award icons

The new transparent award-icons-v2.png sheet replaces the reference screenshot windows. Eight equal cells match the supplied new logo designs. CSS uses a 400% by 200% sheet with centered 64px / 42px frames. Rankings remain unchanged. Artwork was recreated with the built-in image generation tool.


### Progress reference layout

The Progress headline contains only Your lending, at a glance and Refresh data. A repayment progress bar and three summary cells precede the cumulative USD repayment chart, with 30D, 90D and ALL date filters. Live history loads every page per friend from the authenticated ledger history endpoint; the trend uses actual repayment effective dates. The original item-return chart remains below. No repayment events are invented when history is empty or unavailable. The same Iosevka, ivory panels, mint backdrop and green/red totals align this view with the rest of the dashboard.

## Screenshot-aligned reference revision

The latest references supersede the previous fixed 4:3 shell and playful card treatments. The shell now fills available height, with flat pale-paper `#FBFDF7` surfaces, mint `#F1F7EC` background, thin `#D1E1CB` dividers, compact Iosevka typography, and restrained green/red data values. `ReferenceTheme.css` is the final shared visual layer across Dashboard, Progress, Ranks, History, friend profiles, and Account.

Progress contains the single requested headline and refresh button, repayment bar, Record repayment / Draft reminder controls, three summary cells, and cumulative repayment area/line graph with date filters. The previous item pie chart is removed from this view. Record repayment validates USD decimal input, enforces the outstanding balance, and writes through the existing idempotent repayment endpoint; in preview mode it updates memory only. Nudge remains copy-only.

History uses the supplied Past payments table layout: UTC date, loan description, USD amount, and Recorded status, newest first. A second table below retains borrowed-item and open/returned records. Actual payment history is loaded from paginated authenticated friend history endpoints. The reference preview has the eight supplied payments totaling $260 and a $385 loan with $125 outstanding; no live data is replaced.
