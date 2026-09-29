# Sport-Fabrik Inventory — Design System

Status: 27.09.2026 · Applies to every screen in `app/templates` and `app/static`.
Implementation home: `app/static/css/app.css` (section 2 holds the tokens). This file is the
*intent*; the CSS is the *implementation*. When they disagree, fix the CSS or update this file in
the same commit — never let them drift.

---

## 1. Direction in one sentence

**"Topographic precision"** — the warmth and orange of the Sport-Fabrik outlet, expressed with the
calm, exact and quiet craft of a premium tool.

The public site (sportfabrik.ch) sells *discounts*: loud percentages, big photos, light type.
The inventory app manages *stock*: people scan, count, compare and book all day. Premium here does
not mean luxury decoration. It means:

| Premium is | Premium is not |
|---|---|
| Restraint — one accent, used on purpose | Orange everywhere |
| Precision — aligned numbers, exact spacing, one type scale | 18 slightly different font sizes |
| Calm surfaces — warm paper and graphite, hairline borders | Heavy shadows, gradients on every card |
| Confidence — large clear type, obvious next step | Tiny grey text, hidden actions |
| Details that nobody notices until they are missing | Effects that everybody notices |

Personality words: **warm, exact, calm, sporty, honest.**

---

## 2. What we take from the references

### sportfabrik.ch (public site)

| Element | Observed | We keep / change |
|---|---|---|
| Typeface | Geologica, headlines weight 300, body weight 100 | **Keep Geologica.** Keep light display weight for big titles only. Body never below 400 (100 is unreadable on shop-floor screens). |
| Mixed-weight headlines | "Unser **Angebot**", "Nimm **Kontakt mit uns** auf" | **Keep as signature** for page titles and hero only (see 5.3). |
| Orange `#F39200` | Buttons, logo, contour lines | **Keep** as the only brand accent. |
| Graphite `#2E2E2E` | Text and dark footer | **Keep** as brand ink and base of the dark theme. |
| Topographic contour lines | Hero background in orange | **Keep as brand motif**, much quieter (see 8). |
| −30 / −50 / −70 badges | Yellow / red / green | **Keep the colour code.** It is the same code as the printed label rolls (`app/services/etikett.py`: 30 = gelb, 50 = rot, 70 = gruen). One system across web, labels and app. |
| Pill buttons, outline "Online mieten" | Fully rounded | **Keep pills** for buttons and chips. |
| Uppercase nav | All caps, spaced | **Change:** sentence case in the app; uppercase only for tiny eyebrows and table headers. |

### Current app (as of 27.09.2026)

Good base to keep: token architecture with light/dark/explicit theme, glass header, soft-orange
active state, pill buttons, tabular numerals in tables, `prefers-reduced-motion` support,
no external resources.

Gaps this document closes:

1. **Type scale drift** — 18 distinct font sizes (9 to 32 px, incl. 10.5, 11.5, 12.5, 13.5, 14.5).
   Weight 650 and 800 used, but only 400–800 files exist and 650 is not a real weight.
2. **Cool grey neutrals** (`#1d1d1f`, `#f2f2f5`) read "generic Apple clone", not Sport-Fabrik.
3. **Status colours missing** — only `danger`. No success, info, warning. Reductions reuse
   `--danger-text`, so a planned 30 % reduction looks like an error.
4. **Hardcoded colours** — roll dots (`#f7e23e` …), switch knob `#fff`.
5. **Five radii** (8/10/14/20/26) for a system that needs three.
6. **Symbols as icons** — ☀ 🌙 ✕ ⇅ ▲ ▼. Rendering differs per OS and they cannot be styled.
7. **Contrast** — `--border-input` is 1.7:1 on white (WCAG 1.4.11 needs 3:1 for field edges);
   body text 15 px is small for staff with little PC experience.
8. **Tone** — German strings used "du" in a few places (fixed 27.09.2026, see 12).

---

## 3. Design principles

1. **The next step is always obvious.** One primary button per view. Everything else is secondary
   or a link.
2. **Numbers are the product.** Quantities, prices, dates and EANs are always tabular, right-aligned
   in tables, and never truncated.
