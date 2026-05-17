# Customer Picker Modal — Design Spec

**Date:** 2026-05-17  
**Status:** Approved  
**Scope:** Invoice, Quotation, Sale Order creation forms

---

## Problem

Customer selection on sales documents uses a plain Django `<select>` widget. Creating a new customer requires leaving the form, navigating to the customer list sidebar item, creating there, returning, and re-selecting. This is too many steps during invoice entry.

## Goal

Replace the `<select>` widget on all three sales document forms (Invoice, Quotation, Sale Order) with a modal picker that supports:
1. HTMX-powered search across existing customers
2. Quick-create (name + id_type + rnc_cedula) without leaving the form

---

## Architecture

### Backend — New Endpoints

**`CustomerSearchView`** (`apps/invoices/views/htmx.py`)
- `GET invoices:customer_search` — query param `q`
- Scopes to `request.organization`
- Calls `fts_search(qs, q, fts_fields=["name"], trgm_fields=["rnc_cedula"])`
- Returns top 25 matches via `customer_picker_results.html` partial (`<tbody>` rows only)
- Returns empty-state row when `q` has no results

**`CustomerQuickCreateView`** (`apps/invoices/views/htmx.py`)
- `POST invoices:customer_quick_create`
- Validates `CustomerQuickCreateForm` (fields: `name`, `id_type`, `rnc_cedula`)
- On success: `{"pk": ..., "name": ..., "rnc_cedula": ..., "default_ncf_type": ...}` (HTTP 200)
- On failure: `{"errors": {...}}` (HTTP 422)
- Reuses existing RNC/cédula validator from `apps/invoices/validators.py`

**`CustomerQuickCreateForm`** (`apps/invoices/forms.py`)
- New `ModelForm` subclass for `Customer`
- Required fields only: `name`, `id_type`, `rnc_cedula`
- `clean_rnc_cedula`: runs checksum validator + checks uniqueness within org (view passes `organization` into form `__init__`)

### URL Routes (`apps/invoices/urls.py`)

```python
path("htmx/customers/search/",  CustomerSearchView.as_view(),      name="customer_search"),
path("htmx/customers/create/",  CustomerQuickCreateView.as_view(),  name="customer_quick_create"),
```

### Templates — New Files

**`templates/invoices/partials/customer_picker_modal.html`**
- Bootstrap modal (`#customerPickerModal`)
- Two panels toggled via `d-none`:
  - **Search panel** (default): text input with `hx-get`, `hx-trigger="input changed delay:300ms, load"`, `hx-target="#customer-picker-tbody"`; results table; "Nuevo cliente" button in footer
  - **Quick-create panel**: compact form (name, id_type, rnc_cedula); inline error display; "Volver" link back to search panel; submit button

**`templates/invoices/partials/customer_picker_results.html`**
- Renders `<tr>` rows for each customer
- Each row: `onclick="customerPickerSelect(pk, name, rnc, defaultNcf)"`
- Columns: name, RNC/cédula, email (optional), phone (optional)
- Empty-state row: "No se encontraron clientes. ¿Crear uno nuevo?" → link that calls `customerPickerShowCreate()`

### Form Widget Replacement

In `invoice_form.html`, `quotation_form.html`, `sale_order_form.html` replace:

```django
{{ form.customer }}
```

With:

```django
{# Hidden select carries the actual FK value for Django form validation #}
<div style="display:none">{{ form.customer }}</div>

{# Display + trigger #}
<div class="input-group">
  <span class="form-control customer-display text-muted fst-italic" id="customer-display-text">
    {% if form.instance.pk %}{{ form.instance.customer }}{% else %}Sin cliente seleccionado{% endif %}
  </span>
  <button type="button" class="btn btn-outline-secondary"
          onclick="openCustomerPicker()">
    <i class="bi bi-search"></i> Buscar
  </button>
</div>
{{ form.customer.errors }}
```

Modal included once per form template: `{% include "invoices/partials/customer_picker_modal.html" %}`.

---

## JavaScript (`static/js/app.js`)

### `openCustomerPicker()`
- Show `#customerPickerModal` via `bootstrap.Modal`
- Reset search input value to `""`
- Ensure search panel visible, create panel hidden
- Focus search input (triggers `load` HTMX event → initial full list)

### `customerPickerSelect(pk, name, rnc, defaultNcf)`
- Set `#id_customer` value to `pk`
- Update `#customer-display-text` → `name (rnc)` or just `name` if no rnc
- Hide modal
- Fire `change` event on `#id_customer` — existing SaleOrder department HTMX handler picks this up automatically

### `customerPickerShowCreate()` / `customerPickerShowSearch()`
- Toggle `d-none` on the two panels inside the modal

### Quick-create submit handler
- `hx-post` on the create form → `invoices:customer_quick_create`
- `htmx:afterRequest` listener on the form:
  - HTTP 200 → parse JSON → call `customerPickerSelect(...)` → close modal
  - HTTP 422 → parse `errors` → render inline under each field

---

## Data Flow Summary

```
User clicks "Buscar" button
  → openCustomerPicker() → modal opens → HTMX fires with empty q
    → CustomerSearchView returns top 25 rows
      → user types → 300ms debounce → new search → rows refresh
        → user clicks row → customerPickerSelect() → #id_customer filled → modal closes

User clicks "Nuevo cliente"
  → customerPickerShowCreate() → create panel visible
    → fills name + id_type + rnc → submit
      → CustomerQuickCreateView validates + creates
        → 200: customerPickerSelect() → modal closes
        → 422: inline errors shown in create panel
```

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| Quick-create validation fails | HTTP 422 `{"errors": {...}}`; JS renders under each field |
| Bad RNC checksum | Reuse `apps/invoices/validators.py` validator |
| Duplicate RNC in org | `clean_rnc_cedula` catches unique constraint → field error |
| Zero search results | Empty-state `<tr>` with "Crear uno nuevo?" link |
| Form submitted without customer | Django required field validation — normal error display |
| SaleOrder department reload | `change` event on `#id_customer` triggers existing HTMX |

---

## Testing

- `CustomerSearchView`: 200 response, org-scoped, FTS filters, 25-row cap, empty-state on no match
- `CustomerQuickCreateView`: creates customer + returns JSON; rejects bad RNC; rejects duplicate RNC; rejects unauthenticated
- `CustomerQuickCreateForm`: required fields enforced; optional fields not required
- Manual golden path: open invoice → picker → search → select → submit → customer saved on invoice
- Manual quick-create path: open invoice → picker → nuevo cliente → fill minimum → submit → customer created → auto-selected → submit invoice

---

## Files Changed

| Action | File |
|--------|------|
| Add | `templates/invoices/partials/customer_picker_modal.html` |
| Add | `templates/invoices/partials/customer_picker_results.html` |
| Edit | `apps/invoices/views/htmx.py` — add `CustomerSearchView`, `CustomerQuickCreateView` |
| Edit | `apps/invoices/forms.py` — add `CustomerQuickCreateForm` |
| Edit | `apps/invoices/urls.py` — add 2 routes |
| Edit | `templates/invoices/invoice_form.html` — replace customer widget, include modal |
| Edit | `templates/invoices/quotation_form.html` — same |
| Edit | `templates/invoices/sale_order_form.html` — same |
| Edit | `static/js/app.js` — add 4 JS functions + quick-create response handler |
