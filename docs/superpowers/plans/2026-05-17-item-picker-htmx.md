# Item Picker HTMX Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the client-side JSON catalog item picker with an HTMX server-side search pattern identical to the customer picker modal.

**Architecture:** `ItemSearchView` returns a rendered `<tbody>` partial for each search query. The modal search input fires `hx-get` with 300 ms debounce. Row selection reads data attributes from the `<tr>` element instead of looking up `window.ITEM_CATALOG`. The JSON catalog dump (`_sale_items_json` + `window.ITEM_CATALOG`) is removed entirely.

**Tech Stack:** Django, HTMX, Bootstrap 5 modal, Alpine.js (existing formset rows)

---

## Context for the implementer

This codebase is a multi-tenant Django ERP. All views inherit `ERPBaseViewMixin`. Every query must be scoped to `request.organization`. The invoice formset uses Alpine.js `itemRow()` components for live totals — `pickItemRow` must call `Alpine.evaluate` to keep Alpine state in sync after selection.

**This plan builds on top of the customer picker branch.** Before starting, verify `CustomerSearchView` and `CustomerQuickCreateView` exist in `apps/invoices/views/htmx.py`. If the customer picker PR is not yet merged, create a worktree from that branch.

**Run tests with:**
```powershell
cd C:\Users\sabum\sabsys
.\venv\Scripts\pytest apps\invoices\ -q
```
Expected baseline: all invoice tests pass (151 or more).

---

## File Map

| Action | File | Change |
|--------|------|--------|
| Modify | `apps/invoices/views/htmx.py` | Rename `ItemCatalogView` → `ItemSearchView`, return HTML partial |
| Modify | `apps/invoices/views/__init__.py` | Export `ItemSearchView` instead of `ItemCatalogView` |
| Modify | `apps/invoices/urls.py` | Import `ItemSearchView`, rename URL `item_catalog` → `item_search` |
| Create | `templates/invoices/partials/item_picker_results.html` | HTMX `<tbody>` partial with data attrs |
| Modify | `templates/invoices/partials/item_picker_modal.html` | Add HTMX on search input, remove sort/pagination |
| Modify | `static/js/app.js` | Remove 6 old picker functions, add 3 new, simplify init |
| Modify | `templates/invoices/invoice_form.html` | Remove `window.ITEM_CATALOG` line |
| Modify | `templates/invoices/quotation_form.html` | Remove `window.ITEM_CATALOG` line |
| Modify | `templates/invoices/sale_order_form.html` | Remove `window.ITEM_CATALOG` line |
| Modify | `apps/invoices/views/invoices.py` | Remove `_sale_items_json` import + two context lines |
| Modify | `apps/invoices/views/quotations.py` | Remove `_sale_items_json` import + two context lines |
| Modify | `apps/invoices/views/sale_orders.py` | Remove `_sale_items_json` import + two context lines |
| Modify | `apps/invoices/views/_helpers.py` | Delete `_sale_items_json` function |
| Modify | `apps/invoices/tests/test_views.py` | Add `TestItemSearchView` class |

---

## Task 1: Add `ItemSearchView` + URL + tests

**Files:**
- Modify: `apps/invoices/views/htmx.py`
- Modify: `apps/invoices/views/__init__.py`
- Modify: `apps/invoices/urls.py`
- Modify: `apps/invoices/tests/test_views.py`

### Step 1.1 — Write the failing tests

Add to `apps/invoices/tests/test_views.py` (after `TestCustomerSearchView`):

