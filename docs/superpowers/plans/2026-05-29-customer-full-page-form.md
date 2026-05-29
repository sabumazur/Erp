# Customer Full-Page Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the modal-based customer create/edit flow with Odoo-style full-page forms featuring a two-column layout and smart buttons on the edit page.

**Architecture:** Add `CustomerCreateView` at `sales/customers/create/`, strip all HTMX-modal logic from `CustomerUpdateView`, rewrite `customer_form.html` into a two-column card layout with a contextual smart-button bar (edit only), and remove the modal markup from the list page.

**Tech Stack:** Django 4.x, django-crispy-forms + crispy-bootstrap5, Bootstrap 5, HTMX (RNC lookup only), pytest-django

---

## File Map

| Action | File |
|--------|------|
| Modify | `apps/sales/views/customers.py` |
| Modify | `apps/sales/views/__init__.py` |
| Modify | `apps/sales/urls.py` |
| Rewrite | `templates/sales/customer_form.html` |
| Modify | `templates/sales/customer_list.html` |
| Modify | `templates/sales/partials/customer_ribbon.html` |
| Modify | `templates/sales/partials/customer_row.html` |
| Delete | `templates/sales/partials/customer_modal_form.html` |
| Modify | `apps/sales/tests/test_views.py` |

---

### Task 1: Add `CustomerCreateView` with tests

**Files:**
- Modify: `apps/sales/views/customers.py`
- Modify: `apps/sales/views/__init__.py`
- Modify: `apps/sales/urls.py`
- Modify: `apps/sales/tests/test_views.py`

- [ ] **Step 1: Write failing tests for CustomerCreateView**

Add to `apps/sales/tests/test_views.py`, inside or after `TestCustomerViews`:

```python
@pytest.mark.django_db
class TestCustomerCreateView:

    def test_get_returns_200(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.get(reverse("sales:customer_create"))
        assert resp.status_code == 200

    def test_get_requires_login(self, client):
        resp = client.get(reverse("sales:customer_create"))
        assert resp.status_code in (302, 403)

    def test_post_valid_creates_customer_and_redirects_to_detail(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("sales:customer_create"), {
            "name": "Farmacia Nueva S.R.L.",
            "id_type": "RNC",
            "rnc_cedula": "101234563",
            "email": "",
            "phone": "",
            "contact_name": "", "contact_number": "",
            "address": "", "city": "", "province": "",
            "country": "República Dominicana",
            "default_ncf_type": 31,
            "notes": "",
            "change_reason": "",
        })
        from apps.sales.models import Customer
        customer = Customer.objects.get(organization=org, name="Farmacia Nueva S.R.L.")
        assert resp.status_code == 302
        assert resp["Location"] == reverse("sales:customer_detail", args=[customer.pk])

    def test_post_invalid_rnc_returns_form_errors(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("sales:customer_create"), {
            "name": "Test",
            "id_type": "RNC",
            "rnc_cedula": "123",  # too short
            "country": "República Dominicana",
            "default_ncf_type": 31,
        })
        assert resp.status_code == 200
        assert resp.context["form"].errors

    def test_post_duplicate_rnc_returns_form_error(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        CustomerFactory(organization=org, rnc_cedula="101234563")
        resp = client.post(reverse("sales:customer_create"), {
            "name": "Otro Cliente",
            "id_type": "RNC",
            "rnc_cedula": "101234563",
            "country": "República Dominicana",
            "default_ncf_type": 31,
        })
        assert resp.status_code == 200
        assert "rnc_cedula" in resp.context["form"].errors
```

- [ ] **Step 2: Run tests — verify they fail with NoReverseMatch**

```
pytest apps/sales/tests/test_views.py::TestCustomerCreateView -v
```

Expected: FAIL — `NoReverseMatch: Reverse for 'customer_create' not found`

- [ ] **Step 3: Implement CustomerCreateView**

In `apps/sales/views/customers.py`, add after the imports block:

```python
from django.views.generic import TemplateView, UpdateView, CreateView
```

Replace the current import line `from django.views.generic import TemplateView, UpdateView` with the line above.

