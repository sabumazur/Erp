# Customer Full-Page Form — Design Spec

**Date:** 2026-05-29  
**Status:** Approved for implementation

---

## Context

Customer create was modal-only (no dedicated URL). Customer edit had dual-mode: HTMX → modal, direct GET → full page. The form has 15 fields in 4 sections (General, Contacto, Dirección, Facturación) — too much for a modal. Supplier CRUD is coming next and needs the same pattern; establishing full-page customer form first sets the template.

Goal: Odoo-style full-page create and edit, two-column layout, no modal, smart buttons on edit.

---

## Layout

Two-column Bootstrap grid (`col-md-8` / `col-md-4`):

```
┌─ Breadcrumb: Clientes › [Nuevo | customer.name] ───── [Guardar] [Cancelar] ─┐
├─ Smart buttons (edit only) ────────────────────────────────────────────────┤
│  [12 Facturas] [8 Pagos] [RD$45k Balance] [3 Deptos]                       │
├─────────────────────────────────────────┬──────────────────────────────────┤
│  col-md-8 (left)                        │  col-md-4 (right)                │
│  § Datos generales                      │  § Facturación                   │
│    name, id_type, rnc_cedula            │    default_ncf_type              │
│    RNC lookup HTMX widget               │    payment_term                  │
│  § Contacto                             │    credit_limit                  │
│    email, phone                         │  § Notas                         │
│    contact_name, contact_number         │    notes                         │
│  § Dirección                            │  § Razón de cambio (edit only)   │
│    address, city, province, country     │    change_reason                 │
└─────────────────────────────────────────┴──────────────────────────────────┘
```

RNC lookup behavior unchanged: `hx-get="/sales/rnc-lookup/"`, `hx-trigger="blur"`, fills name field on success, shows spinner, renders `#rnc-lookup-result`.

Save/Cancel buttons in page header (sticky app-header pattern used elsewhere). No sticky footer.

Smart buttons render only when `object.pk` exists (edit mode). Each links to `sales:customer_detail` (which already shows invoices, payments, aging, departments) since the list views do not currently support customer-scoped URL filters:
- Facturas count → `customer_detail` URL
- Pagos count → `customer_detail` URL
- Balance (outstanding) → display only, no link
- Deptos count → `customer_detail` URL

Smart button stats computed in `CustomerUpdateView.get_context_data()`: invoice count (non-draft/cancelled), payment count, outstanding balance (invoiced − paid), department count (active). Reuse the same queryset logic from `CustomerDetailView`.

---

## Backend Changes

### New: `CustomerCreateView`

```python
class CustomerCreateView(ERPBaseViewMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "sales/customer_form.html"
    required_module = "sales"
    # no admin_required — matches existing CustomerListView and CustomerUpdateView

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs

    def form_valid(self, form):
        form.instance.organization = self.request.organization
        customer = form.save()
        messages.success(self.request, f"Cliente {customer.name} creado.")
        return redirect("sales:customer_detail", pk=customer.pk)
```

### Modified: `CustomerUpdateView`

Remove all HTMX dual-mode logic:
- Remove `if request.htmx` branch in `get()`
- Remove `_hx_target` hidden field handling in `post()`
- Remove `HX-Trigger` response headers
- Always render `customer_form.html` full page
- Add smart buttons context: invoice count, payment count, outstanding balance, department count (reuse annotations already in `CustomerDetailView`)

### Modified: `CustomerListView`

- Remove `post()` method entirely
- Remove `CustomerForm` from `get_context_data()`

### URL

```python
path("customers/create/", CustomerCreateView.as_view(), name="customer_create"),
# existing: customers/<uuid:pk>/edit/ — URL unchanged, view simplified
```

---

## Template Changes

### `customer_form.html` (rewrite)

- Replace single-column crispy form with two-column Bootstrap grid
- Header: breadcrumb (`Clientes › <name or "Nuevo">`) + Save/Cancel buttons
- Smart buttons bar: conditional on `object.pk`
- Left col: `§ Datos generales`, `§ Contacto`, `§ Dirección` as white cards
- Right col: `§ Facturación`, `§ Notas`, `§ Razón de cambio` (edit only) as white cards
- Render crispy form fields individually per section (not `{% crispy form %}` wholesale)

### `customer_list.html`

- Remove `#customerModal` Bootstrap modal markup
- Change "Nuevo cliente" button: `<a href="{% url 'sales:customer_create' %}" class="btn ...">Nuevo cliente</a>`

### `partials/customer_row.html`

- Change Edit kebab item: remove `hx-get`, add plain `href="{% url 'sales:customer_edit' row.pk %}"`

### Delete: `partials/customer_modal_form.html`

Verify no other template includes it, then delete.

---

## `CustomerForm` layout adjustment

`CustomerForm` currently uses `crispy_forms` `Layout` that groups all fields for modal rendering. With full-page two-column layout, fields will be rendered individually via `{{ form.field_name }}` in the template rather than relying on the crispy `Layout`. The `Layout` in the form can be removed or kept as a fallback — it won't be used by the new template.

Keep form validation logic (RNC/cedula, phone, duplicate check) unchanged.

---

## After-Save Redirect

Both create and edit redirect to `sales:customer_detail` with the customer's pk. Consistent with how invoice/quotation create redirects work in this codebase.

---

## Verification

1. `pytest apps/sales/` — all existing customer tests pass
2. Navigate to `/ventas/clientes/` — "Nuevo cliente" button links to full page (not modal)
3. Fill form, submit → redirected to customer detail
4. Edit from kebab → full page edit, save → back to detail
5. RNC field blur → triggers lookup, fills name field
6. Edit page smart buttons show correct counts, links work
7. Duplicate RNC → form error displayed inline (no SweetAlert needed since full page)
8. HTMX quick-create from invoice/PO item picker unaffected (`CustomerQuickCreateView` unchanged)
