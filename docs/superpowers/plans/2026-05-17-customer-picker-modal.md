# Customer Picker Modal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the plain `<select>` customer widget on Invoice / Quotation / Sale Order forms with an HTMX-powered modal picker that supports search and inline quick-create.

**Architecture:** Two new HTMX views (`CustomerSearchView`, `CustomerQuickCreateView`) in `apps/invoices/views/htmx.py`. A Bootstrap modal with two panels (search / quick-create) replaces the crispy customer column using a custom `HTML(...)` layout block + hidden input. JS functions wire the modal open/close and back-fill the hidden input plus a display span.

**Tech Stack:** Django 4.x, Bootstrap 5, HTMX, vanilla JS (no new libraries)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Edit | `apps/invoices/forms.py` | Add `CustomerQuickCreateForm`; update `InvoiceForm`, `QuotationForm`, `SaleOrderForm` layouts |
| Edit | `apps/invoices/views/htmx.py` | Add `CustomerSearchView`, `CustomerQuickCreateView` |
| Edit | `apps/invoices/views/__init__.py` | Export two new views |
| Edit | `apps/invoices/urls.py` | Add two HTMX routes |
| Create | `templates/invoices/partials/customer_picker_modal.html` | Modal with search panel + quick-create panel |
| Create | `templates/invoices/partials/customer_picker_results.html` | `<tbody>` rows swapped by HTMX on search |
| Edit | `static/js/app.js` | Add 4 JS functions + quick-create response handler |
| Edit | `templates/invoices/invoice_form.html` | Include modal; init display for edit mode |
| Edit | `templates/invoices/quotation_form.html` | Same |
| Edit | `templates/invoices/sale_order_form.html` | Same |
| Edit | `apps/invoices/tests/test_views.py` | Tests for both new views |

---

## Task 1: `CustomerQuickCreateForm`

**Files:**
- Modify: `apps/invoices/forms.py`
- Test: `apps/invoices/tests/test_views.py`

- [ ] **Step 1: Write failing tests for the form**

Add to the bottom of `apps/invoices/tests/test_views.py`:

```python
# ── CustomerQuickCreateForm ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerQuickCreateForm:
    from apps.invoices.forms import CustomerQuickCreateForm

    def _form(self, data, org=None):
        from apps.invoices.forms import CustomerQuickCreateForm
        if org is None:
            from apps.accounts.tests.factories import OrganizationFactory
            org = OrganizationFactory()
        return CustomerQuickCreateForm(data, organization=org)

    def test_valid_rnc(self):
        form = self._form({"name": "Empresa X", "id_type": "RNC", "rnc_cedula": "101234567"})
        assert form.is_valid(), form.errors

    def test_missing_name(self):
        form = self._form({"id_type": "RNC", "rnc_cedula": "101234567"})
        assert not form.is_valid()
        assert "name" in form.errors

    def test_invalid_rnc_checksum(self):
        form = self._form({"name": "X", "id_type": "RNC", "rnc_cedula": "000000000"})
        assert not form.is_valid()
        assert "rnc_cedula" in form.errors

    def test_duplicate_rnc_same_org(self):
        from apps.invoices.tests.factories import CustomerFactory
        c = CustomerFactory(rnc_cedula="101234567", id_type="RNC")
        form = self._form(
            {"name": "Otro", "id_type": "RNC", "rnc_cedula": "101234567"},
            org=c.organization,
        )
        assert not form.is_valid()
        assert "rnc_cedula" in form.errors

    def test_same_rnc_different_org(self):
        from apps.invoices.tests.factories import CustomerFactory
        CustomerFactory(rnc_cedula="101234567", id_type="RNC")
        form = self._form({"name": "Y", "id_type": "RNC", "rnc_cedula": "101234567"})
        assert form.is_valid(), form.errors
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
pytest apps/invoices/tests/test_views.py::TestCustomerQuickCreateForm -v
```

Expected: `ImportError` or `AttributeError` — `CustomerQuickCreateForm` not defined yet.

- [ ] **Step 3: Implement `CustomerQuickCreateForm` in `apps/invoices/forms.py`**

Add after the existing `CustomerForm` class (around line 180, before `InvoiceForm`):

