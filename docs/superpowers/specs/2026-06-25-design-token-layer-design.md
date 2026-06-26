# Design Token Layer — SabSys ERP

**Date:** 2026-06-25  
**Approach:** CSS-only override layer (no template changes)  
**Status:** Approved

---

## Problem

SabSys has accumulated inconsistent visual values across `app.css`, `components.css`, `shell.css`, and `documents.css`:

- Border-radius: 5 different values in use (6px, 7px, 8px, 10px, 12px) with no logical scale
- Shadows: raw `rgba()` triplets scattered across ~15 selectors
- Font: Manrope — solid choice but not the SaaS data-density standard
- Primary accent: `#3f6fd6` (medium blue) — slightly undersaturated for data tables
- Money columns: no `font-variant-numeric: tabular-nums` → digits shift width per row

---

## Solution

One new file — `static/css/design-tokens.css` — loaded **first** in `base.html` (before all other app CSS). It:

1. Defines CSS custom properties for the token scale
2. Overrides the specific selectors that carry the inconsistent values
3. Loads Inter from Google Fonts

Template changes are minimal and isolated to one concern only: adding a CSS class to money `<td>` elements in 6 row partials for tabular numeral alignment. Font, radius, shadow, and color require zero template changes.

---

## Token Definitions

### Radius scale

```css
:root {
  --r-xs:  4px;   /* badges, pills, small chips */
  --r-sm:  6px;   /* inputs, ribbon buttons, small cards */
  --r-md:  8px;   /* standard cards, table wrappers, panels */
  --r-lg:  12px;  /* modals/dialogs, large overlays */
}
```

### Shadow scale

```css
:root {
  --shadow-sm: 0 1px 2px rgba(15, 23, 42, .04);
  --shadow-md: 0 1px 3px rgba(15, 23, 42, .06), 0 4px 16px rgba(15, 23, 42, .04);
}
```

### Color tokens (updated)

```css
:root {
  --brand-accent:       #2563EB;   /* was #3f6fd6 */
  --brand-accent-hover: #1d4ed8;
  --brand-accent-soft:  #eff6ff;
  --brand-accent-ring:  rgba(37, 99, 235, .25);
}
```

All other brand tokens (`--brand-ink`, `--pos`, `--neg`, `--muted`, `--hairline`, etc.) remain unchanged.

---

## Font

Switch body font from Manrope to **Inter** — the dominant B2B SaaS data-density standard. Monospace (IBM Plex Mono) and serif (Cormorant Garamond) unchanged.

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

body {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
```

The Google Fonts `<link>` preconnect tags move to `base.html`; the `@font-face` rules stay in `design-tokens.css`.

---

## Radius Application

Selectors that receive radius overrides (values change; structure unchanged):

| Selector | Old value | New token |
|----------|-----------|-----------|
| `.app-table-wrap` | `8px` | `--r-md` |
| `.settings-panel`, `.settings-aside` | `8px` | `--r-md` |
| `.erp-dialog` | `12px` | `--r-lg` |
| `.kv-card` | `12px` | `--r-lg` |
| `.doc-order-card` | `8px` | `--r-md` |
| `.doc-status-card` | `10px` | `--r-md` |
| `.doc-paper` | `10px` | `--r-md` |
| `.app-filter-panel` | `8px` | `--r-md` |
| `.dt-ribbon .btn` | `4px` | `--r-xs` |
| `.dt-filter-actions .btn` | `4px` | `--r-xs` |
| `.badge-soft` | `6px` | `--r-xs` |
| `.dt-pill` | `12px` (pill) | unchanged — pill shape intentional |
| `.form-control`, `.form-select` | (Bootstrap default) | `--r-sm` |
| `.boolean-status-card` | `8px` | `--r-md` |
| `.doc-order-card-body .form-control` | `7px` | `--r-sm` |

---

## Shadow Application

| Selector | Replacement |
|----------|-------------|
| `.db-kpi` | `--shadow-sm` |
| `.app-table-wrap` | `--shadow-sm` |
| `.settings-panel`, `.settings-aside` | `--shadow-sm` |
| `.kv-card` | `--shadow-sm` |
| `.doc-order-card` | `--shadow-md` |
| `.doc-paper` | `--shadow-md` |
| `.doc-status-card` | `--shadow-sm` |
| `.erp-dialog` | `0 8px 32px rgba(0,0,0,.16)` (keep strong — modal needs depth) |

---

## Tabular Numerals on Money Columns

Add `font-variant-numeric: tabular-nums` so currency digits align vertically across rows:

```css
/* Money/amount cells in all datatables */
.app-table-wrap td.col-amount,
.app-table-wrap td.col-total,
.app-table-wrap td.col-balance,
.app-table-wrap td.col-subtotal,
/* KV card values that contain numbers */
.kv-stat .kv-stat-n,
/* Document inline totals */
.doc-inline-tot-value {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
```

**Note:** Table cell classes (`col-amount`, `col-total`, etc.) need to be added to existing row templates. This is the **only** template change required — add the class to `<td>` elements in:
- `sales/partials/invoice_row.html`
- `sales/partials/quotation_row.html`
- `sales/partials/sale_order_row.html`
- `purchases/partials/purchase_order_row.html`
- `purchases/partials/supplier_invoice_row.html`
- `purchases/partials/supplier_payment_row.html`

---

## File Load Order in `base.html`

```html
<!-- Google Fonts preconnect -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

<!-- Token layer FIRST — before all app CSS -->
{% load static %}
<link rel="stylesheet" href="{% static 'css/design-tokens.css' %}">

<!-- existing stylesheets follow unchanged -->
<link rel="stylesheet" href="{% static 'css/shell.css' %}">
...
```

---

## Out of Scope

- Dark mode color adjustments (separate concern)
- Print stylesheet changes
- Vendor CSS (Tom Select, Bootstrap) — not touched
- Any JavaScript changes
- Any model/view/template logic

---

## Testing Checklist

- [ ] Invoice list page: KPI cards render correctly, table money columns aligned
- [ ] Invoice detail page: doc-paper card, status card, kv-card look correct
- [ ] Document create form: header card, input fields, inline totals
- [ ] Settings pages: panels render with correct radius/shadow
- [ ] Modal (HTMX edit views): correct border-radius, backdrop blur intact
- [ ] Dark mode: verify Inter renders, accent color works on dark sidebar
- [ ] Print: verify print.css still wins for print-specific rules
- [ ] Mobile (375px): no font loading flash, spacing intact
