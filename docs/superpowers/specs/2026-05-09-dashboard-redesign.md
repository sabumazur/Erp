# Dashboard Redesign — Clean Accent

**Date:** 2026-05-09
**Status:** Approved

## Summary

Redesign the existing dashboard (`templates/accounts/dashboard.html` + `DashboardView` in `apps/accounts/views.py`) to be more visually polished. The layout and sections remain identical — only the visual treatment changes. No new data, no new views, no structural changes to the backend.

## Design Direction — Option A: Clean Accent

- **Page background:** `#f0f4f8` (light slate) so white cards visually pop
- **Font hierarchy:** Larger, bolder KPI numbers (800 weight); uppercase small-caps labels; muted subtitles
- **Card style:** `border-radius: 10px`, `box-shadow: 0 1px 3px rgba(0,0,0,.06)`, no Bootstrap `border` utility classes
- **Primary accent color:** Bootstrap blue `#0d6efd` (unchanged from current)

## Sections to Redesign

### 1. Topbar / Page Header
- Separate topbar bar with white background and bottom border, containing the page title and org name subtitle on the left, date chip and avatar on the right.
- Replaces the current inline `d-flex justify-content-between` header inside the content area.

### 2. KPI Cards (4 cards)
- **Left border:** 4px solid, color-coded per metric (blue / green / amber / red).
- **Tinted background strip on icon area removed** — instead use a ghost SVG icon watermark (opacity ~0.12) in the bottom-right corner of the card.
- **Number size:** `font-size: 22px; font-weight: 800` in the matching accent color.
- **Label:** 11px uppercase, letter-spacing, muted slate.
- **Sub-line:** small muted text (overdue count, or arrow trend text).

### 3. Stat Pills (3 cards — Clientes, Cotizaciones, Órdenes)
- **Top border:** 3px solid, color-coded (teal / indigo / orange) — distinct from KPI left borders.
- **Icon box:** 38×38px rounded square with light tinted background, matching stroke-only SVG icon.
- **Number:** `font-size: 20px; font-weight: 800`.
- **Link:** subtle outlined button `Ver →` replacing current Bootstrap `btn-outline-secondary`.

### 4. Charts (3 panels)
- Unified `panel` card: white, `border-radius: 10px`, header with title + small badge showing context ("Últimos 6 meses", "Top 6", "Facturas").
- Legend pills moved inside panel-body above chart canvas, using small colored squares.
- No changes to Chart.js data or configuration — purely container styling.

### 5. Recent Invoices Table
- **Header row:** `background: #f8fafc`, `font-size: 11px`, uppercase, `color: #64748b`.
- **Row separator:** `#f8fafc` (softer than current `table-hover`).
- **Badges:** soft background badges (e.g. `#dcfce7 / #166534` for Pagada) replacing Bootstrap solid badges.
- **Invoice number:** monospace, `color: #0d6efd`.
- **Amount column:** right-aligned, `font-weight: 700`.

### 6. Overdue Invoices + Recent Payments (2-column row)
- Same 2-column grid, same table structure.
- Overdue panel header and "Ver todas" button tinted red (`background: #fff5f5; border-color: #fecaca`).
- Payment method chips: soft-color inline badges (Transfer = sky, Cash = green, Check = slate).
- Empty state row: green check icon + "Sin facturas vencidas" text.

## What Does NOT Change

- All template context variables (`month_invoiced`, `overdue_invoices`, `chart_months`, etc.)
- All Django view logic in `DashboardView`
- Chart.js data configuration and chart types
- URL routing
- Section order and count
- Spanish i18n strings

## Files to Edit

| File | Change |
|---|---|
| `templates/accounts/dashboard.html` | Full template rewrite (HTML structure + CSS classes) |
| `templates/base.html` | May need minor tweak if topbar layout conflicts with existing `{% block content %}` padding |

## Implementation Notes

- Use inline `<style>` block in the dashboard template for all new CSS — do not touch global stylesheets.
- Keep Bootstrap 5 utility classes where they still apply; override with inline styles or scoped classes where they don't.
- All existing `{% trans %}`, `{% url %}`, and template variable references must be preserved exactly.
- The `{% block extra_js %}` Chart.js section is unchanged.
- Add `.superpowers/` to `.gitignore` if not already present.