```python
# ── ItemSearchView ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestItemSearchView:

    def _get(self, client, org, q=""):
        return client.get(reverse("invoices:item_search"), {"q": q})

    def test_requires_login(self, client):
        resp = client.get(reverse("invoices:item_search"))
        assert resp.status_code in (302, 403)

    def test_returns_200(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = self._get(client, org)
        assert resp.status_code == 200

    def test_scope_to_org(self, client):
        from decimal import Decimal
        from apps.items.models import Item
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        Item.objects.create(
            organization=org, name="Mi Artículo",
            item_type=Item.ItemType.SALE,
            unit_price=Decimal("100.00"), is_active=True,
        )
        other_org = OrganizationFactory()
        Item.objects.create(
            organization=other_org, name="Otro Org",
            item_type=Item.ItemType.SALE,
            unit_price=Decimal("50.00"), is_active=True,
        )
        resp = self._get(client, org)
        content = resp.content.decode()
        assert "Mi Artículo" in content
        assert "Otro Org" not in content

    def test_search_filters_by_name(self, client):
        from decimal import Decimal
        from apps.items.models import Item
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        Item.objects.create(
            organization=org, name="Consultoría Web",
            item_type=Item.ItemType.SALE,
            unit_price=Decimal("200.00"), is_active=True,
        )
        Item.objects.create(
            organization=org, name="Mantenimiento",
            item_type=Item.ItemType.SALE,
            unit_price=Decimal("150.00"), is_active=True,
        )
        resp = self._get(client, org, q="Consultoría")
        content = resp.content.decode()
        assert "Consultoría Web" in content
        assert "Mantenimiento" not in content

    def test_excludes_purchase_only_items(self, client):
        from decimal import Decimal
        from apps.items.models import Item
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        Item.objects.create(
            organization=org, name="Solo Compra",
            item_type=Item.ItemType.PURCHASE,
            unit_price=Decimal("50.00"), is_active=True,
        )
        resp = self._get(client, org)
        assert "Solo Compra" not in resp.content.decode()

    def test_returns_at_most_50_rows(self, client):
        from decimal import Decimal
        from apps.items.models import Item
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        for i in range(60):
            Item.objects.create(
                organization=org, name=f"Artículo {i:03d}",
                item_type=Item.ItemType.SALE,
                unit_price=Decimal("10.00"), is_active=True,
            )
        resp = self._get(client, org)
        assert resp.content.decode().count("<tr") <= 50
```

- [ ] **Step 1.2 — Run tests to verify they fail**

```powershell
.\venv\Scripts\pytest apps\invoices\tests\test_views.py::TestItemSearchView -v
```
Expected: FAIL — `NoReverseMatch: Reverse for 'item_search' not found`

- [ ] **Step 1.3 — Rename `ItemCatalogView` → `ItemSearchView` in htmx.py**

In `apps/invoices/views/htmx.py`, replace the entire `ItemCatalogView` class:

```python
class ItemSearchView(ERPBaseViewMixin, View):
    """
    HTMX endpoint: returns item_picker_results.html partial for the item picker modal.
    GET ?q=<search> — scoped to org, top 50 SALE/BOTH active items.
    """
    required_module = "invoices"

    def get(self, request):
        from apps.items.models import Item
        from django.db.models import Q
        from django.shortcuts import render

        q = request.GET.get("q", "").strip()
        org = _org(request)

        qs = Item.objects.filter(
            organization=org,
            is_active=True,
            item_type__in=[Item.ItemType.SALE, Item.ItemType.BOTH],
        ).order_by("name")

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

        items = qs[:50]
        return render(request, "invoices/partials/item_picker_results.html", {"items": items})
```

Also remove the `from django.core.cache import cache` import and the `CustomerDefaultsView` docstring reference to `_sale_items_json` if it mentions it.

- [ ] **Step 1.4 — Update `__init__.py`**

In `apps/invoices/views/__init__.py`, replace:
```python
from .htmx import (
    CustomerDefaultsView,
    ItemCatalogView,
)
```
With:
```python
from .htmx import (
    CustomerDefaultsView,
    ItemSearchView,
    CustomerSearchView,
    CustomerQuickCreateView,
)
```

*(If `CustomerSearchView`/`CustomerQuickCreateView` are already exported from a previous task, keep them.)*

- [ ] **Step 1.5 — Update `urls.py`**

In `apps/invoices/urls.py`:

1. In the imports block at the top, replace `ItemCatalogView,` with `ItemSearchView,`
   Also add `CustomerSearchView, CustomerQuickCreateView,` if not already present.

2. In `urlpatterns`, replace:
```python
path("invoices/items/catalog/",                ItemCatalogView.as_view(),         name="item_catalog"),
```
With:
```python
path("invoices/items/search/",                 ItemSearchView.as_view(),           name="item_search"),
```

- [ ] **Step 1.6 — Run tests to verify they pass**

```powershell
.\venv\Scripts\pytest apps\invoices\tests\test_views.py::TestItemSearchView -v
```
Expected: 6 PASS

- [ ] **Step 1.7 — Commit**