Then add this class after `CustomerListView` and before `CustomerUpdateView`:

```python
class CustomerCreateView(ERPBaseViewMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "sales/customer_form.html"
    required_module = "sales"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["module"] = "customer"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Clientes"), "url": reverse("sales:customer_list")},
            {"label": _("Nuevo cliente")},
        ]
        return ctx

    def form_valid(self, form):
        form.instance.organization = self.request.organization
        customer = form.save()
        messages.success(self.request, _("Cliente creado correctamente."))
        return redirect("sales:customer_detail", pk=customer.pk)
```

- [ ] **Step 4: Export CustomerCreateView from views/__init__.py**

In `apps/sales/views/__init__.py`, add `CustomerCreateView` to the customers import:

```python
from .customers import (
    CustomerListView,
    CustomerDetailView,
    CustomerCreateView,
    CustomerUpdateView,
    CustomerDeleteView,
    CustomerDepartmentCreateView,
    CustomerDepartmentUpdateView,
    CustomerDepartmentToggleView,
    CustomerDepartmentDeleteView,
)
```

- [ ] **Step 5: Add URL**

In `apps/sales/urls.py`, add `CustomerCreateView` to the import:

```python
from .views import (
    # Customers
    CustomerListView,
    CustomerDetailView,
    CustomerCreateView,
    CustomerUpdateView,
    ...
```

Add the URL pattern under the customers section (before `customer_detail` to avoid slug collision):

```python
urlpatterns = [
    # ── Customers ─────────────────────────────────────────────────────────────
    path("sales/customers/",                    CustomerListView.as_view(),   name="customer_list"),
    path("sales/customers/create/",             CustomerCreateView.as_view(), name="customer_create"),
    path("sales/customers/<uuid:pk>/",          CustomerDetailView.as_view(), name="customer_detail"),
    path("sales/customers/<uuid:pk>/edit/",     CustomerUpdateView.as_view(), name="customer_edit"),
    path("sales/customers/<uuid:pk>/delete/",   CustomerDeleteView.as_view(), name="customer_delete"),
```

- [ ] **Step 6: Run tests — verify they pass**

```
pytest apps/sales/tests/test_views.py::TestCustomerCreateView -v
```

Expected: all 5 tests PASS

- [ ] **Step 7: Commit**

```
git add apps/sales/views/customers.py apps/sales/views/__init__.py apps/sales/urls.py apps/sales/tests/test_views.py
git commit -m "feat: add CustomerCreateView at /customers/create/"
```

---

### Task 2: Simplify CustomerUpdateView — remove HTMX modal, add smart buttons

**Files:**
- Modify: `apps/sales/views/customers.py`
- Modify: `apps/sales/tests/test_views.py`

- [ ] **Step 1: Write failing test for edit — HTMX GET returns full page**

Add to `TestCustomerViews` class in `apps/sales/tests/test_views.py`:

```python
def test_edit_htmx_get_returns_full_page_not_partial(self, client):
    """After removing HTMX modal, an HTMX GET must return the full page (200)."""
    user, org, _ = make_member()
    login(client, user)
    set_active_org(client, org)
    customer = CustomerFactory(organization=org)
    resp = client.get(
        reverse("sales:customer_edit", args=[customer.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    # Must NOT be a partial: full page has form tag context key
    assert "form" in resp.context

def test_edit_post_redirects_to_customer_detail(self, client):
    user, org, _ = make_member()
    login(client, user)
    set_active_org(client, org)
    customer = CustomerFactory(organization=org)
    resp = client.post(
        reverse("sales:customer_edit", args=[customer.pk]),
        {
            "name": "Updated Name S.R.L.",
            "id_type": "RNC",
            "rnc_cedula": customer.rnc_cedula,
            "email": "",
            "phone": "",
            "contact_name": "", "contact_number": "",
            "address": "", "city": "", "province": "",
            "country": "República Dominicana",
            "default_ncf_type": 31,
            "notes": "",
            "change_reason": "",
        },
    )
    assert resp.status_code == 302
    assert resp["Location"] == reverse("sales:customer_detail", args=[customer.pk])

def test_edit_context_has_smart_buttons(self, client):
    user, org, _ = make_member()
    login(client, user)
    set_active_org(client, org)
    customer = CustomerFactory(organization=org)
    resp = client.get(reverse("sales:customer_edit", args=[customer.pk]))
    assert resp.status_code == 200
    assert "smart_buttons" in resp.context
    assert "invoice_count" in resp.context["smart_buttons"]
    assert "payment_count" in resp.context["smart_buttons"]
    assert "dept_count" in resp.context["smart_buttons"]
```

