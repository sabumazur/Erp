# SabSys ERP

## What it is
A multi-tenant ERP system for Dominican Republic small and medium businesses. Core features: electronic fiscal invoicing (e-CF / NCF), accounts receivable, accounts payable, purchase orders, supplier invoices, payments, customers, suppliers, and DGII tax reports (606, 607, 608).

## Who uses it
Primary users are **SMB owners and accountants** in the Dominican Republic. Typical session: entering a batch of invoices, reviewing overdue AR, generating a monthly 607 report, or recording supplier payments. Sessions are **task-intensive and data-heavy** — users process hundreds of rows, not single records.

## Design intent
The app is a professional tool, not a consumer product. Design serves the work, not the brand. Speed and clarity matter more than delight.

- **Not** a marketing site
- **Not** a SaaS landing page
- **Is** a data-dense operational tool used daily by professionals

## Technology
- Django 5.2 + HTMX + Alpine.js + Bootstrap 5.3
- Static served via WhiteNoise
- No JavaScript build step — plain CSS and JS files
- Templates are Django HTML (`.html`) with `{% block %}` inheritance

## Design system (current state)

### Typography
- **Display:** Cormorant Garamond 600/700 — used for document reference numbers, auth headlines
- **Body:** Manrope 400/500/600/700/800 — all UI text
- **Monospace:** IBM Plex Mono — all financial figures, dates, codes

### Colors (CSS tokens in `static/css/components.css`)
```
--brand-ink:    #1e2130   (primary dark / sidebar background)
--brand-ink-2:  #2a3050   (hover)
--brand-accent: #3f6fd6   (links / focus rings)
--brand-soft:   #eef3fc   (light accent surface)
--pos:          #16a34a   (positive / paid)
--neg:          #b42318   (overdue / negative)
--warn:         #b45309   (outstanding / aging)
--muted:        #6b7280   (secondary text)
--muted-2:      #9ca3af   (tertiary / decorative)
--hairline:     #e5e7eb   (borders)
--hairline-soft:#eef0f6   (subtle dividers)
```

Per-module accent system (in `static/css/app.css`):
- Invoice: `#10b981` (green)
- Quotation: `#f59e0b` (amber)
- Sale Order: `#6366f1` (indigo)
- Payment: `#0891b2` (cyan)
- Customer: `#7c3aed` (violet)
- Item: `#ea580c` (orange)

### Layout
- Fixed sidebar (250px, `#1e2130`) + topbar (56px, white) + scrollable main area (`#f4f6fb`)
- Main content: `padding: 28px`
- Card chrome: `border: 1px solid #e5e7eb; border-radius: 8px; background: #fff`
- Page header: `.app-header` with title + action buttons, `border-bottom: 2px solid #1e2130`

### Key components
- **`.db-kpi`** — KPI summary card (icon + mono number + uppercase label + semantic accent stripe)
- **`.kv-card` / `.kv-row`** — detail page info panels (label-left / value-right rows)
- **`.badge-soft`** — status badges (soft tinted background + semantic text color)
- **`.doc-order-card`** — collapsible form header card with grid-rows animation
- **`.dt-slate`** — opt-in list skin for datatables
- **`status_badge.html`** — canonical status badge partial (11 document states)
- **`_kpi_cards.html`** — reusable KPI row (pass `stats` list from view)

## Register
`product` — this is app UI / dashboard / tool (design serves the product)

## Known issues (from 2026-06-17 audit)
- Side-stripe `border-left` anti-pattern on 8+ components — scheduled for replacement
- `.form-sticky-bar` class used in 4 templates but CSS is `.app-form-bar` (broken sticky bars)
- `--warn` token defined twice with conflicting values
- `#94a3b8` text color fails WCAG AA on white backgrounds
- Eyebrow labels on every section reduce hierarchy differentiation
- See `docs/ui-ux-audit-2026-06.md` for full findings