```bash
git add apps/invoices/views/htmx.py apps/invoices/views/__init__.py apps/invoices/urls.py apps/invoices/tests/test_views.py
git commit -m "feat(invoices): add ItemSearchView — HTMX HTML partial for item picker"
```

---

## Task 2: Create `item_picker_results.html` partial

**Files:**
- Create: `templates/invoices/partials/item_picker_results.html`

The Task 1 tests call the view which renders this template — they already verified it exists. This task writes its content.

*(Tests already pass from Task 1 if you created a minimal template. This task adds the correct markup.)*

- [ ] **Step 2.1 — Create the template**

`templates/invoices/partials/item_picker_results.html`:

```django
{% load i18n %}
{% if items %}
  {% for item in items %}
  <tr class="item-picker-row"
      data-pk="{{ item.pk }}"
      data-name="{{ item.name|escapejs }}"
      data-code="{{ item.code|escapejs }}"
      data-unit-price="{{ item.unit_price }}"
      data-itbis-rate="{{ item.itbis_rate }}"
      onclick="itemPickerHighlight(this)"
      ondblclick="itemPickerConfirm()"
      style="cursor:pointer">
    <td class="small font-monospace">{{ item.code|default:"-" }}</td>
    <td>{{ item.name }}</td>
    <td class="picker-unit-cell">{{ item.get_unit_display }}</td>
    <td class="text-end">{{ item.unit_price }}</td>
  </tr>
  {% endfor %}
{% else %}
  <tr>
    <td colspan="4" class="text-center text-muted py-4">
      <i class="bi bi-inbox me-1"></i>{% trans "No se encontraron artículos." %}
    </td>
  </tr>
{% endif %}
```

- [ ] **Step 2.2 — Run tests to confirm still passing**

```powershell
.\venv\Scripts\pytest apps\invoices\tests\test_views.py::TestItemSearchView -v
```
Expected: 6 PASS (content checks work with this markup)

- [ ] **Step 2.3 — Commit**

```bash
git add templates/invoices/partials/item_picker_results.html
git commit -m "feat(invoices): add item_picker_results.html HTMX partial"
```

---

## Task 3: Update `item_picker_modal.html` to use HTMX

**Files:**
- Modify: `templates/invoices/partials/item_picker_modal.html`

Replace the entire file content:

```django
{% load i18n %}
<div class="modal fade"
     id="itemPickerModal"
     tabindex="-1"
     aria-labelledby="itemPickerModalLabel"
     aria-hidden="true">

  <div class="modal-dialog picker-dialog">
    <div class="modal-content picker-content">

      <div class="picker-head d-flex align-items-center justify-content-between">
        <h6 class="picker-title mb-0" id="itemPickerModalLabel">
          {% trans "Catálogo de artículos" %}
        </h6>
        <button type="button" class="btn-close" data-bs-dismiss="modal"
                aria-label="{% trans 'Cerrar' %}"></button>
      </div>

      <div class="picker-search-area">
        <div class="input-group input-group-sm">
          <span class="input-group-text bg-transparent border-end-0">
            <i class="bi bi-search" style="font-size:0.85rem"></i>
          </span>
          <input type="text"
                 id="picker-search"
                 class="form-control border-start-0 ps-1 picker-search-input"
                 placeholder="{% trans 'Buscar por nombre o código…' %}"
                 autocomplete="off"
                 hx-get="{% url 'invoices:item_search' %}"
                 hx-trigger="input changed delay:300ms, load"
                 hx-target="#picker-tbody"
                 hx-swap="innerHTML"
                 name="q">
        </div>
      </div>

      <div class="picker-list-wrap">
        <table class="table table-sm picker-table table-hover mb-0" role="grid">
          <thead class="table-light">
            <tr>
              <th class="picker-ch-code">{% trans "No." %}</th>
              <th>{% trans "Descripción" %}</th>
              <th class="picker-ch-unit">{% trans "Unidad" %}</th>
              <th class="text-end picker-ch-price">{% trans "Precio" %}</th>
            </tr>
          </thead>
          <tbody id="picker-tbody"></tbody>
        </table>
      </div>

      <div class="picker-foot">
        <div class="picker-foot-left"></div>
        <div class="picker-foot-right">
          <a href="{% url 'items:item_list' %}"
             target="_blank"
             class="btn btn-sm btn-link picker-new-btn">
            <i class="bi bi-plus-lg"></i> {% trans "Nuevo artículo" %}
          </a>
          <button type="button" class="btn btn-sm btn-outline-secondary"
                  data-bs-dismiss="modal">
            {% trans "Cancelar" %}
          </button>
          <button type="button"
                  class="btn btn-sm"
                  id="picker-select-btn"
                  onclick="itemPickerConfirm()"
                  disabled>
            <i class="bi bi-check-lg me-1"></i>{% trans "Seleccionar" %}
          </button>
        </div>
      </div>

    </div>
  </div>
</div>
```

