# Handoff: Dashboard KPI Hierarchy

## Overview
The SabSys dashboard currently opens with **12 equally-weighted `db-kpi` tiles**
(4 Administración + 4 Ventas + 4 Compras, for a user with purchasing access)
stacked above the charts. This redesign replaces that flat block with a **three-tier
hierarchy** that gives the most important number a clear home, turns static figures
into trend metrics, and demotes operational counts to navigation — recovering
above-the-fold space for the charts and the overdue list.

**12 tiles → 1 cash band + 3 flow stats + a row of worklist chips.**

## About the Design Files
The files in `prototype/` are a **design reference created in HTML/React** — a
prototype showing intended look and behaviour, **not production code to copy
directly**. The target codebase is **Django + Bootstrap 5 + server-rendered
templates** (the SabSys ERP). The task is to recreate this design using the app's
existing patterns: Django template partials, the existing `dashboard.css` /
`components.css` conventions, and the existing `:root` design tokens. The CSS and
Django partials in this bundle (`static/`, `templates/`) are production-ready
starting points written to those conventions — wire them in, don't rebuild from
the React prototype.

## Fidelity
**High-fidelity.** Final colours, typography, spacing, and interactions. Recreate
pixel-for-pixel. Every value below is drawn from the live `components.css` /
`dashboard.css` token set — no new colours or fonts are introduced.

## Screens / Views

### Dashboard — KPI zone (top of `templates/accounts/dashboard.html`)
Replaces the three `{% include "components/_kpi_cards.html" %}` blocks under the
Administración / Ventas / Compras section headers. Everything below those blocks
(the charts, recent-invoices table, overdue/payments tables) is **unchanged** and
simply moves up.

Three stacked tiers, each preceded by a thin section header (reuse the existing
`.db-section` markup, or the `.dbx-tier` label style shown in the prototype):

