# Reports Templates Redesign

**Date:** 2026-05-13
**Scope:** 7 report detail templates + 2 shared partials (hub page `reports.html` excluded)

## Goal

Apply a consistent "Professional/Financial" design language across all report detail pages. Current state is inconsistent — some templates use `report_shared_styles.html`, others have inline styles; filter forms are duplicated in two templates; KPI card styles differ per page.

## Design Direction: Professional/Financial

- **Page header**: `border-bottom: 2px solid #1e2130` (sidebar accent), bold title, muted subtitle (`{report name} · {period} · {org}`), back + print buttons as `btn-outline-secondary btn-sm` on the right.
- **Filter panel**: `background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px 16px`. "Filtros" label: `9px uppercase #9ca3af`. "Consultar" button: `background: #1e2130; color: #fff` (sidebar accent).
- **KPI metric cards**: `text-align: center; border: 1px solid #e5e7eb; border-radius: 6px; background: #fff; padding: 12px`. Value: `fw-700 fs-4`. Color: green (`#16a34a`) for totals/revenue, red (`#dc2626`) for ITBIS/tax, neutral (`#111827`) for counts.
- **Table**: `border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; background: #fff`. Header: `background: #f9fafb; font-size: 10px uppercase #6b7280`. Body: alternating `#fafafa` rows. Footer: `border-top: 2px solid #1e2130 fw-700`. Amounts: `font-family: monospace`. Null values: `<span class="text-muted">—</span>`.
- **Empty state**: Bootstrap `alert-info` with `bi-info-circle` icon.
- **Error state**: Bootstrap `alert-danger`.
- **Print**: `@page { size: A4 landscape }`. Hide `.no-print`. Show `.print-header` (org name, report title, period). Remove shadows, show borders.

Hub page (`reports.html`) is **not changed** — keeps existing colorful icon cards.

## CSS Architecture

All styles live in `templates/invoices/partials/report_shared_styles.html` — included via `{% block extra_css %}` in every detail template. No changes to `app.css`.

## Files Changed

### Partials (2)

**`templates/invoices/partials/report_shared_styles.html`** — full rewrite:
- Keep `.badge-soft` and `.badge-*` class names unchanged (used by `report_statement.html` and `report_invoices_by_customer.html` — no badge markup changes needed in those templates)
- Replace `.metric-card` with `.rpt-metric-card`; replace old `.customer-block`/`.customer-avatar` with updated versions
- Add: `.rpt-header`, `.rpt-filter-panel`, `.rpt-metric-card`, `.rpt-table-wrap`, `.customer-block`, `.customer-avatar`
- Add improved print CSS

**`templates/invoices/partials/report_filter_panel.html`** — style update only:
- Replace `card shadow-sm` with new filter panel style (no shadow, `#f9fafb` bg, `#e5e7eb` border)
- Replace `btn btn-{{ btn_color }} btn-sm` submit button with `btn btn-dark btn-sm` (sidebar color); `btn_color` context variable no longer needed

### Detail templates (7)

All 7 templates get `{% include "invoices/partials/report_shared_styles.html" %}` in `{% block extra_css %}`.

| Template | Primary changes |
|---|---|
| `report_ncf_type.html` | Replace inline filter form with `report_filter_panel.html` partial; replace `bg-light` pill cards with `.rpt-metric-card`; apply `.rpt-table` to table |
| `report_itbis.html` | Replace inline filter form with `report_filter_panel.html` partial; replace `bg-light` pill cards with `.rpt-metric-card`; apply `.rpt-table` |
| `report_aging.html` | Apply new page header; apply `.rpt-table` footer accent |
| `report_sales_period.html` | Replace `bg-light` pill cards with `.rpt-metric-card`; apply `.rpt-table` footer accent |
| `report_collections.html` | Replace `bg-light` method summary cards with `.rpt-metric-card`; apply `.rpt-table` |
| `report_statement.html` | Replace inline `metric-card` styles with `.rpt-metric-card`; apply new page header; apply `.rpt-table-wrap`; strip inline `style=` from `<th>` elements (covered by `.rpt-table-wrap thead` CSS) |
| `report_invoices_by_customer.html` | Replace inline `metric-card` styles with `.rpt-metric-card`; apply new page header; apply `.rpt-table-wrap`; strip inline `style=` from `<th>` elements |