Key changes vs old template:
- Search input gains `hx-get`, `hx-trigger`, `hx-target`, `hx-swap`, `name="q"` attributes
- `<thead>` — sort icons and `data-sort` attrs removed
- `#picker-pagination` and `#picker-count` divs removed
- "Seleccionar" button gets `onclick="itemPickerConfirm()"`

- [ ] **Step 3.1 — Write the new template** (content above)

- [ ] **Step 3.2 — Run full invoice test suite**

```powershell
.\venv\Scripts\pytest apps\invoices\ -q
```
Expected: all pass (template change has no Python test coverage, but no breakage)

- [ ] **Step 3.3 — Commit**

```bash
git add templates/invoices/partials/item_picker_modal.html
git commit -m "feat(invoices): update item_picker_modal to use HTMX search"
```

---

## Task 4: Rewrite item picker JS in `app.js`

**Files:**
- Modify: `static/js/app.js`

This is the largest change. Find the section bounded by `var picker = {...}` through the end of `initInvoiceItemFormset()`.

### Step 4.1 — Remove old picker functions

Delete these blocks entirely from `app.js`:

1. `var picker = { selectedPk: null, sortKey: "name", sortDir: "asc", page: 1 };`
2. `function pickerRender(query) { ... }` (lines ~368–450)
3. `function pickerSelect(pk) { ... }` (lines ~452–458)
4. `function pickerRenderPagination(totalPages) { ... }` (lines ~460–478)
5. `function pickerGoPage(n) { ... }` (lines ~480–484)
6. `function pickerUpdateSortHeaders() { ... }` (lines ~486–503)
7. `function openItemPicker(rowEl) { ... }` (lines ~505–510) — replaced in Step 4.2
8. `function pickCatalogRow(rowEl, pk) { ... }` (lines ~512–540) — replaced in Step 4.2

### Step 4.2 — Add new picker functions

Add these three functions in place of the removed block (after `deleteRow` function, before `formatMoney`):

```javascript
  function openItemPicker(rowEl) {
    if (!window.bootstrap) return;
    window.activeItemRow  = rowEl;
    window.activePickerTr = null;
    var selBtn = document.getElementById("picker-select-btn");
    if (selBtn) selBtn.disabled = true;
    var searchEl = document.getElementById("picker-search");
    if (searchEl) searchEl.value = "";
    var modal = document.getElementById("itemPickerModal");
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).show();
    // Trigger HTMX search after modal is visible so tbody loads initial results.
    if (searchEl && window.htmx) htmx.trigger(searchEl, "input");
  }

  function itemPickerHighlight(tr) {
    document.querySelectorAll("#picker-tbody .item-picker-row").forEach(function (r) {
      r.removeAttribute("aria-selected");
    });
    tr.setAttribute("aria-selected", "true");
    window.activePickerTr = tr;
    var selBtn = document.getElementById("picker-select-btn");
    if (selBtn) selBtn.disabled = false;
  }

  function itemPickerConfirm() {
    var tr = window.activePickerTr;
    if (!tr || !window.activeItemRow) return;
    pickItemRow(window.activeItemRow, tr);
    var modal = document.getElementById("itemPickerModal");
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
    window.activePickerTr = null;
  }

  function pickItemRow(formRow, catalogTr) {
    var pk    = catalogTr.dataset.pk;
    var name  = catalogTr.dataset.name;
    var price = catalogTr.dataset.unitPrice;
    var rate  = catalogTr.dataset.itbisRate;

    var next    = formRow.nextElementSibling;
    var descEl  = formRow.querySelector('[name$="-description"]') ||
                  (next && next.querySelector('[name$="-description"]'));
    var priceEl = formRow.querySelector('[name$="-unit_price"]');
    var qtyEl   = formRow.querySelector('[name$="-quantity"]');
    var rateEl  = formRow.querySelector('[name$="-itbis_rate"]');
    var itemEl  = formRow.querySelector('[name$="-item"]');

    if (descEl)  descEl.value  = name;
    if (itemEl)  itemEl.value  = pk;
    if (priceEl) priceEl.value = price;
    if (qtyEl)   qtyEl.value   = "1";
    if (rateEl)  rateEl.value  = rate;

    if (typeof Alpine !== "undefined") {
      try {
        Alpine.evaluate(formRow, "price = " + (parseFloat(price) || 0) +
          ", qty = 1, rate = '" + (rate || "RATE_18") + "'");
      } catch (err) {
        console.warn("pickItemRow: Alpine.evaluate failed", err);
      }
    }
    recalcGrandTotal();
  }
```