3. **Colour means something.** Orange = brand and "do this". Yellow/red/green = reduction stages.
   Red-orange danger = something is wrong. Nothing is coloured for decoration.
4. **Never colour alone.** Every status also has a word, number or icon.
5. **Scanner first.** A scan field keeps focus, accepts input without the mouse and confirms every
   scan visibly.
6. **Quiet by default, loud by exception.** Surfaces are calm so that warnings stand out.
7. **Same thing, same look.** A chip, a date, a quantity or a "back" link looks identical on every
   page. New pattern → add it here first.

---

## 4. Colour

All colours are CSS custom properties. Components never use raw hex values.
Neutrals are warm (a hint of the orange) instead of cool blue-grey.

### 4.1 Brand constants (never change between themes)

| Token | Value | Use |
|---|---|---|
| `--brand-orange` | `#F39200` | Logo, motif, accent source |
| `--brand-graphite` | `#2E2E2E` | Brand ink, print |

### 4.2 Semantic tokens

| Token | Light | Dark | Notes |
|---|---|---|---|
| `--bg` | `#F5F4F2` | `#121211` | Warm paper / warm graphite, never pure black |
| `--surface` | `#FFFFFF` | `#1B1B1A` | Panels, tables, cards |
| `--surface-soft` | `#FAF9F7` | `#212120` | Stat tiles, hero gradient end |
| `--surface-alt` | `#F0EEEB` | `#272725` | Table header, hover |
| `--surface-sunken` | `#EAE8E4` | `#0D0D0C` | Code, wells, drop zones |
| `--text` | `#1F1E1C` | `#F2F1EE` | 16.7:1 / 15.3:1 |
| `--text-muted` | `#5C5A56` | `#A8A59F` | Secondary text, labels — 6.9:1 / 7.0:1 |
| `--text-faint` | `#6F6C66` | `#8A8780` | Meta only (timestamps, hints) — ≥ 4.5:1 on surface |
| `--border` | `#E4E1DC` | `#2C2B29` | Hairlines, dividers |
| `--border-strong` | `#D3CFC9` | `#3A3936` | Table header line, hover borders |
| `--border-input` | `#948F87` | `#6B6760` | Field edges — 3.2:1 / 3.1:1 (WCAG 1.4.11) |
| `--accent` | `#F39200` | `#F39200` | Primary button fill, focus, active marker |
| `--accent-hover` | `#FF9F1A` | `#FFA42E` | |
| `--accent-pressed` | `#DB8300` | `#DB8300` | |
| `--accent-on` | `#1F1405` | `#1F1405` | Text on orange — 7.7:1. **Never white on orange** (2.4:1). |
| `--accent-text` | `#8A5300` | `#FFB45C` | Orange-family text and links — 6.3:1 / 9.8:1 |
| `--accent-soft-bg` | `#FFF4E5` | `rgba(243,146,0,.14)` | Active nav, selected row |
| `--accent-soft-border` | `#FFDCAC` | `rgba(243,146,0,.34)` | |
| `--focus-ring` | `rgba(243,146,0,.32)` | `rgba(243,146,0,.40)` | Plus solid 2 px outline (see 11) |

**Rule:** orange (`--accent`) is never used as text on light backgrounds. Use `--accent-text`.

### 4.3 Status

| Status | Text | Background | Border | Dark text | Use |
|---|---|---|---|---|---|
| `danger` | `#B42318` | `#FEF1EF` | `#F6C9BD` | `#FF8F7A` | Errors, failed booking, delete |
| `success` | `#1E6B3F` | `#EBF5EE` | `#BFE0CB` | `#6FCF97` | Booked, saved, arrived |
| `warning` | `#7A5A00` | `#FFF6D6` | `#F0DC94` | `#F5D36B` | Needs attention, not wrong (unknown layout, missing EAN) |
| `info` | `#2B5F8E` | `#EDF3F9` | `#C4D8EC` | `#8AB8E6` | Neutral facts, filter active, expected delivery |