### Not changed
- `reports.html` (hub) — no changes
- All Python/Django files — no changes
- `app.css` — no changes
- Migrations — none needed

## CSS Class Reference (new system)

```css
/* Page header — bottom border using sidebar accent */
.rpt-header { border-bottom: 2px solid #1e2130; padding-bottom: 14px; margin-bottom: 18px; }

/* Filter panel */
.rpt-filter-panel { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px 16px; margin-bottom: 16px; }
.rpt-filter-label { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: #9ca3af; margin-bottom: 10px; }

/* Metric cards */
.rpt-metric-card { text-align: center; padding: 12px; border: 1px solid #e5e7eb; border-radius: 6px; background: #fff; }
.rpt-metric-value { font-size: 1.35rem; font-weight: 700; line-height: 1.2; }
.rpt-metric-label { font-size: 9px; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; margin-top: 3px; }

/* Table wrapper */
.rpt-table-wrap { border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; background: #fff; }
.rpt-table-wrap .table { margin-bottom: 0; font-size: .875rem; }
.rpt-table-wrap thead { background: #f9fafb; font-size: .7rem; text-transform: uppercase; letter-spacing: .04em; color: #6b7280; border-bottom: 1px solid #e5e7eb; }
.rpt-table-wrap tfoot { background: #f9fafb; border-top: 2px solid #1e2130; font-weight: 700; }

/* Status badges — class names unchanged from current system */
.badge-soft { font-size: .72rem; font-weight: 500; padding: .3em .65em; border-radius: 6px; display: inline-block; }
.badge-confirmed { background: #E6F1FB; color: #185FA5; }
.badge-sent      { background: #D1ECF1; color: #0C5460; }
.badge-paid      { background: #D1E7DD; color: #0A6640; }
.badge-overdue   { background: #F8D7DA; color: #842029; }
.badge-cancelled { background: #E9ECEF; color: #495057; }
.badge-invoice   { background: #E9ECEF; color: #495057; }
.badge-payment   { background: #D1E7DD; color: #0A6640; }

/* Customer block (statement / invoices-by-customer) */
.customer-block { display: flex; align-items: center; gap: 12px; padding: .85rem 1.1rem; border-radius: 8px; border: 1px solid #e5e7eb; background: #fff; margin-bottom: 1rem; }
.customer-avatar { width: 40px; height: 40px; border-radius: 50%; background: #f3f4f6; color: #374151; font-weight: 600; font-size: .9rem; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }

/* Print */
@media print {
  @page { size: A4 landscape; }
  .no-print { display: none !important; }
  .print-header { display: block !important; }
  .rpt-table-wrap { border: 1px solid #dee2e6 !important; box-shadow: none !important; }
  .rpt-badge { background: none !important; border: none !important; padding: 0 !important; color: inherit !important; font-weight: 600; }
}
.print-header { display: none; }
```

## Success Criteria

- All 7 detail pages share identical page header, filter panel, metric card, table, and empty state patterns
- No inline `style=` attributes; semantic colors expressed via Bootstrap classes (`text-danger`, `text-success`, `text-warning`) or `.rpt-metric-value` with a color utility class
- `report_ncf_type.html` and `report_itbis.html` no longer duplicate the filter form markup
- Print output is consistent across all 7 pages (A4 landscape, hidden nav/filters)
- `reports.html` hub is visually unchanged
- All existing Django template tags, `{% trans %}`, `{% url %}`, and context variables are preserved
