# IOU terminal design system

Use this guide when extending the login design to Your Circle, reports, friend
details, reminders, The Halls, and account settings. The direction is a serious
banking terminal applied to very unserious debts: restrained, precise, slightly
sarcastic, and readable. Let typography, information hierarchy, thin rules, and
small status details carry the theme.

## Source of truth and current implementation

- Visual reference: [IOU-Terminal-Login.html](../frontend/public/IOU-Terminal-Login.html).
- Integration: [TerminalLogin.jsx](../frontend/src/components/TerminalLogin.jsx)
  and [terminal login documentation](TERMINAL_LOGIN.md).
- Font license: [Iosevka SIL Open Font License](licenses/Iosevka-LICENSE.txt).

The HTML currently contains its own styles, embedded fonts, and graph code. Its
later Flexoki overrides and final `.headline-chart` rules define the current
appearance. Earlier amber colors, large corner radii, sculptural forms, and
upward-trace styles remain in the file as historical overrides; do not copy them
as the current theme.

The design is rendered in a same-origin iframe. Its styles **do not cascade into
React pages**. The signed-in account screen and the embedded local demo have not
been migrated to this visual system. `src/App.css` and `src/index.css` are not the
shared terminal theme. This document is a specification, not a loaded stylesheet
or an assertion that all pages already match.

## Palette

Colors are the implemented Flexoki dark palette. Keep backgrounds neutral and
reserve green, red, and yellow for purposeful accents.

| Role | Current value | Apply to |
| --- | --- | --- |
| Canvas / input fill | `#100f0f` | Page background, recessed input surfaces |
| Panel | `#1c1b1a` | Cards, dialogs, grouped information |
| Raised surface | `#282726` | Secondary buttons and compact controls |
| Hover / subtle separator | `#343331` | Secondary hover fill, header/footer rules |
| Standard border | `#403e3c` | Cards, inputs, dividers |
| Strong border | `#575653` | Secondary controls, dialogs, input hover |
| Primary text | `#cecdc3` | Labels and default text |
| Emphasized text | `#e6e4d9` | Headings, amounts, important names |
| Supporting text | `#b7b5ac` | Descriptions and secondary actions |
| Muted text | `#9f9d96` | Metadata, placeholders, helper text |
| Green | `#879a39` | Primary action, positive status, positive graph |
| Green hover / link | `#a0af54` | Primary hover, selected links |
| Yellow | `#d0a215` | Headline emphasis, brand accents, attention |
| Yellow detail | `#dfb431` | Small emphasized captions and links |
| Red | `#d14d41` | Negative graph, overdue status indicator |
| Red foreground | `#e8705f` | Overdue badge text |

Status treatments already used in the login:

| Treatment | Fill | Border | Text |
| --- | --- | --- | --- |
| Overdue | `#261312` | `#6c201c` | `#e8705f` |
| Warning / inline notice | `#241e08` | `#664d01` | `#eccb60` |
| Selected background option | `#1a1e0c` | `#879a39` | `#a0af54` |
| Initials avatar | `#3a2d04` | `#664d01` | `#eccb60` |

Use text and an icon or marker alongside status color. A green primary action is
not automatically a financial success state. Errors should explain the problem
and recovery action; do not copy the yellow `.error` treatment for every severity.

The existing variable names can seed a future shared stylesheet:

```css
:root {
  color-scheme: dark;
  --bg: #100f0f;
  --panel: #1c1b1a;
  --surface: #282726;
  --line: #403e3c;
  --ink: #cecdc3;
  --muted: #9f9d96;
  --green: #879a39;
  --red: #d14d41;
  --yellow: #d0a215;
  --amber: var(--yellow); /* Compatibility alias; visually yellow. */
  --mono: 'IOU Iosevka', 'Iosevka', Consolas, monospace;
  --sans: var(--mono);
}
```

## Typography and font assets

Use **Iosevka** throughout: headings, navigation, body copy, form controls, numbers,
and metadata. The internal embedded family is `IOU Iosevka`, with regular `400`
and bold `700` WOFF2 faces, normal style, and `font-display: swap`. Preserve that
family name when reusing the existing definitions. Set form controls explicitly
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

When creating shared React styles, extract the two existing embedded WOFF2 assets
into a shared font location and define `@font-face` once. That extraction is not
implemented yet; there is currently no public `/fonts` directory promised by this
guide. Avoid duplicating the multi-megabyte font data URI on every page. Retain
the font copyright and SIL license with any redistributed font files.

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

- **Primary action:** green fill, dark `#100f0f` text, green border, `6px` radius;
  hover `#a0af54`, no vertical jump. Use one dominant action per local task.
- **Secondary action:** raised neutral fill, strong border, emphasized text;
  hover fill `#343331`. Text links underline on hover with a small offset.
- **Inputs:** recessed canvas fill, standard border, emphasized value text;
  hover border `#575653`; focus border green plus `0 0 0 2px #879a391a` ring.
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
- Color is green `#879a39` or red `#d14d41` according to the decorative reference
  level. The line uses `1.35px` stroke at `.48` opacity.
- Area fill fades from `.17` to `.015` opacity. Grid lines use `.055` opacity and
  the dashed reference line `.09`, keeping the reading surface quiet.
- Occasional labels such as `CHARGER` or `$20.00` travel with points. A new label
  is added every 12 samples; label text is `10px` at `.5` opacity.
- The SVG uses a `720 × 400` viewBox. Its wrapper is positioned relative to the
  hero and resized with the heading; a horizontal mask fades its edges.
- Keep it behind text, clipped, `aria-hidden`, and `pointer-events: none`.
- Stop animation when paused, when the document is hidden, when another pattern
  is selected, or when `prefers-reduced-motion: reduce` is set. Reduced motion
  leaves a static graph. Other reduced-motion styling also removes transitions.

Other study patterns (contours, grid, signals, off) remain optional preview
controls. They are not required navigation or a production settings feature.
Do not reuse retired `.market-series` or upward-draw rules as the active ticker.
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

1. Establish a single shared token/font layer from the values above. Import it in
   the React entry point when performing that migration; iframe CSS cannot do it.
2. Create reusable Button, Input, Panel, StatusBadge, and Dialog components with
   the documented states. Scope page styles to avoid global `h1`/`label` overrides
   accidentally applying marketing dimensions to working screens.
3. Apply canvas/panel separation and the typography hierarchy first, then small
   yellow brand details and semantic green/red statuses. Keep dense data legible.
4. Use the existing authenticated API/service layer. Styling a sample record does
   not connect it to the backend or authorize changes to account/session behavior.
5. Check keyboard order, visible focus, labels, loading/errors/empty states, small
   screens, and reduced motion. Test essential text contrast on its actual surface;
   low-opacity decorative tokens are not text colors or accessibility guarantees.
6. Compare with the login reference and run the relevant frontend tests, lint,
   and build. Run `npm run test:login` when changing the login graph or auth bridge.

Page recipes: use neutral panels and a clear Add reminder action for Your Circle;
aligned amounts, dates, units, and labeled charts for reports; labeled fields and
clear due-date/repayment choices for reminder forms; restrained badges with explicit
fictional-score labeling for The Halls; and the same field/focus/feedback patterns
for account settings. Preserve one consistent shell and keep real account data
separate from the local demo.