```python
class CustomerQuickCreateForm(forms.ModelForm):
    """Minimal form for creating a customer from within the picker modal."""

    class Meta:
        model = Customer
        fields = ["name", "id_type", "rnc_cedula"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        self.fields["name"].widget.attrs["autofocus"] = True
        self.fields["rnc_cedula"].widget.attrs["placeholder"] = _("9 dígitos (RNC) · 11 (Cédula)")

    def clean(self):
        cleaned_data = super().clean()
        id_type = cleaned_data.get("id_type")
        rnc_cedula = (cleaned_data.get("rnc_cedula") or "").strip()

        if rnc_cedula:
            normalized = re.sub(r"[\s\-]", "", rnc_cedula)

            if id_type == Customer.IdType.RNC:
                if not re.fullmatch(r"\d{9}", normalized):
                    self.add_error("rnc_cedula", _("El RNC debe tener exactamente 9 dígitos numéricos."))
                else:
                    ok, msg = validate_rnc(normalized)
                    if not ok:
                        self.add_error("rnc_cedula", msg)
                    else:
                        cleaned_data["rnc_cedula"] = normalized

            elif id_type == Customer.IdType.CEDULA:
                if not re.fullmatch(r"\d{11}", normalized):
                    self.add_error("rnc_cedula", _("La Cédula debe tener exactamente 11 dígitos numéricos."))
                else:
                    ok, msg = validate_cedula(normalized)
                    if not ok:
                        self.add_error("rnc_cedula", msg)
                    else:
                        cleaned_data["rnc_cedula"] = normalized

            elif id_type in (Customer.IdType.PASAPORTE, Customer.IdType.EXTERIOR):
                if not re.fullmatch(r"[A-Za-z0-9\-]{4,20}", rnc_cedula):
                    self.add_error("rnc_cedula", _("Identificación inválida (4–20 caracteres alfanuméricos)."))

            # Uniqueness within org (only if no prior errors on this field)
            if self._organization and "rnc_cedula" not in self.errors and normalized:
                if Customer.objects.filter(
                    organization=self._organization,
                    rnc_cedula=normalized,
                    deleted_at__isnull=True,
                ).exists():
                    self.add_error("rnc_cedula", _("Ya existe un cliente con este RNC/cédula en la organización."))

        return cleaned_data
```

- [ ] **Step 4: Run tests to confirm PASS**

```bash
pytest apps/invoices/tests/test_views.py::TestCustomerQuickCreateForm -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/invoices/forms.py apps/invoices/tests/test_views.py
git commit -m "feat(invoices): add CustomerQuickCreateForm for picker modal"
```

---

## Task 2: `CustomerSearchView`

**Files:**
- Modify: `apps/invoices/views/htmx.py`
- Test: `apps/invoices/tests/test_views.py`

- [ ] **Step 1: Write failing test**

Add to `apps/invoices/tests/test_views.py`:

```python
# ── CustomerSearchView ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerSearchView:

    def _get(self, client, org, q=""):
        from django.urls import reverse
        return client.get(reverse("invoices:customer_search"), {"q": q})

    def test_requires_login(self, client):
        from apps.accounts.tests.factories import OrganizationFactory
        org = OrganizationFactory()
        resp = client.get("/invoices/htmx/customers/search/")
        assert resp.status_code in (302, 403)

    def test_returns_200(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = self._get(client, org)
        assert resp.status_code == 200

    def test_scope_to_org(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        from apps.invoices.tests.factories import CustomerFactory
        c_mine = CustomerFactory(organization=org, name="Mi Cliente")
        c_other = CustomerFactory(name="Otro Org")
        resp = self._get(client, org)
        content = resp.content.decode()
        assert "Mi Cliente" in content
        assert "Otro Org" not in content

    def test_search_filters_by_name(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        from apps.invoices.tests.factories import CustomerFactory
        CustomerFactory(organization=org, name="Ferretería Central")
        CustomerFactory(organization=org, name="Supermercado Norte")
        resp = self._get(client, org, q="Ferretería")
        content = resp.content.decode()
        assert "Ferretería Central" in content
        assert "Supermercado Norte" not in content

    def test_returns_at_most_25_rows(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        from apps.invoices.tests.factories import CustomerFactory
        for i in range(30):
            CustomerFactory(organization=org)
        resp = self._get(client, org)
        # count <tr> tags in response
        assert resp.content.decode().count("<tr") <= 26  # 25 data rows + possible empty-state
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
pytest apps/invoices/tests/test_views.py::TestCustomerSearchView -v
```