### Step 4.3 — Simplify `initInvoiceItemFormset`

Replace the entire `initInvoiceItemFormset` function:

```javascript
  function initInvoiceItemFormset() {
    if (!document.getElementById("item-tbody")) return;
    recalcGrandTotal();

    var tbody = document.getElementById("item-tbody");
    tbody.addEventListener("input", function (e) {
      var n = e.target.name || "";
      if (n.endsWith("-quantity")) {
        var val = parseFloat(e.target.value);
        var warn = e.target.closest("td") && e.target.closest("td").querySelector(".qty-warning");
        if (warn) warn.classList.toggle("d-none", !val || val <= 0 || Number.isInteger(val));
        recalcGrandTotal();
      } else if (n.endsWith("-unit_price")) {
        recalcGrandTotal();
      }
    });
    tbody.addEventListener("change", function (e) {
      var n = e.target.name || "";
      if (n.endsWith("-itbis_rate")) recalcGrandTotal();
    });

    var pickerModal = document.getElementById("itemPickerModal");
    if (pickerModal) {
      pickerModal.addEventListener("hidden.bs.modal", function () {
        window.activePickerTr = null;
        var selBtn = document.getElementById("picker-select-btn");
        if (selBtn) selBtn.disabled = true;
      });
    }
  }
```

Key removals vs old version:
- No `pickerSearch` input listener (HTMX handles search)
- No `pickerSelBtn` click listener (button has `onclick="itemPickerConfirm()"`)
- No `pickerThead` sort listener
- `shown.bs.modal` block removed (HTMX `load` trigger handles initial results)
- `hidden.bs.modal` simplified: clear `activePickerTr`, disable button

- [ ] **Step 4.1–4.3** — Apply all three JS changes described above.

- [ ] **Step 4.4 — Run full invoice tests**

```powershell
.\venv\Scripts\pytest apps\invoices\ -q
```
Expected: all pass

- [ ] **Step 4.5 — Commit**

```bash
git add static/js/app.js
git commit -m "feat(invoices): rewrite item picker JS to use HTMX + data attributes"
```

---

## Task 5: Remove `sale_items_json` from form views and templates

**Files:**
- Modify: `apps/invoices/views/invoices.py`
- Modify: `apps/invoices/views/quotations.py`
- Modify: `apps/invoices/views/sale_orders.py`
- Modify: `apps/invoices/views/_helpers.py`
- Modify: `templates/invoices/invoice_form.html`
- Modify: `templates/invoices/quotation_form.html`
- Modify: `templates/invoices/sale_order_form.html`

### Step 5.1 — `apps/invoices/views/invoices.py`

1. Find the import line:
   ```python
   from ._helpers import _org, _sale_items_json, _customer_defaults_json
   ```
   Remove `_sale_items_json,` from it:
   ```python
   from ._helpers import _org, _customer_defaults_json
   ```

2. Find two occurrences of:
   ```python
   ctx["sale_items_json"] = _sale_items_json(self.request)
   ```
   Delete both lines (one in `InvoiceCreateView.get_context_data`, one in `InvoiceUpdateView.get_context_data`).

### Step 5.2 — `apps/invoices/views/quotations.py`

Same pattern as invoices.py:
1. Remove `_sale_items_json,` from import line.
2. Delete both `ctx["sale_items_json"] = _sale_items_json(self.request)` lines.

### Step 5.3 — `apps/invoices/views/sale_orders.py`

