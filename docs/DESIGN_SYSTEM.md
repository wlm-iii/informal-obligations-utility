# IOU terminal design system

Use this guide when extending the login design to Your Circle, reports, friend
details, reminders, The Halls, and account settings. The direction is a serious
banking terminal applied to very unserious debts: restrained, precise, slightly
sarcastic, and readable. Let typography, information hierarchy, thin rules, and
small status details carry the theme.

## Source of truth and current implementation

The production login is native React. There is no standalone HTML bundle,
iframe, HTML injection, or cross-window authentication bridge in the app.

| Source | Responsibility |
| --- | --- |
| [tokens.css](../frontend/src/styles/tokens.css) | Shared palette, font faces, radii, and typography variables |
| [index.css](../frontend/src/index.css) | Global reset, body typography, form controls, focus, and inline feedback |
| [terminal.css](../frontend/src/styles/terminal.css) | Login layout, responsive rules, cards, dialogs, and background styling |
| [TerminalLogin.jsx](../frontend/src/components/TerminalLogin.jsx) | Controlled sign-in form, navigation, and background controls |
| [MarketChart.jsx](../frontend/src/components/MarketChart.jsx) | React SVG graph and lifecycle-managed timer |
| [InfoDialog.jsx](../frontend/src/components/InfoDialog.jsx) | Shared native dialog, rendered through a React portal |
| [App.css](../frontend/src/App.css) | Signed-in account layout using the shared tokens |
| [DemoWorkspace.jsx](../frontend/src/demo/DemoWorkspace.jsx) | Lazy-loaded local demo in React |

The shared theme is imported by `src/index.css` at the React entry point. New
React screens inherit its tokens and form defaults. Use scoped layout rules for
each page instead of copying a whole login stylesheet. The independently saved
HTML preview is not a source dependency of this repository.

See [terminal login integration](TERMINAL_LOGIN.md) and the
[Iosevka SIL Open Font License](licenses/Iosevka-LICENSE.txt).

## Palette

Colors follow the mint-and-emerald study from the latest design preview. Keep backgrounds pale and
reserve green, red, and yellow for purposeful accents.

| Role | Current value | Apply to |
| --- | --- | --- |
| Canvas | `#f1f7ed` | Page background |
| Panel | `#fcfef9` | Cards, dialogs, grouped information |
| Raised surface | `#e5f0df` | Inputs, secondary buttons and compact controls |
| Hover / subtle separator | `#dce8d7` | Secondary hover fill, header/footer rules |
| Standard border | `#d6e5d2` | Cards, inputs, dividers |
| Strong border | `#a2c5a9` | Secondary controls, dialogs, input hover |
| Primary text | `#15261f` | Labels and default text |
| Emphasized text | `#15261f` | Headings, amounts, important names |
| Supporting text | `#425e52` | Descriptions and secondary actions |
| Muted text | `#536c60` | Metadata, placeholders, helper text |
| Green | `#198357` | Primary action, positive status, positive graph |
| Green hover / link | `#13764c` | Primary hover, selected links |
| Yellow | `#bd871b` | Gold coin, receipt details, attention |
| Yellow detail | `#856214` | Small emphasized captions and links |
| Red | `#bb413f` | Negative graph, overdue status indicator |
| Red foreground | `#a93436` | Overdue badge text |

Status treatments (the warning palette is reserved for future warning notices):

| Treatment | Fill | Border | Text |
| --- | --- | --- | --- |
| Overdue / inline error | `#ffe7e1` | `#f5c6ba` | `#a93436` |
| Warning (reserved) | `#fff3d5` | `#f1d38a` | `#4b390a` |
| Selected background option | `#e3f1df` | `#198357` | `#13764c` |
| Initials avatar | `#ffe6a0` | `#f1d38a` | `#4b390a` |

Use text and an icon or marker alongside status color. A green primary action is
not automatically a financial success state. Errors should explain the problem
and recovery action. The current `.inline-error` treatment is red; do not use a
warning color for every severity.

The shared variables are declared in `src/styles/tokens.css`:

```css
:root {
  color-scheme: light;
  --bg: #f1f7ed;
  --panel: #fcfef9;
  --surface: #e5f0df;
  --line: #d6e5d2;
  --ink: #15261f;
  --muted: #536c60;
  --green: #198357;
  --red: #bb413f;
  --yellow: #bd871b;
  --amber: var(--green); /* Compatibility alias for the emerald accent. */
  --mono: 'IOU Iosevka', 'Iosevka', Consolas, monospace;
  --sans: var(--mono);
}
```

## Typography and font assets

Use **Iosevka** throughout: headings, navigation, body copy, form controls, numbers,
and metadata. The internal family is `IOU Iosevka`, with regular `400`
and bold `700` WOFF2 assets, normal style, and `font-display: swap`. Preserve that
family name when reusing the shared definitions. Set form controls explicitly
to the same family; otherwise browser defaults can introduce another font.