Dark backgrounds: the text colour at 14–16 % alpha; borders at 34 %.
All text/background pairs above are ≥ 5.8:1.

### 4.4 Reduction stages (one code everywhere)

The stage colours match the physical label rolls and the public website badges. They are **never**
used for anything else, and danger is **never** used for a reduction.

| Stage | Roll / print colour (`--roll-*`) | Chip text | Chip background (light) |
|---|---|---|---|
| −30 % | `#F7E23E` yellow | `#5C4A00` | `#FFF3B8` |
| −50 % | `#E3342A` red | `#9E1F17` | `#FDE3E1` |
| −70 % | `#58B24B` green | `#23612A` | `#E3F3E0` |

Chip = tinted background + dark text "−30 %" + 10 px dot in the roll colour (the dot is what staff
match to the roll in their hand). Dark theme: roll colour at 16 % alpha as background, roll colour
lightened as text.

---

## 5. Typography

### 5.1 Typeface

**Geologica** only, self-hosted from `/static/fonts` (rule: no CDN). Fallback:
`-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif`.
Monospace (EAN, article numbers in edit fields, raw OCR text): `ui-monospace, SFMono-Regular,
Menlo, Consolas, monospace`.

Allowed weights: **300** (display only), **400**, **500**, **600**, **700**.
No 650, no 800 in UI. `geologica-300.ttf` is installed (27.09.2026, Google Fonts, same release as
the other files) and registered in `app.css`; use it only for display titles.

### 5.2 Type scale (fixed steps, ratio ≈ 1.2)

| Token | Size / line-height | Weight | Tracking | Use |
|---|---|---|---|---|
| `--fs-display` | clamp(36px, 4vw, 52px) / 1.05 | 300 + 700 | −0.035em | Dashboard greeting, login title |
| `--fs-h1` | clamp(28px, 3vw, 36px) / 1.1 | 600 (or 300 + 700) | −0.028em | Page title |
| `--fs-h2` | 22px / 1.25 | 600 | −0.02em | Panel title |
| `--fs-h3` | 18px / 1.3 | 600 | −0.01em | Sub-section |
| `--fs-body` | **16px** / 1.55 | 400 | 0 | Default text, inputs |
| `--fs-sm` | 14px / 1.45 | 400/500 | 0 | Tables, secondary text, buttons |
| `--fs-xs` | 13px / 1.4 | 500/600 | 0.01em | Labels, meta, chips |
| `--fs-micro` | 12px / 1.3 | 600 | 0.08em, uppercase | Eyebrow, table header only |
| `--fs-metric` | clamp(36px, 3.6vw, 48px) / 1 | 600 | −0.04em | KPI numbers |

Nothing below 12 px. Nothing between steps. Line length for prose: max 68ch.

### 5.3 Signature: the mixed-weight title

Borrowed from the website and made precise. The quiet part is weight 300, the key word is 700,
same size, same colour:

```html
<h1 class="title-mixed">Guten Tag, <strong>SF2</strong></h1>
```

Use only for display and page titles, at most once per page, and only when the bold part carries
the meaning (the store, the article, the count). Everywhere else headings are plain 600.

### 5.4 Numbers and formats

- `font-variant-numeric: tabular-nums` on every number (tables, metrics, quantities, prices, dates).
- Right-align numbers in tables; the header aligns with its column.
- Format with `Intl` and the UI language: `de-CH`, `fr-CH`, `en-GB` (as `ausbuchen.js` does).
  Examples de: `1’250 Stk.`, `CHF 49.90`, `27.09.2026`, `14:05`.
- Negative quantities use a real minus `−` (U+2212), not a hyphen. Same for "−30 %".
- Units get a non-breaking space: `30 %`, `12 Stk.`.
- EAN: monospace, grouped only for reading (`7 612345 678904`), stored ungrouped.
  Internal EANs (GS1 20–29) carry an "intern" chip.

---

## 6. Space, size, shape

### 6.1 Spacing — 4 px base

`--space-1` 4 · `--space-2` 8 · `--space-3` 12 · `--space-4` 16 · `--space-5` 20 · `--space-6` 24 ·
`--space-8` 32 · `--space-10` 40 · `--space-12` 48 · `--space-16` 64

