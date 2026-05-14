# Item Picker Modal Redesign — D365 Compact Lookup Style

**Date:** 2026-05-14
**Scope:** Shared item picker modal used across invoice, quotation, and sale order edit views.

---

## Goal

Redesign the item picker modal to match Microsoft Dynamics 365's "show from full list" lookup dialog aesthetic: clean corporate UI, sortable table, client-side pagination. One unified design across all three sale document types.

---

## Constraints

- Client-side only — all items remain in `window.ITEM_CATALOG` (injected at page load)
- Must integrate with existing Bootstrap 5 modal infrastructure
- Must not break `pickCatalogRow()`, `openItemPicker()`, or `initInvoiceItemFormset()` behavior
- No new Django views or URL routes required
- Shared template: `templates/invoices/partials/item_picker_modal.html`

---

## Visual Design

### Shell
- Width: 560px (`max-width`)
- Position: `margin-top: 6vh` (keep existing)
- Border: `1px solid #e0e0e0`, `border-radius: 4px`
- No colored left accent border (remove existing 4px blue left border)
- Box shadow: `0 4px 16px rgba(0,0,0,0.10)`
- Entry animation: keep existing `translateY(-14px) scale(0.98)` slide-in

### Header
- Background: `#f3f3f3`
- Title: `"Catálogo de artículos"`, font-weight 600, color `#1f1f1f`
- No icon badge
- Close button: Bootstrap `btn-close`, right-aligned
- Bottom border: `1px solid #e0e0e0`

### Search Area
- Full-width input, no `input-group-sm` wrapping complexity
- Magnifier icon (`bi-search`) inside left padding
- Placeholder: `"Buscar por nombre o código…"`
- Focus ring: `0 0 0 2px rgba(0,120,212,0.25)`, border-color `#0078d4`
- Bottom border separator: `1px solid #e0e0e0`

### Table

| Column | Width | Alignment | Font |
|--------|-------|-----------|------|
| Código | 90px | Left | IBM Plex Mono, 0.73rem |
| Artículo | flex | Left | default |
| Precio | 90px | Right | IBM Plex Mono, 0.78rem |

- Headers: sortable, uppercase, 0.68rem, color `#605e5c` (D365 gray)
- Active sort column shows `▲` or `▼` chevron, color `#0078d4`
- Default sort: name ascending
- Row height: ~36px
- No alternating stripes
- Hover: `rgba(0,120,212,0.06)` background
- Selected row: `rgba(0,120,212,0.12)` background + `3px solid #0078d4` left border
- Empty state: centered `bi-inbox` icon + "No se encontraron artículos."

### Pagination
- Page size: 20 items
- Rendered inside `#picker-pagination` div below table
- Format: `‹  1  2  3  ›` — previous/next arrows + page number buttons
- Active page: filled `#0078d4` background, white text
- Hidden when total items ≤ 20

### Footer
- Background: `#f3f3f3`, top border `1px solid #e0e0e0`
- Left: record count — `"1–20 de 48 artículos"` (IBM Plex Mono, 0.70rem, color `#605e5c`)
- Right: `Cancelar` (btn-outline-secondary btn-sm) · `Seleccionar` (btn-sm, bg `#0078d4`, white text)
- Select button disabled until a row is chosen; opacity 0.4 when disabled

---

## Behavior

### Search
- Live filter on `input` event (existing behavior, keep)
- Resets to page 1 on new query
- Search matches `item.name` and `item.code` (case-insensitive, existing)

### Sorting
- Click column header → sort ascending by that field
- Click same header again → sort descending
- Sort state tracked in `picker.sortKey` and `picker.sortDir` (`"asc"` | `"desc"`)
- Default: `sortKey = "name"`, `sortDir = "asc"`
- Sorting applied after filtering, before pagination

### Pagination
- State tracked in `picker.page` (1-indexed)
- Resets to 1 on new search or sort change
- `pickerRender()` slices filtered+sorted array: `items.slice((page-1)*20, page*20)`
- Pagination controls re-rendered on each `pickerRender()` call

### Selection
- Single click → highlight row, enable Select button (existing behavior, keep)
- Double click → select and close (existing behavior, keep)
- Modal open → reset search, reset to page 1, focus search input (existing behavior, keep)
- Modal close → clear `picker.selectedPk` (existing behavior, keep)

---

## Files Changed

| File | Change |
|------|--------|
| `templates/invoices/partials/item_picker_modal.html` | Full rewrite — D365 shell, add `#picker-pagination` div |
| `static/css/app.css` | Replace picker section (lines 970–1083) with D365 styles |
| `static/js/app.js` | Extend `pickerRender()`: add sort logic, pagination slice, render pagination controls; add `dtSort` state to `picker` object |

---

## Shared Across Documents

All three edit views already include the modal via:
```django
{% include "invoices/partials/item_picker_modal.html" %}
```
No per-document changes needed. Single template, single CSS block, single JS function.

---

## Out of Scope

- Server-side pagination or AJAX item loading
- Multi-select
- "New item" button inside picker
- Inline dropdown / typeahead on description field (Option C)
- Any change to `pickCatalogRow()`, `openItemPicker()`, or form row templates
