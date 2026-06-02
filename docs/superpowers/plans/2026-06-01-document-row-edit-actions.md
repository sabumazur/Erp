# Document Row Edit Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make document list row actions match the actual edit behavior so the three-dot `Editar` action appears only when the document can open the edit form.

**Architecture:** The edit URL routes already point to form views, but each update view redirects non-editable documents back to the detail page. The row dropdowns should use the same lifecycle rule as the views: only `DRAFT`/`is_editable` documents expose `data-action="edit"`, while non-editable rows expose `Ver` and any valid lifecycle actions.

**Tech Stack:** Django templates, Django template rendering tests, pytest.

---

### Findings

- `sales:invoice_edit`, `sales:quotation_edit`, and `sales:sale_order_edit` are wired to `InvoiceUpdateView`, `QuotationUpdateView`, and `SaleOrderUpdateView`.
- `purchases:po_edit` and `purchases:supplier_invoice_edit` are wired to `PurchaseOrderUpdateView` and `SupplierInvoiceUpdateView`.
- Each update view calls a `_get_*` helper and redirects to the detail page when `not document.is_editable`.
- `SalesDocument.is_editable` and `PurchaseDocument.is_editable` currently mean `status == DRAFT`.
- The current dropdown change made `Editar` visible for non-draft rows, so clicking it hits the edit URL and then redirects to detail. That is expected backend behavior, but confusing UI behavior.

### Task 1: Add Row Action Tests

**Files:**
- Modify: `apps/core/tests/test_datatable_templates.py`

- [ ] **Step 1: Add document row edit-action assertions**

Append these tests to `apps/core/tests/test_datatable_templates.py`:

```python
def test_sales_document_rows_show_edit_only_for_drafts():
    templates = [
        "sales/partials/invoice_row.html",
        "sales/partials/quotation_row.html",
        "sales/partials/sale_order_row.html",
    ]

    for template_name in templates:
        draft_html = render_to_string(template_name, {"row": _row(status="DRAFT")})
        confirmed_html = render_to_string(template_name, {"row": _row(status="CONFIRMED")})

        assert 'data-action="edit"' in draft_html
        assert 'data-action="edit"' not in confirmed_html
        assert 'data-action="view"' in confirmed_html


def test_purchase_document_rows_show_edit_only_for_drafts():
    templates = [
        "purchases/partials/purchase_order_row.html",
        "purchases/partials/supplier_invoice_row.html",
    ]

    for template_name in templates:
        draft_html = render_to_string(template_name, {"row": _row(status="DRAFT")})
        confirmed_html = render_to_string(template_name, {"row": _row(status="CONFIRMED")})

        assert 'data-action="edit"' in draft_html
        assert 'data-action="edit"' not in confirmed_html
        assert 'data-action="view"' in confirmed_html
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
pytest apps/core/tests/test_datatable_templates.py -q
```

Expected result: the new tests fail because confirmed rows still render `data-action="edit"`.

### Task 2: Align Sales Row Dropdowns With Editability

**Files:**
- Modify: `templates/sales/partials/invoice_row.html`
- Modify: `templates/sales/partials/quotation_row.html`
- Modify: `templates/sales/partials/sale_order_row.html`

- [ ] **Step 1: Wrap invoice edit action with the draft condition**

In `templates/sales/partials/invoice_row.html`, change the edit menu item to:

```django
{% if row.status == 'DRAFT' %}
<li>
  <a class="dropdown-item" href="{% url 'sales:invoice_edit' row.pk %}" data-action="edit">
    <i class="bi bi-pencil me-2"></i>{% trans "Editar" %}
  </a>
</li>
{% endif %}
```

- [ ] **Step 2: Wrap quotation edit action with the draft condition**

In `templates/sales/partials/quotation_row.html`, change the edit menu item to:

```django
{% if row.status == 'DRAFT' %}
<li>
  <a class="dropdown-item" href="{% url 'sales:quotation_edit' row.pk %}" data-action="edit">
    <i class="bi bi-pencil me-2"></i>{% trans "Editar" %}
  </a>
</li>
{% endif %}
```

- [ ] **Step 3: Wrap sale order edit action with the draft condition**

In `templates/sales/partials/sale_order_row.html`, change the edit menu item to:

```django
{% if row.status == 'DRAFT' %}
<li>
  <a class="dropdown-item" href="{% url 'sales:sale_order_edit' row.pk %}" data-action="edit">
    <i class="bi bi-pencil me-2"></i>{% trans "Editar" %}
  </a>
</li>
{% endif %}
```

### Task 3: Align Purchase Row Dropdowns With Editability

**Files:**
- Modify: `templates/purchases/partials/purchase_order_row.html`
- Modify: `templates/purchases/partials/supplier_invoice_row.html`

- [ ] **Step 1: Wrap purchase order edit action with the draft condition**

In `templates/purchases/partials/purchase_order_row.html`, change the edit menu item to:

```django
{% if row.status == 'DRAFT' %}
<li><a class="dropdown-item" href="{% url 'purchases:po_edit' row.pk %}" data-action="edit">
  <i class="bi bi-pencil me-2"></i>{% trans "Editar" %}</a></li>
{% endif %}
```

- [ ] **Step 2: Wrap supplier invoice edit action with the draft condition**

In `templates/purchases/partials/supplier_invoice_row.html`, change the edit menu item to:

```django
{% if row.status == 'DRAFT' %}
<li><a class="dropdown-item" href="{% url 'purchases:supplier_invoice_edit' row.pk %}" data-action="edit">
  <i class="bi bi-pencil me-2"></i>{% trans "Editar" %}</a></li>
{% endif %}
```

Keep the existing `Reabrir` option for cancelled supplier invoices unchanged.

### Task 4: Verify

**Files:**
- Test: `apps/core/tests/test_datatable_templates.py`

- [ ] **Step 1: Run focused row-template tests**

Run:

```bash
pytest apps/core/tests/test_datatable_templates.py -q
```

Expected result: all datatable template tests pass.

- [ ] **Step 2: Run Django checks**

Run:

```bash
python manage.py check
```

Expected result:

```text
System check identified no issues (0 silenced).
```

- [ ] **Step 3: Optional targeted view smoke tests**

Run:

```bash
pytest apps/sales/tests/test_views.py apps/purchases/tests/test_views.py -q
```

Expected result: existing sales and purchase view tests pass.

### Task 5: UX Follow-Up Decision

**Files:**
- No required file changes.

- [ ] **Step 1: Decide whether non-editable documents need a disabled menu item**

Recommended decision: do not render a disabled `Editar` row. It adds noise and still does not perform a useful action. The visible `Ver` action already matches the allowed behavior for confirmed/sent/paid/cancelled documents.

- [ ] **Step 2: Decide whether draft-only edit should be documented in UI copy**

Recommended decision: no extra copy in row dropdowns. The status badge plus absence of `Editar` keeps the row compact and consistent with the existing ribbon behavior for sales lists.

---

## Self-Review

- Spec coverage: The plan addresses the edit/detail confusion for sales and purchase document row dropdowns.
- Placeholder scan: No placeholders remain.
- Type consistency: Uses existing `status == 'DRAFT'`, `data-action="edit"`, URL names, and row partial paths.