Rules: related items 8–12, groups 24, sections 40–48. Panel padding 24 (mobile 20).
Vertical rhythm comes from spacing tokens, not from `<br>` or ad-hoc margins.

### 6.2 Radius — three steps plus pill

| Token | Value | Use |
|---|---|---|
| `--radius-sm` | 8px | Inputs, small tiles, menu items, table wrap on mobile |
| `--radius-md` | 12px | Tables, menus, notices, stat tiles, dialogs |
| `--radius-lg` | 20px | Panels, metric cards, hero |
| `--radius-pill` | 999px | Buttons, chips, segmented controls, store pill |

Nested corners: inner radius = outer radius − padding (panel 20 with 12 padding → inner 8).

### 6.3 Elevation — borders first, shadow second

| Level | Shadow | Use |
|---|---|---|
| 0 | none, 1 px `--border` | Default panels, tables |
| 1 | `0 1px 2px rgb(31 30 28/.04), 0 1px 3px rgb(31 30 28/.04)` | Cards, secondary buttons |
| 2 | `0 2px 6px rgb(31 30 28/.05), 0 18px 48px rgb(31 30 28/.12)` | Menus, dialogs, popovers |

Shadows use warm graphite, not pure black. Only interactive cards lift on hover (−2 px, level 1→2).

### 6.4 Sizes

- Touch/click targets ≥ 44 × 44 px (buttons, table row actions, chips that act).
- Controls: default height 44 px; large 52 px (scan field, primary action in booking flows).
- Header height 64 px. Content max 1280 px; wide pages (articles, invoice check) 1680 px.
- Breakpoints (unchanged, keep exactly these): 560, 760, 900, 1100 px.

---

## 7. Iconography

- One icon set: **Lucide** (ISC licence), copied into `/static/img/icons.svg` as a sprite —
  no CDN, no icon font.
- 24 px grid, stroke 1.75 px, round caps and joins, `currentColor`.
- Sizes: 16 (inline in text/buttons), 20 (nav, table actions), 24 (empty states, headers).
- Icon + label for every action. Icon-only only for universal actions (close, more, sort) and then
  with `aria-label` and a tooltip.
- Decorative icons get `aria-hidden="true"`.
- Replace: ☀/🌙 → `sun`/`moon`, ✕ → `x`, ⇅ ▲ ▼ → `chevrons-up-down`/`chevron-up`/`chevron-down`.
- No emoji anywhere in the UI.

---

## 8. Brand motif and logo

### 8.1 Contour lines

The website hero uses orange topographic lines. In the app they become a quiet watermark:

- Own local SVG (`/static/img/contours.svg`), drawn for the app — not a copy of the website image.
- 1 px strokes, `--brand-orange` at 10–16 % opacity (dark theme 12–18 %), no fills, no labels.
- Allowed places only: login background, dashboard hero corner, empty states.
- Never behind tables, forms, numbers or text blocks. Never animated.

### 8.2 Logo

- Existing `sportfabrik-logo.png` (orange wordmark). Replace with SVG when available.
- Minimum width 120 px. Clear space = height of the "S" on all sides.
- Lock-up in the header: logo · hairline divider · `INVENTORY` in `--fs-micro`, tracking 0.18em,
  `--text-faint`. No other text next to the logo.
- Never recolour, stretch, outline or place on orange.

---

## 9. Layout patterns

### 9.1 App shell

Fixed left sidebar from 901 px (252 px, `--surface`, hairline right border): stacked logo
(SPORT-FABRIK above INVENTORY) · navigation · at the bottom the store pill (which branch you book
in) and the account avatar. Below 901 px: sticky glass top bar (surface at 72 % +
`backdrop-filter: saturate(180%) blur(20px)`) with logo, store pill, avatar and "Menü". The store
pill is always visible — booking in the wrong branch is the most expensive mistake in the app.

### 9.2 Page anatomy (every page, same order)