Expected: 404 or `NoReverseMatch` — URL not registered yet.

- [ ] **Step 3: Create the results partial template**

Create `templates/invoices/partials/customer_picker_results.html`:

```html
{% load i18n %}
{% if customers %}
  {% for c in customers %}
  <tr style="cursor:pointer"
      onclick="customerPickerSelect('{{ c.pk }}', '{{ c.name|escapejs }}', '{{ c.rnc_cedula|escapejs }}', {{ c.default_ncf_type }})">
    <td>{{ c.name }}</td>
    <td class="text-muted small">{{ c.rnc_cedula }}</td>
    <td class="text-muted small">{{ c.email|default:"—" }}</td>
    <td class="text-muted small">{{ c.phone|default:"—" }}</td>
  </tr>
  {% endfor %}
{% else %}
  <tr>
    <td colspan="4" class="text-center text-muted py-3">
      {% trans "No se encontraron clientes." %}
      <a href="#" onclick="customerPickerShowCreate(); return false;" class="ms-1">
        {% trans "¿Crear uno nuevo?" %}
      </a>
    </td>
  </tr>
{% endif %}
```

- [ ] **Step 4: Add `CustomerSearchView` to `apps/invoices/views/htmx.py`**

Add after `ItemCatalogView`:

```python
from apps.core.search import fts_search
from django.shortcuts import render as _render


class CustomerSearchView(ERPBaseViewMixin, View):
    """Returns customer rows for the picker modal via HTMX."""
    required_module = "invoices"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        org = _org(request)
        qs = Customer.objects.filter(organization=org).order_by("name")
        if q:
            qs = fts_search(qs, q, fts_fields=["name"], trgm_fields=["rnc_cedula"])
        customers = qs[:25]
        return _render(request, "invoices/partials/customer_picker_results.html",
                       {"customers": customers})
```

Note: `_render` alias avoids shadowing the module-level `render` if it were imported. Add to the top of `htmx.py` import block: `from django.shortcuts import render as _render`.

- [ ] **Step 5: Export from `__init__.py`**

In `apps/invoices/views/__init__.py`, update the htmx import block:

```python
from .htmx import (
    CustomerDefaultsView,
    ItemCatalogView,
    CustomerSearchView,
    CustomerQuickCreateView,  # will add in Task 3 — add the name now to avoid a second edit
)
```

Wait — `CustomerQuickCreateView` doesn't exist yet. Add only `CustomerSearchView` here, then add `CustomerQuickCreateView` in Task 3.

```python
from .htmx import (
    CustomerDefaultsView,
    ItemCatalogView,
    CustomerSearchView,
)
```

- [ ] **Step 6: Register URL in `apps/invoices/urls.py`**

In the imports section add `CustomerSearchView`:
```python
    CustomerSearchView,
```

In the HTMX helpers block (after line 165):
```python
    path("invoices/customers/search/",  CustomerSearchView.as_view(), name="customer_search"),
```

- [ ] **Step 7: Run tests to confirm PASS**

```bash
pytest apps/invoices/tests/test_views.py::TestCustomerSearchView -v
```

Expected: 5 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/invoices/views/htmx.py apps/invoices/views/__init__.py \
        apps/invoices/urls.py \
        templates/invoices/partials/customer_picker_results.html \
        apps/invoices/tests/test_views.py