```css
body {
  font-family: var(--mono);
  font-feature-settings: 'calt' 1, 'liga' 1;
  -webkit-font-smoothing: antialiased;
}
button, input, textarea, select { font-family: var(--mono); }
```

| Element | Current login typography |
| --- | --- |
| Hero heading | `700`, `clamp(48px, 5.3vw, 75px)`, line-height `1.04`; breakpoint overrides below |
| Hero tracking | `-1.6px` normally; `-1.8px` wide desktop; `-1px` tablet/mobile; `-.9px` smallest mobile |
| Brand name | `21px`, `700`; `19px` on mobile before the smallest layout hides it |
| Supporting paragraph | `14px`, line-height `1.8`; `15px` wide desktop and `13px` smallest mobile |
| Primary button | `14px`, `700` |
| Secondary / Google button | `13px` |
| Form labels / values | `12px` / `14px`; placeholders `12px` |
| Dialog heading / body | `23px` heading (`21px` smallest mobile) / `13px` body |
| Sample money amount | `27px` (`25px` smallest mobile), tracking `-1.4px` |
| Metadata | Usually `9-11px`; uppercase with restrained tracking |

For new working pages, use `14-16px` for essential reading and form values, and
reserve tiny terminal captions for nonessential metadata. The login's `9px`
captions are not the default size for a borrowing table or a mobile form.
Use one prominent page title, then smaller section headings; do not repeat the
large marketing hero scale on every dashboard section. Keep amounts aligned in
tables and format currencies consistently, including currency labels where needed.

The two fonts live in `frontend/src/assets/fonts/Iosevka-400.woff2` and
`Iosevka-700.woff2`. `tokens.css` defines each face once through a relative asset
URL; Vite emits hashed, separately cacheable WOFF2 files in the build. They are
binary assets, not base64 strings inside HTML or JavaScript. Keep the font
copyright and [SIL license](licenses/Iosevka-LICENSE.txt) with redistributed fonts.
The full font files are large; any later subsetting should preserve the glyphs
needed by names, currency values, and UI symbols, and retain the license.

## Geometry, spacing, and layout

Corners are slightly rounded, with rectangular banking-software proportions.

| Component | Current radius |
| --- | --- |
| Inputs and primary/secondary buttons | `6px` |
| Standard receipt card | `8px` (`7px` smallest mobile) |
| Login card | `9px` (`8px` smallest mobile) |
| Dialog | `9px` |
| Logo / initials avatar | `5px` |
| Status badge / small icon control | `4px` |

Use `1px` borders and flat fills. The login card shadow is intentionally quiet:
`0 20px 50px #0002`; receipt cards have no shadow. Keep large soft shadows for
overlays. Avoid adding large pill controls or broadly rounded cards to new pages.

The existing desktop shell has a `1360px` maximum width, `7%` horizontal padding,
and a `105px` header. At `1500px` and above, the shell becomes `1450px` wide with
`100px` side padding. The login uses a `1.12fr 1fr` grid with a `10%` gap; its form
column is at most `418px` (`450px` on wide desktop). Those columns are specific to
the login, not a required dashboard layout.

Reference component spacing: login card `30px 28px 24px`, input `13px 14px`, field
gap `20px`, label-to-input gap `9px`, and receipt padding `19px 21px 17px`. On new
pages, use a consistent `8 / 12 / 16 / 20 / 24 / 32px` spacing vocabulary rather
than cloning every marketing-page measurement. Give related fields a tighter gap
than separate sections.

## Components and interaction states

- **Primary action:** green fill, white `#ffffff` text, green border, `6px` radius;
  hover `#13764c`, no vertical jump. Use one dominant action per local task.
- **Secondary action:** raised neutral fill, strong border, emphasized text;
  hover fill `#dce8d7`. Text links underline on hover with a small offset.
- **Inputs:** recessed canvas fill, standard border, emphasized value text;
  hover border `#a2c5a9`; focus border green plus `0 0 0 2px #19835717` ring.
  Keep persistent labels; placeholders do not replace them.
- **Keyboard focus:** preserve visible focus. The current generic rule is a
  `2px` yellow outline with `4px` offset; inputs use the green focus treatment.
- **Sizing:** current inputs/Google action are at least `47px` high and the primary
  action `49px`. For new pages, aim for at least `44px` interactive targets,
  including icon-only controls; some older small preview controls are smaller.
- **Loading:** disable duplicate submission, communicate progress in text, retain
  the user's context, and restore controls after failure. Current disabled
  opacity is `.6`. Do not rely on a spinner alone.
- **Feedback:** use inline status/alert regions. Put field-specific validation by
  its field; put API failures near the relevant action with a retry path.