- [ ] **Step 2: Run tests — verify they fail**

```
pytest apps/sales/tests/test_views.py::TestCustomerViews::test_edit_htmx_get_returns_full_page_not_partial apps/sales/tests/test_views.py::TestCustomerViews::test_edit_post_redirects_to_customer_detail apps/sales/tests/test_views.py::TestCustomerViews::test_edit_context_has_smart_buttons -v
```

Expected: `test_edit_post_redirects_to_customer_detail` FAIL (currently redirects to customer_list), others may fail

- [ ] **Step 3: Rewrite CustomerUpdateView**

In `apps/sales/views/customers.py`, replace the entire `CustomerUpdateView` class with:

```python
class CustomerUpdateView(ERPBaseViewMixin, UpdateView):
    form_class = CustomerForm
    template_name = "sales/customer_form.html"
    required_module = "sales"

    def get_object(self):
        return get_object_or_404(
            Customer, pk=self.kwargs["pk"], organization=self.request.organization
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs

    def get_context_data(self, **kwargs):
        from decimal import Decimal
        from ..models import SalesDocument, Payment

        ctx = super().get_context_data(**kwargs)
        customer = self.object
        org = self.request.organization

        invoice_count = SalesDocument.invoices.filter(
            organization=org, customer=customer
        ).exclude(
            status__in=[SalesDocument.Status.DRAFT, SalesDocument.Status.CANCELLED]
        ).count()

        payment_count = Payment.objects.filter(
            customer=customer, organization=org
        ).count()

        dept_count = customer.departments.filter(
            deleted_at__isnull=True, is_active=True
        ).count()

        ctx["smart_buttons"] = {
            "invoice_count": invoice_count,
            "payment_count": payment_count,
            "dept_count": dept_count,
            "detail_url": reverse("sales:customer_detail", args=[customer.pk]),
        }
        ctx["module"] = "customer"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Clientes"), "url": reverse("sales:customer_list")},
            {"label": customer.name},
        ]
        return ctx

    def form_valid(self, form):
        self.object = form.save()
        record_change_reason(self.object, form.cleaned_data.get("change_reason", ""))
        messages.success(self.request, _("Cliente actualizado."))
        return redirect("sales:customer_detail", pk=self.object.pk)
```

- [ ] **Step 4: Run tests**

```
pytest apps/sales/tests/test_views.py::TestCustomerViews -v
```

Expected: all tests in `TestCustomerViews` PASS

- [ ] **Step 5: Commit**

```
git add apps/sales/views/customers.py apps/sales/tests/test_views.py
git commit -m "refactor: CustomerUpdateView — remove HTMX modal, add smart buttons context"
```

---

### Task 3: Remove POST from CustomerListView

**Files:**
- Modify: `apps/sales/views/customers.py`
- Modify: `apps/sales/tests/test_views.py`

- [ ] **Step 1: Update test_create_customer_via_post**

The existing test `test_create_customer_via_post` POSTs to `customer_list`. After removing `post()`, that URL returns 405. Update the test to use the new URL:

In `apps/sales/tests/test_views.py`, replace `test_create_customer_via_post`:

```python
def test_customer_list_does_not_accept_post(self, client):
    """CustomerListView no longer handles POST — create moved to customer_create."""
    user, org, _ = make_member()
    login(client, user)
    set_active_org(client, org)
    resp = client.post(reverse("sales:customer_list"), {"name": "X"})
    assert resp.status_code == 405
```