1. Eyebrow (optional, section name) → 2. Title → 3. One-line purpose in `--text-muted` →
4. Primary action (right of title on desktop, full width under it on mobile) → 5. Filters →
6. Content (table / form / cards) → 7. Secondary actions and danger zone at the end.

### 9.3 Dashboard

Greeting (mixed-weight title) → shortcuts (max 5, equal size) → 4 metrics → three small insight
panels (sales of the last 14 days as bars, stock by reduction stage as a stacked bar, best sellers
of the week) → two columns "Anstehend" and "Aktuelles" (grouped by day). Metrics show one number,
one label, one link.

Charts on the dashboard are allowed since 29.09.2026 (decision: user), under three limits: only
plain bars from tokens (no axes, no chart library; the only legend is the stage list, which repeats every number as text); every value is
also written as text next to or in the bar (`title`, legend numbers); reduction stages use the
roll colours of §4.4 and nothing else does. Detailed charts and periods stay in Statistiken.

### 9.4 Grid

12 columns, gutter 24 px (16 px under 760). Forms use 1–3 columns, never more; fields that belong
together (Farbe + Grösse, Menge + Einheit) share a row.

---

## 10. Components

States for every interactive component: default · hover · active/pressed · focus-visible ·
disabled · loading. Transitions 160 ms (see 13).

### 10.1 Buttons

| Variant | Look | Use |
|---|---|---|
| Primary | `--accent` fill, `--accent-on` text, 600 | The one main action per view |
| Secondary | `--surface`, `--border-input` edge, `--text` | Other actions |
| Ghost | no fill, `--accent-text` text; hover `--surface-alt` | Tertiary, in tables and menus |
| Danger | Secondary shape, `--danger` text and border; hover danger bg | Delete, storno. Never a filled red button. |

- Pill shape, height 44 (52 in booking flows), padding 0 20 px, `--fs-sm` 600.
- Label = verb + object: "Ware einbuchen", "Umlagerung speichern". Not "OK", not "Weiter".
- Pressed: `scale(.98)`. Loading: spinner replaces the icon, label stays, button disabled,
  width does not change.
- Disabled: 40 % opacity and a reason nearby ("Erst Filiale wählen").

### 10.2 Inputs and forms

- Label above the field (`--fs-xs` 600, `--text-muted`), never placeholder-only.
- Field: height 44, `--radius-sm`, `--border-input`, `--fs-body` (16 px also prevents iOS zoom).
- Focus: `--accent` border + 4 px `--focus-ring`.
- Helper text below in `--fs-xs` `--text-faint`. Error replaces helper, `--danger` text with
  `alert-circle` icon, field border `--danger`. Validate on blur and on submit, not on every key.
- Required fields are the norm; mark the *optional* ones ("optional"), e.g. EAN, EK.
- `<select>` uses the custom chevron; checkboxes use `accent-color: var(--accent)`.

### 10.3 Scan field (signature component)

- Large (52 px, `--fs-h3`), full width, `inputmode="numeric"` where only EAN is valid,
  `autocomplete="off"`, autofocus, barcode icon left.
- After a scan: field clears, focus stays, the result appears as a row directly under the field
  with a 600 ms `--success-bg` flash. Unknown code: `--warning` row with "Artikel anlegen" action.
- The last 5 scans stay visible so staff can check without looking away from the scanner.

### 10.4 Tables

- Wrapper: `--surface`, 1 px `--border`, `--radius-md`, sticky header, max-height 68vh.
- Header: `--surface-alt`, `--fs-micro` uppercase, `--text-muted`, 1 px `--border-strong` below.
- Row height 48 px (compact option 40 px), `--fs-sm`, 16 px cell padding, hairline dividers,
  no zebra stripes. Hover `--row-hover`.
- Selected row: `--accent-soft-bg` + 3 px inset left bar in `--accent`.
- Numbers right-aligned and tabular; text left; actions right, ghost buttons.
- Sort: header is a `<button>` with chevron icon and `aria-sort`.
- Empty table: centred empty state (10.9), not an empty grid.
- Mobile (< 760): tables become stacked cards only for the main lists (Bestand, Artikel);
  wide tables scroll horizontally inside the wrapper, never the page.