- **Dialogs:** neutral panel, strong border, `9px` radius, clear title, close control,
  keyboard dismissal, and focus return. Current maximum width is `490px`/`92vw`.
- **Icons:** simple SVG line icons, usually `15-16px`, about `1.2-1.4px` stroke.
  Give icon-only buttons an accessible name. Do not use emoji as every control's icon.
- **Empty states:** explain what belongs here and give the relevant next action,
  such as Add reminder. Distinguish empty results from loading and API failure.

## Responsive behavior

| Breakpoint | Existing login behavior to preserve |
| --- | --- |
| `min-width: 1500px` | Wider shell; `80px` hero; slightly larger card and copy |
| `max-width: 1000px` | `6%` shell padding; narrower gap; `58px` hero |
| `max-width: 740px` | Single column; `61px` hero; header `88px`; content/form up to `540px`; branding caption hidden |
| `max-width: 430px` | Header `77px`; `52px` hero; tighter gaps; brand wordmark hidden; logo retained |

For new pages, collapse multi-column forms and card grids before content becomes
cramped. Keep the primary action reachable, avoid horizontal page scrolling, and
use a deliberate scroll container or a compact alternate layout for wide tables.
Never hide an essential label or debt status to imitate the login's decorative
metadata reductions.

## Decorative stock-style background

The active pattern is the **Debt ticker**, a jagged area graph concentrated behind
the left-hand headline. It does not cover the login card or represent live data.

- New sample every `1000ms`; a roughly one-minute window moves left smoothly
  between samples, and older values exit through the clipped left edge.
- Color is green `#198357` or red `#bb413f` according to the decorative reference
  level. The line uses `1.35px` stroke at `.48` opacity.
- Area fill fades from `.17` to `.015` opacity. Grid lines use `.055` opacity and
  the dashed reference line `.09`, keeping the reading surface quiet.
- Occasional labels such as `CHARGER` or `$20.00` travel with points. A new label
  is added every 12 samples; label text is `10px` at `.5` opacity.
- The SVG uses a `720 × 400` viewBox. Its wrapper is positioned relative to the
  hero heading and follows its CSS dimensions; a horizontal mask fades its edges.
- Keep it behind text, clipped, `aria-hidden`, and `pointer-events: none`.
- Stop animation when paused, when the document is hidden, when another pattern
  is selected, or when `prefers-reduced-motion: reduce` is set. React effects clean
  up timers and listeners on unmount, including StrictMode remounts. Reduced motion
  leaves a static graph. Other reduced-motion styling also removes transitions.

Other study patterns (contours, grid, signals, off) remain optional preview
controls. They are not required navigation or a production settings feature.
Use `MarketChart` and its pure sample functions in `marketSeries.js`; do not
copy a second animation loop into another page.
On dense working pages, prefer a static or absent decorative chart. Real charts
need their own labeled axes, units, source data, and accessible interpretation;
never mix decorative movement with a user's actual balance or statistics.

## Tone and information hierarchy

Keep financial labels precise and jokes secondary. For example, show **Overdue
3 days** as the status, and put **Concert financing. Emotionally necessary.** in
supporting copy. Buttons should describe actions: Add reminder, Record repayment,
Mark returned. Keep humor out of validation requirements, money calculations,
authentication failures, and destructive confirmation labels.

Use uppercase sparingly for short metadata such as `CLIENT ACCESS / 01`, with
ordinary sentence case for fields and prose. Fictional scores, sample debts,
local demos, and decorative market data must remain identifiable as such.

## Applying the design to another page

1. Reuse the token/font layer already imported through `src/index.css`. Add new
   semantic tokens to `src/styles/tokens.css` instead of duplicating color literals.
2. Reuse `InfoDialog` and the shared control classes. Extract additional reusable
   Button, Input, Panel, and StatusBadge components as their behaviors repeat. Scope page styles to avoid global `h1`/`label` overrides
   accidentally applying marketing dimensions to working screens.
3. Apply canvas/panel separation and the typography hierarchy first, then small
   yellow brand details and semantic green/red statuses. Keep dense data legible.
4. Use the existing authenticated API/service layer. Styling a sample record does
   not connect it to the backend or authorize changes to account/session behavior.
5. Check keyboard order, visible focus, labels, loading/errors/empty states, small
   screens, and reduced motion. Test essential text contrast on its actual surface;
   low-opacity decorative tokens are not text colors or accessibility guarantees.
6. Compare with the login reference and run the relevant frontend tests, lint,
   and build. Run `npm run test:login` when changing the login graph or form behavior.

Page recipes: use neutral panels and a clear Add reminder action for Your Circle;
aligned amounts, dates, units, and labeled charts for reports; labeled fields and
clear due-date/repayment choices for reminder forms; restrained badges with explicit
fictional-score labeling for The Halls; and the same field/focus/feedback patterns
for account settings. Preserve one consistent shell and keep real account data
separate from the local demo.