Same pattern:
1. Remove `_sale_items_json,` from import line.
2. Delete both `ctx["sale_items_json"] = _sale_items_json(self.request)` lines.

### Step 5.4 — `apps/invoices/views/_helpers.py`

Delete the entire `_sale_items_json` function (lines ~71–95):

```python
def _sale_items_json(request) -> str:
    """
    Active SALE/BOTH items for the current org serialized as JSON.
    Injected into form pages as window.ITEM_CATALOG.
    """
    from apps.items.models import Item

    qs = Item.objects.filter(
        organization=_org(request),
        is_active=True,
        item_type__in=[Item.ItemType.SALE, Item.ItemType.BOTH],
    ).order_by("name")
    return _html_safe_json(
        [
            {
                "pk": str(item.pk),
                "code": item.code,
                "name": item.name,
                "unit": item.get_unit_display(),
                "unit_price": str(item.unit_price),
                "itbis_rate": item.itbis_rate,
            }
            for item in qs
        ]
    )
```

After deletion, verify `_html_safe_json` is still used by `_customer_defaults_json` (it is — leave it).

### Step 5.5 — `templates/invoices/invoice_form.html`

The `<script>` block currently reads:
```django
<script>
window.ITEM_CATALOG              = {{ sale_items_json|safe }};
window.CUSTOMER_DEFAULTS         = {{ customer_defaults_json|safe }};
window.CUSTOMER_QUICK_CREATE_URL = "{% url 'invoices:customer_quick_create' %}";
</script>
```

Remove only the `ITEM_CATALOG` line:
```django
<script>
window.CUSTOMER_DEFAULTS         = {{ customer_defaults_json|safe }};
window.CUSTOMER_QUICK_CREATE_URL = "{% url 'invoices:customer_quick_create' %}";
</script>
```

### Step 5.6 — `templates/invoices/quotation_form.html`

The `<script>` block:
```django
<script>
window.ITEM_CATALOG      = {{ sale_items_json|safe }};
window.CUSTOMER_DEFAULTS = {{ customer_defaults_json|safe }};
</script>
```
Remove `ITEM_CATALOG` line:
```django
<script>
window.CUSTOMER_DEFAULTS = {{ customer_defaults_json|safe }};
</script>
```

### Step 5.7 — `templates/invoices/sale_order_form.html`

Same as quotation_form.html — remove the `ITEM_CATALOG` line.

- [ ] **Steps 5.1–5.7** — Apply all removals described above.

- [ ] **Step 5.8 — Run full invoice tests**

```powershell
.\venv\Scripts\pytest apps\invoices\ -q
```
Expected: all pass. If any test fails with `KeyError: 'sale_items_json'`, a template still references the removed context variable — check each form template.

- [ ] **Step 5.9 — Commit**

```bash
git add apps/invoices/views/invoices.py apps/invoices/views/quotations.py \
        apps/invoices/views/sale_orders.py apps/invoices/views/_helpers.py \
        templates/invoices/invoice_form.html templates/invoices/quotation_form.html \
        templates/invoices/sale_order_form.html
git commit -m "chore(invoices): remove sale_items_json / ITEM_CATALOG — replaced by ItemSearchView"
```

---

## Self-Review

**Spec coverage check:**
- ✅ `ItemSearchView` returns HTML partial (Task 1)
- ✅ `item_picker_results.html` with data attributes (Task 2)
- ✅ Modal uses HTMX `hx-get`, 300 ms debounce (Task 3)
- ✅ `pickItemRow` reads data attributes — no catalog lookup (Task 4)
- ✅ `window.ITEM_CATALOG` removed from all 3 templates (Task 5)
- ✅ `_sale_items_json` deleted from helpers and 3 form views (Task 5)
- ✅ Sort columns and client-side pagination removed (Task 3, 4)
- ✅ "Seleccionar" button + single-click highlight + double-click confirm preserved (Task 3, 4)
- ✅ Alpine.js sync via `Alpine.evaluate` preserved in `pickItemRow` (Task 4)
- ✅ Tests cover: 200 OK, org scope, name filter, purchase exclusion, 50-row cap (Task 1)

**No placeholders found.**

**Type consistency:** `pickItemRow(formRow, catalogTr)` called in `itemPickerConfirm()` with `window.activeItemRow` and `window.activePickerTr` — consistent throughout.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-17-item-picker-htmx.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, spec + quality review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