git commit -m "feat(invoices): add CustomerSearchView + picker results partial"
```

---

## Task 3: `CustomerQuickCreateView`

**Files:**
- Modify: `apps/invoices/views/htmx.py`
- Test: `apps/invoices/tests/test_views.py`

- [ ] **Step 1: Write failing tests**

Add to `apps/invoices/tests/test_views.py`:

```python
# ── CustomerQuickCreateView ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerQuickCreateView:

    def _post(self, client, org, data):
        from django.urls import reverse
        return client.post(reverse("invoices:customer_quick_create"), data,
                           content_type="application/x-www-form-urlencoded",
                           HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_requires_login(self, client):
        resp = client.post("/invoices/htmx/customers/create/", {})
        assert resp.status_code in (302, 403)

    def test_creates_customer_returns_json(self, client):
        import json
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = self._post(client, org, {
            "name": "Empresa Nueva S.R.L.",
            "id_type": "RNC",
            "rnc_cedula": "101234567",
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert "pk" in data
        assert data["name"] == "Empresa Nueva S.R.L."
        assert data["rnc_cedula"] == "101234567"
        assert "default_ncf_type" in data

    def test_invalid_returns_422(self, client):
        import json
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = self._post(client, org, {
            "name": "",
            "id_type": "RNC",
            "rnc_cedula": "101234567",
        })
        assert resp.status_code == 422
        data = json.loads(resp.content)
        assert "errors" in data
        assert "name" in data["errors"]

    def test_duplicate_rnc_returns_422(self, client):
        import json
        from apps.invoices.tests.factories import CustomerFactory
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        CustomerFactory(organization=org, rnc_cedula="101234567", id_type="RNC")
        resp = self._post(client, org, {
            "name": "Otro",
            "id_type": "RNC",
            "rnc_cedula": "101234567",
        })
        assert resp.status_code == 422
        data = json.loads(resp.content)
        assert "errors" in data

    def test_viewer_cannot_create(self, client):
        user, org, _ = make_member(Membership.Role.VIEWER)
        login(client, user)
        set_active_org(client, org)
        resp = self._post(client, org, {
            "name": "X",
            "id_type": "RNC",
            "rnc_cedula": "101234567",
        })
        assert resp.status_code in (302, 403)
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
pytest apps/invoices/tests/test_views.py::TestCustomerQuickCreateView -v
```

Expected: `NoReverseMatch` or 404.

- [ ] **Step 3: Add `CustomerQuickCreateView` to `apps/invoices/views/htmx.py`**

Add after `CustomerSearchView`:

```python
from ..forms import CustomerQuickCreateForm


class CustomerQuickCreateView(ERPBaseViewMixin, View):
    """Creates a customer from the picker modal quick-create panel."""
    required_module = "invoices"
    admin_required = True

    def post(self, request):
        org = _org(request)
        form = CustomerQuickCreateForm(request.POST, organization=org)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.organization = org
            customer.save()
            return JsonResponse({
                "pk": str(customer.pk),
                "name": customer.name,
                "rnc_cedula": customer.rnc_cedula,
                "default_ncf_type": customer.default_ncf_type,
            })
        return JsonResponse(
            {"errors": {field: [str(e) for e in errs]
                        for field, errs in form.errors.items()}},
            status=422,
        )
```

`JsonResponse` is already imported at the top of `htmx.py`. Add `CustomerQuickCreateForm` import at top of file:

```python
from ..forms import CustomerQuickCreateForm
```

- [ ] **Step 4: Export from `__init__.py`**

Update `apps/invoices/views/__init__.py` htmx import block:

```python
from .htmx import (
    CustomerDefaultsView,
    ItemCatalogView,
    CustomerSearchView,
    CustomerQuickCreateView,
)
```

- [ ] **Step 5: Register URL in `apps/invoices/urls.py`**

Add `CustomerQuickCreateView` to imports, and add path in the HTMX helpers block:

```python
    path("invoices/customers/create/", CustomerQuickCreateView.as_view(), name="customer_quick_create"),
```

- [ ] **Step 6: Run tests to confirm PASS**

```bash
pytest apps/invoices/tests/test_views.py::TestCustomerQuickCreateView -v
```

Expected: 5 tests PASS.

- [ ] **Step 7: Run full invoice test suite to check for regressions**

```bash
pytest apps/invoices/ -v --tb=short
```

Expected: all existing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add apps/invoices/views/htmx.py apps/invoices/views/__init__.py \
        apps/invoices/urls.py apps/invoices/forms.py \
        apps/invoices/tests/test_views.py
git commit -m "feat(invoices): add CustomerQuickCreateView"
```

---

## Task 4: Customer Picker Modal Template

**Files:**
- Create: `templates/invoices/partials/customer_picker_modal.html`

- [ ] **Step 1: Create the modal template**

Create `templates/invoices/partials/customer_picker_modal.html`:

```html
{% load i18n %}
<div class="modal fade"
     id="customerPickerModal"
     tabindex="-1"
     aria-labelledby="customerPickerModalLabel"
     aria-hidden="true">

  <div class="modal-dialog picker-dialog">
    <div class="modal-content picker-content">

      {{# ── Search panel (default) ── #}}
      <div id="customer-picker-search-panel">

        <div class="picker-head d-flex align-items-center justify-content-between">
          <h6 class="picker-title mb-0" id="customerPickerModalLabel">
            {% trans "Seleccionar cliente" %}
          </h6>
          <button type="button" class="btn-close" data-bs-dismiss="modal"
                  aria-label="{% trans 'Cerrar' %}"></button>
        </div>

        <div class="picker-search-area">
          <div class="input-group input-group-sm">
            <span class="input-group-text bg-transparent border-end-0">
              <i class="bi bi-search" style="font-size:.85rem"></i>
            </span>
            <input type="text"
                   id="customer-picker-search"
                   class="form-control border-start-0 ps-1 picker-search-input"
                   placeholder="{% trans 'Nombre o RNC…' %}"
                   autocomplete="off"
                   hx-get="{% url 'invoices:customer_search' %}"
                   hx-trigger="input changed delay:300ms, load"
                   hx-target="#customer-picker-tbody"
                   hx-include="[name='csrfmiddlewaretoken']"
                   name="q">
          </div>
        </div>

        <div class="picker-list-wrap">
          <table class="table table-sm picker-table table-hover mb-0" role="grid">
            <thead class="table-light">
              <tr>
                <th>{% trans "Nombre" %}</th>
                <th>{% trans "RNC / Cédula" %}</th>
                <th class="d-none d-md-table-cell">{% trans "Correo" %}</th>
                <th class="d-none d-md-table-cell">{% trans "Teléfono" %}</th>
              </tr>
            </thead>
            <tbody id="customer-picker-tbody"></tbody>
          </table>
        </div>

        <div class="picker-foot">
          <div class="picker-foot-left"></div>
          <div class="picker-foot-right">
            <button type="button"
                    class="btn btn-sm btn-link picker-new-btn"
                    onclick="customerPickerShowCreate()">
              <i class="bi bi-plus-lg"></i> {% trans "Nuevo cliente" %}
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary"
                    data-bs-dismiss="modal">
              {% trans "Cancelar" %}
            </button>
          </div>
        </div>

      </div>{{# end search panel #}}

      {{# ── Quick-create panel ── #}}
      <div id="customer-picker-create-panel" class="d-none">

        <div class="picker-head d-flex align-items-center justify-content-between">
          <h6 class="picker-title mb-0">{% trans "Nuevo cliente" %}</h6>
          <button type="button" class="btn-close" data-bs-dismiss="modal"
                  aria-label="{% trans 'Cerrar' %}"></button>
        </div>

        <div class="p-3">
          {% csrf_token %}
          <div class="mb-3">
            <label class="form-label fw-semibold" for="qc-name">{% trans "Nombre / Razón social" %} <span class="text-danger">*</span></label>
            <input type="text" class="form-control form-control-sm" id="qc-name" name="qc_name"
                   placeholder="{% trans 'Empresa S.R.L.' %}">
            <div class="invalid-feedback" id="qc-name-error"></div>
          </div>
          <div class="row g-2 mb-3">
            <div class="col-5">
              <label class="form-label fw-semibold" for="qc-id-type">{% trans "Tipo ID" %} <span class="text-danger">*</span></label>
              <select class="form-select form-select-sm" id="qc-id-type" name="qc_id_type">
                <option value="RNC">RNC</option>
                <option value="CED">{% trans "Cédula" %}</option>
                <option value="PAS">{% trans "Pasaporte" %}</option>
                <option value="EXT">{% trans "Ext." %}</option>
              </select>
              <div class="invalid-feedback" id="qc-id-type-error"></div>
            </div>
            <div class="col-7">
              <label class="form-label fw-semibold" for="qc-rnc">{% trans "RNC / Cédula" %} <span class="text-danger">*</span></label>
              <input type="text" class="form-control form-control-sm" id="qc-rnc" name="qc_rnc"
                     placeholder="{% trans '9 dígitos (RNC)…' %}">
              <div class="invalid-feedback" id="qc-rnc-error"></div>
            </div>
          </div>
          <div class="text-danger small mb-2" id="qc-non-field-errors"></div>
        </div>

        <div class="picker-foot">
          <div class="picker-foot-left">
            <button type="button" class="btn btn-sm btn-link"
                    onclick="customerPickerShowSearch()">
              <i class="bi bi-arrow-left me-1"></i>{% trans "Volver" %}
            </button>
          </div>
          <div class="picker-foot-right">
            <button type="button" class="btn btn-sm btn-outline-secondary"
                    data-bs-dismiss="modal">{% trans "Cancelar" %}</button>
            <button type="button" class="btn btn-sm"
                    id="qc-submit-btn"
                    style="background:#1e2130;color:#fff"
                    onclick="customerPickerQuickCreate()">
              <i class="bi bi-check-lg me-1"></i>{% trans "Crear y seleccionar" %}
            </button>
          </div>
        </div>

      </div>{{# end create panel #}}

    </div>
  </div>
</div>
```

Note: `{{# ... #}}` are not valid Django comments — use `{# ... #}`. Replace those in the actual file.

- [ ] **Step 2: Fix Django comment syntax in the template**

The template above used `{{# ... #}}` for illustration. In the actual file use `{# ... #}`. Ensure the template file uses correct Django comment syntax.

- [ ] **Step 3: Commit**

```bash
git add templates/invoices/partials/customer_picker_modal.html
git commit -m "feat(invoices): add customer picker modal template"
```

---

## Task 5: JavaScript Functions

**Files:**
- Modify: `static/js/app.js`

Add the four functions plus the quick-create submit handler. Insert them after the `openItemPicker` function (around line 510).

- [ ] **Step 1: Add JS functions to `static/js/app.js`**

After the `openItemPicker` function block (after line ~510 in `app.js`), add:

```javascript
  // ── Customer picker ──────────────────────────────────────────────────────

  function openCustomerPicker() {
    if (!window.bootstrap) return;
    var modal = document.getElementById("customerPickerModal");
    if (!modal) return;
    customerPickerShowSearch();
    var searchInput = document.getElementById("customer-picker-search");
    bootstrap.Modal.getOrCreateInstance(modal).show();
    modal.addEventListener("shown.bs.modal", function handler() {
      if (searchInput) {
        searchInput.value = "";
        searchInput.focus();
        htmx.trigger(searchInput, "load");
      }
      modal.removeEventListener("shown.bs.modal", handler);
    });
  }

  function customerPickerSelect(pk, name, rnc, defaultNcfType) {
    var sel = document.getElementById("id_customer");
    if (sel) {
      sel.value = pk;
      // Trigger HTMX change for SaleOrder department reload
      htmx.trigger(sel, "change");
    }
    var display = document.getElementById("customer-display-text");
    if (display) {
      display.textContent = rnc ? (name + " (" + rnc + ")") : name;
      display.classList.remove("text-muted", "fst-italic");
    }
    var modal = document.getElementById("customerPickerModal");
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).hide();
  }

  function customerPickerShowCreate() {
    var search = document.getElementById("customer-picker-search-panel");
    var create = document.getElementById("customer-picker-create-panel");
    if (search) search.classList.add("d-none");
    if (create) create.classList.remove("d-none");
    var nameInput = document.getElementById("qc-name");
    if (nameInput) nameInput.focus();
  }

  function customerPickerShowSearch() {
    var search = document.getElementById("customer-picker-search-panel");
    var create = document.getElementById("customer-picker-create-panel");
    if (search) search.classList.remove("d-none");
    if (create) create.classList.add("d-none");
    // Clear quick-create error state
    ["qc-name", "qc-rnc", "qc-id-type"].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.classList.remove("is-invalid");
    });
    ["qc-name-error", "qc-rnc-error", "qc-id-type-error", "qc-non-field-errors"].forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.textContent = "";
    });
  }

  function customerPickerQuickCreate() {
    var name = (document.getElementById("qc-name") || {}).value || "";
    var idType = (document.getElementById("qc-id-type") || {}).value || "";
    var rnc = (document.getElementById("qc-rnc") || {}).value || "";
    var csrf = (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "";
    var btn = document.getElementById("qc-submit-btn");
    if (btn) { btn.disabled = true; }

    var body = "name=" + encodeURIComponent(name) +
               "&id_type=" + encodeURIComponent(idType) +
               "&rnc_cedula=" + encodeURIComponent(rnc);

    fetch(window.CUSTOMER_QUICK_CREATE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrf,
      },
      body: body,
    })
    .then(function(resp) {
      return resp.json().then(function(data) {
        return { status: resp.status, data: data };
      });
    })
    .then(function(result) {
      if (btn) { btn.disabled = false; }
      if (result.status === 200) {
        customerPickerSelect(
          result.data.pk,
          result.data.name,
          result.data.rnc_cedula,
          result.data.default_ncf_type
        );
      } else {
        var errors = result.data.errors || {};
        var fieldMap = { name: "qc-name", id_type: "qc-id-type", rnc_cedula: "qc-rnc" };
        Object.keys(fieldMap).forEach(function(field) {
          var inputEl = document.getElementById(fieldMap[field]);
          var errEl = document.getElementById(fieldMap[field] + "-error");
          if (errors[field] && errors[field].length) {
            if (inputEl) inputEl.classList.add("is-invalid");
            if (errEl) errEl.textContent = errors[field][0];
          }
        });
        var nonField = errors["__all__"] || errors["non_field_errors"] || [];
        var nfEl = document.getElementById("qc-non-field-errors");
        if (nfEl) nfEl.textContent = nonField.join(" ");
      }
    })
    .catch(function() {
      if (btn) { btn.disabled = false; }
    });
  }
```

- [ ] **Step 2: Verify JS syntax**

```bash
node --check static/js/app.js
```

Expected: no output (no syntax errors).

- [ ] **Step 3: Commit**

```bash
git add static/js/app.js
git commit -m "feat(invoices): add customer picker JS functions"
```

---

## Task 6: Form Layout Changes

**Files:**
- Modify: `apps/invoices/forms.py`

Replace the customer field in `InvoiceForm`, `QuotationForm`, and `SaleOrderForm` with a hidden input + picker widget HTML block.

- [ ] **Step 1: Update `InvoiceForm.__init__`**

In `apps/invoices/forms.py`, find `InvoiceForm.__init__` (around line 261). Change:
1. After `super().__init__(*args, **kwargs)`, add the hidden widget line:
2. Update the Layout's customer column.

Change:
```python
    def __init__(self, organization=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = Customer.objects.filter(
                organization=organization
            )

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("customer", css_class="col-md-8"),
                Column("ncf_type", css_class="col-md-4"),
            ),
```

To:
```python
    def __init__(self, organization=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = Customer.objects.filter(
                organization=organization
            )
        self.fields["customer"].widget = forms.HiddenInput(attrs={"id": "id_customer"})

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column(
                    HTML(
                        '<label class="form-label requiredField">'
                        + str(_("Cliente"))
                        + '<span class="asteriskField">*</span></label>'
                        '<div class="input-group mb-1">'
                        '<span class="form-control customer-display-text" id="customer-display-text"'
                        ' style="cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"'
                        ' onclick="openCustomerPicker()">'
                        '{% if form.instance.customer %}{{ form.instance.customer.name }}{% else %}'
                        '<span class=\\"text-muted fst-italic\\">Sin cliente seleccionado</span>'
                        '{% endif %}'
                        '</span>'
                        '<button type="button" class="btn btn-outline-secondary" onclick="openCustomerPicker()">'
                        '<i class="bi bi-search"></i>'
                        '</button>'
                        '</div>'
                        '{% if form.customer.errors %}'
                        '<div class="text-danger small">{{ form.customer.errors.0 }}</div>'
                        '{% endif %}'
                    ),
                    Field("customer"),
                    css_class="col-md-8",
                ),
                Column("ncf_type", css_class="col-md-4"),
            ),
```

- [ ] **Step 2: Update `QuotationForm.__init__`**

Same pattern. Find `QuotationForm.__init__` (around line 324). Apply the same two changes (hidden widget + Layout update).

Change the customer column in the Layout from:
```python
            Row(
                Column("customer", css_class="col-md-8"),
                Column("payment_condition", css_class="col-md-4"),
            ),
```

To the same `Column(HTML(...), Field("customer"), css_class="col-md-8")` block as InvoiceForm, paired with `Column("payment_condition", css_class="col-md-4")`.

Also add after `super().__init__`:
```python
        self.fields["customer"].widget = forms.HiddenInput(attrs={"id": "id_customer"})
```

- [ ] **Step 3: Update `SaleOrderForm.__init__`**

SaleOrderForm adds HTMX attrs to the customer widget for department reload. Find the block (around line 411):

```python
        self.fields["customer"].widget.attrs.update(
            {
                "hx-get": reverse_lazy("invoices:departments_for_customer"),
                "hx-trigger": "change",
                "hx-target": "#id_department",
                "hx-swap": "innerHTML",
            }
        )
```

Change it to set `HiddenInput` first, then add HTMX attrs:

```python
        self.fields["customer"].widget = forms.HiddenInput(attrs={
            "id": "id_customer",
            "hx-get": reverse_lazy("invoices:departments_for_customer"),
            "hx-trigger": "change",
            "hx-target": "#id_department",
            "hx-swap": "innerHTML",
        })
```

Also update the Layout customer column from `Column("customer", css_class="col-md-8")` to the same `Column(HTML(...), Field("customer"), css_class="col-md-8")` pattern.

And add after `super().__init__` (before the existing `self.fields["delivery_date"]` lines):
```python
        self.fields["customer"].widget = forms.HiddenInput(attrs={"id": "id_customer"})
```

Wait — the widget is now set twice (once above, once in the HTMX block). Remove the duplicate. The final pattern for SaleOrderForm is:

```python
        # Set HiddenInput with HTMX attrs for department reload
        self.fields["customer"].widget = forms.HiddenInput(attrs={
            "id": "id_customer",
            "hx-get": reverse_lazy("invoices:departments_for_customer"),
            "hx-trigger": "change",
            "hx-target": "#id_department",
            "hx-swap": "innerHTML",
        })
```

This replaces BOTH the old widget line AND the old `widget.attrs.update(...)` call. Only one assignment needed.

- [ ] **Step 4: Run all form tests**

```bash
pytest apps/invoices/ -v --tb=short
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/invoices/forms.py
git commit -m "feat(invoices): replace customer select with hidden input + picker widget in forms"
```

---

## Task 7: Template Integration

**Files:**
- Modify: `templates/invoices/invoice_form.html`
- Modify: `templates/invoices/quotation_form.html`
- Modify: `templates/invoices/sale_order_form.html`

- [ ] **Step 1: Update `invoice_form.html`**

At the bottom of `templates/invoices/invoice_form.html`, replace:

```django
{% include "invoices/partials/item_picker_modal.html" %}

<script>
window.ITEM_CATALOG      = {{ sale_items_json|safe }};
window.CUSTOMER_DEFAULTS = {{ customer_defaults_json|safe }};
</script>
{% include "invoices/partials/item_js.html" %}
```

With:

```django
{% include "invoices/partials/item_picker_modal.html" %}
{% include "invoices/partials/customer_picker_modal.html" %}

<script>
window.ITEM_CATALOG             = {{ sale_items_json|safe }};
window.CUSTOMER_DEFAULTS        = {{ customer_defaults_json|safe }};
window.CUSTOMER_QUICK_CREATE_URL = "{% url 'invoices:customer_quick_create' %}";
</script>
{% include "invoices/partials/item_js.html" %}
```

- [ ] **Step 2: Update `quotation_form.html`**

Apply the same change to `templates/invoices/quotation_form.html` — add the modal include and `window.CUSTOMER_QUICK_CREATE_URL` script line alongside any existing `ITEM_CATALOG` / `CUSTOMER_DEFAULTS` script block.

To find the exact location, look for `item_picker_modal.html` in the template and add the customer picker modal include immediately after it.

- [ ] **Step 3: Update `sale_order_form.html`**

Same as above for `templates/invoices/sale_order_form.html`.

- [ ] **Step 4: Manual smoke test**

Start the dev server:
```bash
python manage.py runserver
```

Navigate to a new Invoice form. Verify:
- Customer field shows "Sin cliente seleccionado" button group
- Clicking the button opens the picker modal
- Searching filters customer rows
- Clicking a row closes modal and fills the customer display
- Clicking "Nuevo cliente" shows the quick-create panel
- Submitting with no customer shows Django validation error under customer field

Navigate to an existing Invoice edit form. Verify:
- Customer display shows the existing customer's name on load

Navigate to a new Sale Order form. Verify:
- After picking a customer from the modal, the department dropdown reloads via HTMX

- [ ] **Step 5: Commit**

```bash
git add templates/invoices/invoice_form.html \
        templates/invoices/quotation_form.html \
        templates/invoices/sale_order_form.html
git commit -m "feat(invoices): wire customer picker modal into all three sale document forms"
```

---

## Task 8: Final Test Run

- [ ] **Step 1: Run full test suite**

```bash
pytest --tb=short
```

Expected: all tests pass.

- [ ] **Step 2: Run JS syntax check**

```bash
node --check static/js/app.js
```

Expected: no output.

- [ ] **Step 3: Final commit if any fixups needed**

If any minor fixups were required during testing, commit them:

```bash
git add -p
git commit -m "fix(invoices): customer picker modal fixups"
```