- [ ] **Step 2: Run test to verify it fails (create URL still has POST)**

```
pytest apps/sales/tests/test_views.py::TestCustomerViews::test_customer_list_does_not_accept_post -v
```

Expected: FAIL — list view still accepts POST

- [ ] **Step 3: Remove post() and form from CustomerListView**

In `apps/sales/views/customers.py`, in `CustomerListView`:

1. Remove the entire `post()` method (lines starting with `def post(self, request):` through the end of the method).

2. In `get_context_data()`, remove these two lines:
```python
        ctx["form"] = CustomerForm(organization=org)
```

The `_refresh_table` classmethod can stay (used by other views if needed — check first, but it is currently only called from `post()` and `CustomerUpdateView.form_valid()` for HTMX; since we're removing HTMX from both, it can be removed too).

Remove `_refresh_table` classmethod as well since it is no longer called anywhere.

- [ ] **Step 4: Run tests**

```
pytest apps/sales/tests/test_views.py::TestCustomerViews -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```
git add apps/sales/views/customers.py apps/sales/tests/test_views.py
git commit -m "refactor: remove CustomerListView.post() — create moved to dedicated URL"
```

---

### Task 4: Rewrite customer_form.html (two-column + smart buttons)

**Files:**
- Rewrite: `templates/sales/customer_form.html`

- [ ] **Step 1: Rewrite the template**

Replace the entire contents of `templates/sales/customer_form.html` with:

```django
{% extends "base.html" %}
{% load crispy_forms_tags i18n %}

{% block title %}{% if object %}{{ object.name }}{% else %}{% trans "Nuevo cliente" %}{% endif %}{% endblock %}

{% block extra_css %}
{% include "components/app_styles.html" %}
{% endblock %}

{% block content %}

<div class="app-header">
  <div>
    <nav aria-label="breadcrumb">
      <ol class="breadcrumb mb-1" style="font-size:.75rem">
        <li class="breadcrumb-item">
          <a href="{% url 'sales:customer_list' %}" class="text-decoration-none text-muted">{% trans "Clientes" %}</a>
        </li>
        <li class="breadcrumb-item active text-muted">
          {% if object %}{{ object.name }}{% else %}{% trans "Nuevo cliente" %}{% endif %}
        </li>
      </ol>
    </nav>
    <h4 class="app-header-title">
      {% if object %}{{ object.name }}{% else %}{% trans "Nuevo cliente" %}{% endif %}
    </h4>
  </div>
  <div class="app-header-actions">
    <a href="{% url 'sales:customer_list' %}" class="btn btn-outline-secondary btn-sm">
      {% trans "Cancelar" %}
    </a>
  </div>
</div>

{% if smart_buttons %}
<div class="d-flex gap-2 mb-3 flex-wrap">
  <a href="{{ smart_buttons.detail_url }}" class="text-decoration-none">
    <div class="app-table-wrap px-3 py-2 text-center" style="min-width:80px;cursor:pointer">
      <div class="fw-bold lh-1 mb-1" style="font-size:1.25rem;color:#1e2130">{{ smart_buttons.invoice_count }}</div>
      <div class="text-muted" style="font-size:.65rem;text-transform:uppercase;letter-spacing:.04em">{% trans "Facturas" %}</div>
    </div>
  </a>
  <a href="{{ smart_buttons.detail_url }}" class="text-decoration-none">
    <div class="app-table-wrap px-3 py-2 text-center" style="min-width:80px;cursor:pointer">
      <div class="fw-bold lh-1 mb-1" style="font-size:1.25rem;color:#1e2130">{{ smart_buttons.payment_count }}</div>
      <div class="text-muted" style="font-size:.65rem;text-transform:uppercase;letter-spacing:.04em">{% trans "Pagos" %}</div>
    </div>
  </a>
  <a href="{{ smart_buttons.detail_url }}" class="text-decoration-none">
    <div class="app-table-wrap px-3 py-2 text-center" style="min-width:80px;cursor:pointer">
      <div class="fw-bold lh-1 mb-1" style="font-size:1.25rem;color:#1e2130">{{ smart_buttons.dept_count }}</div>
      <div class="text-muted" style="font-size:.65rem;text-transform:uppercase;letter-spacing:.04em">{% trans "Deptos" %}</div>
    </div>
  </a>
</div>
{% endif %}

<form method="post">
  {% csrf_token %}

  <div class="row g-3 align-items-start">

    {# ── Left column ────────────────────────────────────────────────────── #}
    <div class="col-md-8">

      {# Datos generales #}
      <div class="app-table-wrap mb-3">
        <div style="padding:10px 14px 9px;border-bottom:1px solid #e5e7eb;font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:#6b7280">
          {% trans "Datos generales" %}
        </div>
        <div class="p-3">
          {% crispy_field form.name %}
          <div class="row g-2">
            <div class="col-md-4">{% crispy_field form.id_type %}</div>
            <div class="col-md-8">{% crispy_field form.rnc_cedula %}</div>
          </div>
          <div class="d-flex align-items-center gap-2 mt-1 mb-1" style="min-height:1.6rem">
            <span id="rnc-lookup-spinner"
                  class="htmx-indicator spinner-border spinner-border-sm text-secondary"
                  role="status"></span>
            <div id="rnc-lookup-result"></div>
          </div>
        </div>
      </div>

      {# Contacto #}
      <div class="app-table-wrap mb-3">
        <div style="padding:10px 14px 9px;border-bottom:1px solid #e5e7eb;font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:#6b7280">
          {% trans "Contacto" %}
        </div>
        <div class="p-3">
          <div class="row g-2">
            <div class="col-md-6">{% crispy_field form.email %}</div>
            <div class="col-md-6">{% crispy_field form.phone %}</div>
          </div>
          <div class="row g-2">
            <div class="col-md-6">{% crispy_field form.contact_name %}</div>
            <div class="col-md-6">{% crispy_field form.contact_number %}</div>
          </div>
        </div>
      </div>

      {# Dirección #}
      <div class="app-table-wrap mb-3">
        <div style="padding:10px 14px 9px;border-bottom:1px solid #e5e7eb;font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:#6b7280">
          {% trans "Dirección" %}
        </div>
        <div class="p-3">
          {% crispy_field form.address %}
          <div class="row g-2">
            <div class="col-md-4">{% crispy_field form.city %}</div>
            <div class="col-md-4">{% crispy_field form.province %}</div>
            <div class="col-md-4">{% crispy_field form.country %}</div>
          </div>
        </div>
      </div>

    </div>

    {# ── Right column ───────────────────────────────────────────────────── #}
    <div class="col-md-4">

      {# Facturación #}
      <div class="app-table-wrap mb-3">
        <div style="padding:10px 14px 9px;border-bottom:1px solid #e5e7eb;font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:#6b7280">
          {% trans "Facturación" %}
        </div>
        <div class="p-3">
          {% crispy_field form.default_ncf_type %}
          {% crispy_field form.payment_term %}
          {% crispy_field form.credit_limit %}
        </div>
      </div>

      {# Notas #}
      <div class="app-table-wrap mb-3">
        <div style="padding:10px 14px 9px;border-bottom:1px solid #e5e7eb;font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:#6b7280">
          {% trans "Notas" %}
        </div>
        <div class="p-3">
          {% crispy_field form.notes %}
        </div>
      </div>

      {# Auditoría — edit only #}
      {% if object %}
      <div class="app-table-wrap mb-3">
        <div style="padding:10px 14px 9px;border-bottom:1px solid #e5e7eb;font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:#6b7280">
          {% trans "Auditoría" %}
        </div>
        <div class="p-3">
          {% crispy_field form.change_reason %}
        </div>
      </div>
      {% endif %}

    </div>

  </div>

  <div class="form-sticky-bar">
    <button type="submit" class="btn btn-sm" style="background:#1e2130;color:#fff">
      <i class="bi bi-floppy me-1"></i>{% trans "Guardar" %}
    </button>
    <a href="{% url 'sales:customer_list' %}" class="btn btn-outline-secondary btn-sm">
      {% trans "Cancelar" %}
    </a>
  </div>

</form>

{% endblock %}

{% block extra_js %}
<script>
window.SabSysConfig = Object.assign(window.SabSysConfig || {}, {
  rncFoundTitle: "{% trans 'RNC encontrado' %}",
  rncNotFoundTitle: "{% trans 'No encontrado' %}",
  rncNotFoundText: "{% trans 'Este RNC/Cédula no está registrado en el registro oficial.' %}",
  acceptText: "{% trans 'Aceptar' %}",
  cancelText: "{% trans 'Cancelar' %}",
  closeText: "{% trans 'Cerrar' %}"
});
</script>
{% endblock %}
```

- [ ] **Step 2: Run the full test suite to catch any regressions**

```
pytest apps/sales/ -v
```

Expected: all passing

- [ ] **Step 3: Commit**

```
git add templates/sales/customer_form.html
git commit -m "feat: rewrite customer_form.html — two-column Odoo-style layout with smart buttons"
```

---

### Task 5: Update list page and ribbon — remove modal, add create link

**Files:**
- Modify: `templates/sales/customer_list.html`
- Modify: `templates/sales/partials/customer_ribbon.html`

- [ ] **Step 1: Rewrite customer_list.html**

Replace the entire contents of `templates/sales/customer_list.html` with:

```django
{% extends "base.html" %}
{% load i18n %}

{% block title %}{% trans "Clientes" %}{% endblock %}

{% block extra_css %}
{% include "components/app_styles.html" %}
{% endblock %}

{% block content %}

<div class="app-header">
  <div>
    <h4 class="app-header-title">{% trans "Clientes" %}</h4>
    <p class="app-header-sub">{% trans "CRM" %}</p>
  </div>
</div>

{% include "components/datatable/wrapper.html" %}

{% endblock %}

{% block extra_js %}
<script>
window.SabSysConfig = Object.assign(window.SabSysConfig || {}, {
  departmentsTitle: "{% trans 'Departamentos' %}",
  acceptText: "{% trans 'Aceptar' %}",
  cancelText: "{% trans 'Cancelar' %}",
  closeText: "{% trans 'Cerrar' %}"
});
</script>
{% endblock %}
```

- [ ] **Step 2: Rewrite customer_ribbon.html — change "Nuevo" from modal trigger to link**

Replace the entire contents of `templates/sales/partials/customer_ribbon.html` with:

```django
{% load i18n %}
{# Ribbon actions for the customer list. Rendered inside .dt-ribbon-left inside #dt-wrapper (Alpine dtTable() scope). #}

<a href="{% url 'sales:customer_create' %}" class="btn btn-primary">
  <i class="bi bi-plus-lg me-1"></i>{% trans "Nuevo" %}
</a>

<span class="dt-ribbon-sep"></span>

<button type="button" class="btn btn-outline-secondary"
        :disabled="!canAct"
        :class="{'disabled': !canAct}"
        @click="canAct && (window.location.href = document.querySelector('tr.dt-row-selected [data-action=view]')?.href || '#')">
  <i class="bi bi-eye me-1"></i>{% trans "Ver" %}
</button>

<button type="button" class="btn btn-outline-secondary"
        :disabled="!canAct"
        :class="{'disabled': !canAct}"
        @click="canAct && (window.location.href = document.querySelector('tr.dt-row-selected [data-action=edit]')?.href || '#')">
  <i class="bi bi-pencil me-1"></i>{% trans "Editar" %}
</button>

<button type="button" class="btn btn-outline-secondary"
        :disabled="!canAct"
        :class="{'disabled': !canAct, 'text-danger': canAct}"
        @click="canAct && document.querySelector('tr.dt-row-selected [data-action=delete]')?.click()">
  <i class="bi bi-trash me-1"></i>{% trans "Eliminar" %}
</button>
```

Note: The "Editar" ribbon button changed from `?.click()` to `?.href` navigation because the edit kebab item is now a plain `<a>` link (changed in Task 6). The "Eliminar" button still uses `.click()` because the delete kebab item is still a `<button>` with an `onclick` handler.

- [ ] **Step 3: Run tests**

```
pytest apps/sales/tests/test_views.py -v
```

Expected: all PASS

- [ ] **Step 4: Commit**

```
git add templates/sales/customer_list.html templates/sales/partials/customer_ribbon.html
git commit -m "feat: customer list — remove modal, Nuevo button links to full-page create"
```

---

### Task 6: Update customer_row.html — change edit kebab to plain link

**Files:**
- Modify: `templates/sales/partials/customer_row.html`

- [ ] **Step 1: Replace the edit kebab item**

In `templates/sales/partials/customer_row.html`, replace the edit `<button>` block:

```html
                <li>
                  <button type="button" class="dropdown-item" data-action="edit"
                          hx-get="{% url 'sales:customer_edit' row.pk %}?hx_target=%23dt-results"
                          hx-target="#customer-modal-body"
                          hx-on::after-request="document.getElementById('customerModalTitle').textContent = '{% trans "Editar cliente" %}';
                                                bootstrap.Modal.getOrCreateInstance('#customerModal').show();">
                    <i class="bi bi-pencil me-2"></i>{% trans "Editar" %}
                  </button>
                </li>
```

with:

```html
                <li>
                  <a class="dropdown-item" href="{% url 'sales:customer_edit' row.pk %}" data-action="edit">
                    <i class="bi bi-pencil me-2"></i>{% trans "Editar" %}
                  </a>
                </li>
```

- [ ] **Step 2: Run full sales test suite**

```
pytest apps/sales/ -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```
git add templates/sales/partials/customer_row.html
git commit -m "feat: customer row — edit kebab navigates to full-page edit"
```

---

### Task 7: Delete customer_modal_form.html

**Files:**
- Delete: `templates/sales/partials/customer_modal_form.html`

- [ ] **Step 1: Verify no remaining references**

```
grep -r "customer_modal_form" templates/ apps/
```

Expected output: no matches (or only the file itself)

- [ ] **Step 2: Delete the file**

```
git rm templates/sales/partials/customer_modal_form.html
```

- [ ] **Step 3: Run full test suite**

```
pytest apps/sales/ -v
```

Expected: all PASS

- [ ] **Step 4: Commit**

```
git commit -m "chore: delete customer_modal_form.html — replaced by full-page form"
```

---

## Self-Review

### Spec Coverage

| Spec requirement | Task |
|-----------------|------|
| New `CustomerCreateView` at `customers/create/` | Task 1 |
| `required_module = "sales"`, no admin_required | Task 1 |
| POST → redirect to `customer_detail` | Task 1 |
| Remove all HTMX modal logic from `CustomerUpdateView` | Task 2 |
| Smart buttons context on edit page | Task 2 |
| `form_valid` redirects to `customer_detail` | Task 2 |
| Remove `CustomerListView.post()` | Task 3 |
| Two-column template with sections | Task 4 |
| Smart buttons bar (edit only, via `{% if object %}`) | Task 4 |
| RNC lookup spinner + `#rnc-lookup-result` div | Task 4 |
| `change_reason` field edit-only | Task 4 |
| Remove modal from `customer_list.html` | Task 5 |
| "Nuevo" button links to `customer_create` | Task 5 |
| Edit kebab → plain link | Task 6 |
| Delete `customer_modal_form.html` | Task 7 |

### End-to-End Verification

After all tasks:
1. `pytest apps/sales/ -v` — all pass
2. Start dev server: `python manage.py runserver`
3. Navigate to `/ventas/clientes/` → "Nuevo" button links to `/ventas/clientes/create/`
4. Fill form, submit → redirected to customer detail page, success message shown
5. RNC blur on form → spinner shows, name field auto-populated
6. Edit from kebab → navigates to `/ventas/clientes/<pk>/editar/` (full page)
7. Edit page shows smart buttons with invoice/payment/dept counts linking to detail
8. Edit, save → redirected to customer detail, "Cliente actualizado" message
9. Invalid form → stays on page, field errors inline