### 10.5 Chips and badges

- Height 24 (acting chips 32 with 44 px hit area), pill, `--fs-xs` 600, 8–10 px padding.
- Types: status (4.3), reduction stage (4.4), neutral (`--surface-alt`, `--text-muted`),
  "intern" (EAN), store code (SF1–SF4 in `--fs-micro`).
- A chip always has text; the dot or icon is extra.

### 10.6 Metric card

Label (`--fs-sm` 500 muted) → number (`--fs-metric`, tabular) → context line or link.
Unknown value shows `—`, loading shows a skeleton bar, never `0`.

### 10.7 Notices

`--radius-md`, 16 px padding, status background and border, icon left, one short sentence,
optional action right. Types map to 4.3. The active-filter notice (Filter aus der Übersicht) is
`info`, 16 px 600, with "Filter entfernen".

### 10.8 Menus, dialogs, confirmations

- Menus: `--surface`, `--radius-md`, level 2 shadow, 8 px padding, items 44 px.
- Dialogs: max 520 px, `--radius-lg`, title + one sentence + actions right (secondary left of
  primary). Escape and backdrop close non-destructive dialogs only.
- Destructive or irreversible (Ausbuchen, Stornieren, Löschen): dialog names the object and the
  consequence ("12 Stk. Salomon XA Pro werden in SF2 ausgebucht."), the confirm button repeats
  the verb ("Ausbuchen").

### 10.9 Empty, loading, error states

- Empty: 24 px icon, one sentence what is missing, one action. Optional contour motif.
- Loading: skeleton bars in `--surface-alt` for tables and metrics; spinner only inside buttons.
  Status text in `aria-live="polite"` region (existing `#status`).
- Error: what happened + what to do + "Erneut versuchen". Never raw stack traces or HTTP codes
  alone.

### 10.10 Navigation

- Sidebar list, order fixed by `docs/redesign-2026-09-29.md`; groups expand in place (chevron
  turns), children are indented behind a hairline. A group holding the active page is open and
  its label is `--accent-text`.
- Active page: `--accent-soft-bg` fill, `--accent-text`, 600.
- Mobile (< 901): burger opens full-width sheet; groups are always open, shown as small uppercase
  headings; store pill stays in the header.

---

## 11. Accessibility and shop-floor rules

- Contrast: text ≥ 4.5:1, large text and UI edges ≥ 3:1 — tokens above are pre-checked;
  new colours must be checked before use.
- Focus: `:focus-visible` → 2 px solid `--accent` outline, 2 px offset (plus ring on fields).
  Never remove focus without a replacement.
- Full keyboard flow for booking: Tab order follows reading order, Enter submits, Escape cancels.
- Every icon-only control has `aria-label`; every status update is announced via `aria-live`.
- Minimum body 16 px; users may zoom to 200 % without horizontal page scroll.
- Colour never alone (stage chip shows "−30 %", error shows icon + text).
- Language: `<html lang>` follows the selected language (DE/FR/EN).

---

## 12. Voice and microcopy

- All UI text through i18n keys (DE default, FR, EN). Supplier article data is never translated.
- Sentence case everywhere ("Ware einbuchen", not "Ware Einbuchen" or "WARE EINBUCHEN").
- Short, concrete, active: "3 Artikel ohne EAN" instead of "Es wurden Artikel gefunden, die keine
  EAN aufweisen".
- Buttons: verb + object. Errors: cause + fix.
- **Address form (decided 27.09.2026): formal.** German uses "Sie"/"Ihr", French "vous"/"vos".
  Prefer impersonal wording where it reads naturally ("Werte prüfen"); when addressing the user,
  always "Sie". Never "du"/"tu", even though the public website uses "du".

---

## 13. Motion

Motion explains change; it never decorates. No scroll-reveal, no parallax, no animation library.

| Token | Duration | Easing | Use |
|---|---|---|---|
| `--fast` | 160 ms | `cubic-bezier(.32,.08,.24,1)` | Hover, press, colour, focus |
| `--base` | 220 ms | same | Menus, chips, row insert |
| `--slow` | 280 ms | same | Dialogs, card lift, sheet |