**Tier 1 — Cash position band** (`components/_cash_position.html`)
A single full-width card, three zones left→right:
- **Net position** (left, min-width 300px, `border-left: 4px solid --brand-ink`):
  eyebrow "Posición neta", then the signed net figure at **2.1rem / 800 / IBM Plex
  Mono**, coloured `--pos` (#16a34a) when ≥0 or `--neg` (#b42318) when <0. Footer
  line "CxC − CxP · ▲9.2% vs. mayo" (the delta pill omitted if no prior-month data).
- **Two contributors** (centre, flex 1 each, `border-left: 1px solid --hairline-soft`):
  "Por cobrar" (blue dot `--brand-accent`) and "Por pagar" (amber dot `--warn`),
  each a 1.18rem mono value + a muted sub-caption with the open-invoice count.
  Both are links to the respective invoice lists.
- **Risk callout** (right, min-width 200px, `background: #fdeceb`): "Vencido CxC · 7"
  in `--neg`, the overdue total at 1.34rem/800, and a "Cobrar ahora →" link. Whole
  zone links to `?status=OVERDUE`. Hidden when `overdue_total` is 0.

**Tier 2 — Flow stats** (`components/_flow_stats.html`)
A 3-column grid of light cards: Facturado, Cobrado, Comprado (Comprado only with
purchasing access). Each card = uppercase label, a 1.34rem mono value, and a
**month-over-month delta pill** (green `up` / red `down`) on the same row, plus a
muted footnote. The delta is the whole point — it's what makes these worth a card
rather than folding entirely into the chart headers below.

**Tier 3 — Worklist chips** (`components/_worklist.html`)
A wrapping flex row of pill links, each = icon + label + count badge. Counts that
were tiles become navigation: Cotizaciones activas, Órdenes de venta, Órdenes de
compra (and a red `risk` chip for Vencido proveedores). Without purchasing access,
show a Clientes chip instead.

## Interactions & Behavior
- **Cash band sides + risk** are `<a>` links (cash sides → invoice lists, risk →
  `sales:invoice_list?status=OVERDUE`). Risk zone has a subtle bg-darken on hover.
- **Worklist chips**: hover lifts `translateY(-1px)` + border darken + soft shadow,
  140ms ease. `:focus-visible` ring `2px #86b7fe`. Respect `prefers-reduced-motion`
  (transitions/transform disabled — already in the CSS).
- **No new JS.** All three partials are static server-rendered markup. Chart.js
  block and the welcome-banner script in `dashboard.html` are untouched.
- **Responsive**: cash band stacks vertically <992px; flow grid → 1 column <768px;
  worklist already wraps. (Media queries included in `dashboard-cash.css`.)

## State Management
None client-side. All data comes from the Django view context. See
`views_refactor.py.md` for the exact context contract:
- **New primitives to compute** (cached): `ar_open_count`, `ap_open_count`,
  `prev_invoiced`, `prev_collected`, `prev_purchased`.
- **New per-request structures**: `flow_stats` (list), `worklist` (list), plus
  scalars `net_position_delta`, `net_position_up`, `ar_outstanding` (alias of the
  existing `outstanding`). Everything else (`net_position`, `ap_outstanding`,
  `overdue_total`, `overdue_count`, `month_*`) is already in the context today.

## Design Tokens
All already defined in `components.css :root` — reuse, do not redefine:
| Token | Value | Use |
|---|---|---|
| `--brand-ink` | `#1e2130` | net-position accent bar, count-badge text |
| `--brand-accent` | `#3f6fd6` | "Por cobrar" dot / AR series |
| `--warn` | `#d97706` | "Por pagar" dot / AP series |
| `--pos` | `#16a34a` | positive net, up-deltas |
| `--neg` | `#b42318` | negative net, overdue, down-deltas |
| `--muted` | `#6b7280` | labels |
| `--muted-2` | `#9ca3af` | sub-captions, `RD$` affix |
| `--hairline` | `#e5e7eb` | card borders |
| `--hairline-soft` | `#eef0f6` | inner dividers, count-badge bg |
| risk surface | `#fdeceb` | overdue callout / risk chip bg |

- **Type**: Manrope (UI), IBM Plex Mono + `font-feature-settings:"tnum"` (all numbers).
- **Radii**: cards 9–10px, chips/badges 999px. **Card shadow**:
  `0 1px 3px rgba(16,24,40,.05), 0 2px 14px rgba(16,24,40,.04)`.
- **Spacing**: card padding 13–18px; grid gaps 8px; tier headers 16px top / 7–8px bottom.

## Assets
None. Icons are Bootstrap Icons (already loaded in `base.html`): `bi-arrow-up-short`,
`bi-arrow-down-short`, `bi-arrow-right-short`, `bi-exclamation-triangle-fill`,
`bi-exclamation-triangle`, `bi-file-earmark-text`, `bi-cart`, `bi-clipboard-check`,
`bi-people`.

## Files
**In this bundle**
- `static/css/dashboard-cash.css` — production CSS for all three tiers (append to
  `dashboard.css` or load after it).
- `templates/components/_cash_position.html` — Tier 1 partial (+ context doc in header).
- `templates/components/_flow_stats.html` — Tier 2 partial.
- `templates/components/_worklist.html` — Tier 3 partial.
- `views_refactor.py.md` — exact `views.py` changes (new aggregates + the
  `_build_dashboard_context` method replacing `_build_kpi_stats`).
- `prototype/dashboard-kpi-redesign.html` + `prototype/design-canvas.jsx` — the
  interactive reference (Antes / Después / full reflowed dashboard).

**To edit in the target repo**
- `templates/accounts/dashboard.html` — swap the three `_kpi_cards.html` includes
  under the Administración/Ventas/Compras headers for:
  ```django
  {% include "components/_cash_position.html" %}
  {% include "components/_flow_stats.html" %}
  {% include "components/_worklist.html" %}
  ```
- `apps/accounts/views.py` — per `views_refactor.py.md`.
- `static/css/dashboard.css` (or `base.html` link list) — pull in `dashboard-cash.css`.

## Wiring order (suggested)
1. Add `dashboard-cash.css` and confirm it loads.
2. Add the three primitives + `_build_dashboard_context` in `views.py`.
3. Drop the three partials into `dashboard.html`, remove the old includes.
4. Verify both access modes: with purchasing (Comprado stat + 4 chips) and without
   (no Comprado, Clientes chip instead, risk callout still present).