- Enter: fade + 4 px translate. Exit is faster than enter (≈ 70 %).
- Animate only `opacity` and `transform`.
- Success flash on scan/booking: 600 ms background fade, once.
- `prefers-reduced-motion: reduce` → all durations ≈ 0, no transforms (already in app.css).

---

## 14. Dark theme

- Warm graphite (`#121211`), never pure black; surfaces get lighter with elevation.
- Orange stays `#F39200`; orange text uses `#FFB45C`.
- Shadows are stronger but used less; borders carry structure.
- Theme choice: system default, override stored per device (`sportfabrikTheme`), toggle with
  sun/moon icon + label.
- Printed labels are unaffected by theme.

---

## 15. Do and don't

| Do | Don't |
|---|---|
| One orange primary button per view | Two primary buttons side by side |
| `--accent-text` for orange text | `#F39200` text on white |
| Stage chips yellow/red/green with "−30 %" text | Red danger style for reductions |
| Tabular, right-aligned numbers | Centred numbers or proportional digits |
| Scale steps from 5.2 | 13.5 px, 14.5 px, 650 weight |
| SVG icons from the sprite | Emoji or Unicode symbols as icons |
| Label above field + helper below | Placeholder as the only label |
| Contour motif on login/hero/empty states | Motif behind data |
| Self-hosted fonts and assets | Any CDN (Google Fonts, icon CDNs, GSAP) |

---

## 16. Pre-delivery checklist (every UI change)

- [ ] Only tokens used — no raw hex, px sizes from the scale, spacing from `--space-*`
- [ ] One primary action; button labels are verb + object
- [ ] All states: hover, focus-visible, active, disabled, loading, empty, error
- [ ] Numbers tabular and formatted for the current language
- [ ] New texts in `de.json`, `fr.json`, `en.json`
- [ ] Light and dark theme checked; contrast ≥ 4.5:1 text, ≥ 3:1 edges
- [ ] Keyboard only: reachable, visible focus, Enter/Escape work
- [ ] Widths 375, 768, 1024, 1440 — no horizontal page scroll
- [ ] Targets ≥ 44 px; scan field keeps focus after a scan
- [ ] No external requests (DevTools network tab shows only localhost)
- [ ] CSS cache-bust version bumped in templates

---

## 17. Migration plan for `app.css`

Ordered by value per effort. Each step is a small, reviewable commit; no step changes behaviour.

1. **Tokens:** add status, stage/roll, spacing, type-scale and `--brand-*` tokens; switch neutrals
   to the warm values; raise `--border-input` to 3:1. Replace hardcoded roll and switch colours.
2. **Type scale:** map the 18 sizes to the 9 steps (10.5/11/11.5 → 12; 12.5/13/13.5 → 13 or 14;
   14.5/15 → 14 or 16; 17/19 → 18; 24/27/32 → h2/h1/metric). Body to 16 px. Remove 650/800.
3. **Radii:** 10 → 8, 14 → 12, 26 → 20.
4. **Reductions:** `.reduktion-stufe` and roll hints use stage chips instead of `--danger-text`.
5. **Icons:** add Lucide sprite; replace ☀ 🌙 ✕ ⇅ ▲ ▼.
6. **Signature details:** mixed-weight title on dashboard and login (font already installed);
   contour SVG on login and dashboard hero.
7. **Scan field and state patterns** (10.3, 10.9) when the booking pages are next touched.

---

## 18. Decisions and rejected options

- The ui-ux-pro-max generator suggested Cormorant + Montserrat, a gold accent, "Liquid Glass" and
  GSAP scroll reveals. **Rejected:** a serif/gold luxury look does not fit an outlet brand;
  extra fonts and GSAP break the no-CDN rule and add weight; scroll reveals slow down a work tool.
  Kept from it: warm-stone neutrals, restrained motion, the pre-delivery checklist.
- Glass is used only for the sticky header, where content scrolls behind it.
- Colour code for reductions follows the physical label rolls (`etikett.py`) — change both or
  neither.
