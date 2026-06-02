# Core TAX CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an organization-scoped TAX catalog in the `core` app with list/create/edit/toggle/delete CRUD, ready to feed document tax dropdowns in a later change.

**Architecture:** Create a reusable `Tax` model in `apps/core` because tax rates are shared configuration, not sales-only data. Scope every tax row to `request.organization`, restrict CRUD to organization admins, and follow the existing HTMX/DataTable pattern used by `PaymentTermListView` and `ModuleListView`.

**Tech Stack:** Django models/forms/views/templates, django-filter, crispy-forms, HTMX, Bootstrap 5, pytest.

---

## File Structure

- Modify: `apps/core/models.py`
  - Add `Tax(ERPBaseModel)` with `organization`, `name`, `code`, `rate`, `is_active`, and `description`.
  - Keep uniqueness scoped to organization and live rows.
- Create: `apps/core/migrations/0006_tax.py`
  - Add the database table and constraints.
- Modify: `apps/core/admin.py`
  - Register `Tax` in Django admin.
- Modify: `apps/core/forms.py`
  - Add `TaxForm`.
- Modify: `apps/core/filters.py`
  - Add `TaxFilter`.
- Create: `apps/core/views_taxes.py`
  - Add org-scoped admin CRUD views.
- Modify: `apps/core/urls.py`
  - Add `tax_list`, `tax_edit`, `tax_toggle`, and `tax_delete` routes.
- Create: `templates/core/tax_list.html`
- Create: `templates/core/tax_form.html`
- Create: `templates/core/partials/tax_row.html`
- Create: `templates/core/partials/tax_modal_form.html`
- Create: `templates/core/partials/tax_filters.html`
- Modify: `templates/partials/_sidebar.html`
  - Add an admin-only organization navigation item for Taxes.
- Create: `apps/core/tests/test_taxes.py`
  - Cover model validation, org scoping, admin-only access, HTMX create/edit/toggle/delete, and blocked deletion once used by later integrations.

## Model Decisions

- Name: `Tax`, not `TaxRate`, because the UI request is for "TAX" and the object is a catalog row.
- Scope: organization-owned, using `ERPBaseModel`.
- Fields:
  - `organization`: FK to `accounts.Organization`, `related_name="taxes"`.
  - `name`: user-facing label, e.g. `ITBIS 18%`.
  - `code`: stable short code, e.g. `ITBIS_18`, `EXEMPT`.
  - `rate`: decimal percent value stored as `18.00`, not `0.18`, so forms and dropdowns match user expectations.
  - `is_active`: inactive taxes remain visible in historical records later but should be hidden from new dropdown choices.
  - `description`: optional notes.
- Constraints:
  - Unique live `code` per organization.
  - Unique live `name` per organization.
  - `rate >= 0`.
- Later dropdown integration:
  - Existing document line models currently store `itbis_rate` as a fixed choice. This plan does not change those fields yet.
  - The next plan should decide whether document lines keep a denormalized rate field, add `tax = ForeignKey("core.Tax", null=True)`, or migrate the current enum values to catalog rows.

---

### Task 1: Add Tax Model Tests

**Files:**
- Create: `apps/core/tests/test_taxes.py`

- [ ] **Step 1: Write model tests**

Create `apps/core/tests/test_taxes.py` with:

```python
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.tests.factories import OrganizationFactory
from apps.core.models import Tax


@pytest.mark.django_db
class TestTaxModel:
    def test_tax_is_scoped_to_organization(self):
        org = OrganizationFactory()
        other_org = OrganizationFactory()
        tax = Tax.objects.create(
            organization=org,
            name="ITBIS 18%",
            code="ITBIS_18",
            rate=Decimal("18.00"),
        )
        Tax.objects.create(
            organization=other_org,
            name="ITBIS 18%",
            code="ITBIS_18",
            rate=Decimal("18.00"),
        )

        assert list(Tax.objects.for_org(org)) == [tax]

    def test_duplicate_live_code_is_rejected_per_org(self):
        org = OrganizationFactory()
        Tax.objects.create(
            organization=org,
            name="ITBIS 18%",
            code="ITBIS_18",
            rate=Decimal("18.00"),
        )
        duplicate = Tax(
            organization=org,
            name="ITBIS venta",
            code="ITBIS_18",
            rate=Decimal("18.00"),
        )

        with pytest.raises(ValidationError):
            duplicate.full_clean()

    def test_duplicate_code_is_allowed_across_organizations(self):
        org = OrganizationFactory()
        other_org = OrganizationFactory()
        Tax.objects.create(
            organization=org,
            name="ITBIS 18%",
            code="ITBIS_18",
            rate=Decimal("18.00"),
        )
        tax = Tax(
            organization=other_org,
            name="ITBIS 18%",
            code="ITBIS_18",
            rate=Decimal("18.00"),
        )

        tax.full_clean()

    def test_negative_rate_is_rejected(self):
        org = OrganizationFactory()
        tax = Tax(
            organization=org,
            name="Invalid",
            code="BAD",
            rate=Decimal("-1.00"),
        )

        with pytest.raises(ValidationError):
            tax.full_clean()

    def test_string_uses_name_and_rate(self):
        org = OrganizationFactory()
        tax = Tax.objects.create(
            organization=org,
            name="ITBIS 18%",
            code="ITBIS_18",
            rate=Decimal("18.00"),
        )

        assert str(tax) == "ITBIS 18% (18.00%)"
```

- [ ] **Step 2: Run the model tests to verify failure**

Run:

```bash
pytest apps/core/tests/test_taxes.py -v
```

Expected: FAIL because `apps.core.models.Tax` does not exist.

### Task 2: Implement Tax Model And Migration

**Files:**
- Modify: `apps/core/models.py`
- Create: `apps/core/migrations/0006_tax.py`

- [ ] **Step 1: Add the model**

In `apps/core/models.py`, add this after `Module` and before `ERPBaseModel` consumers that do not need it:

```python
class Tax(ERPBaseModel):
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="taxes",
    )
    name = models.CharField(max_length=100, verbose_name=_("nombre"))
    code = models.SlugField(max_length=50, verbose_name=_("codigo"))
    rate = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("tasa"),
        help_text=_("Porcentaje. Ejemplo: 18.00 para ITBIS 18%."),
    )
    description = models.TextField(blank=True, verbose_name=_("descripcion"))
    is_active = models.BooleanField(default=True, verbose_name=_("activo"))

    class Meta(ERPBaseModel.Meta):
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_tax_code_per_org",
            ),
            models.UniqueConstraint(
                fields=["organization", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_tax_name_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["organization", "code"]),
        ]
        verbose_name = _("impuesto")
        verbose_name_plural = _("impuestos")

    def __str__(self):
        return f"{self.name} ({self.rate}%)"

    @property
    def decimal_rate(self):
        return (self.rate / Decimal("100")).quantize(Decimal("0.0001"))
```

- [ ] **Step 2: Generate the migration**

Run:

```bash
python manage.py makemigrations core
```

Expected: Django creates `apps/core/migrations/0006_tax.py`.

- [ ] **Step 3: Inspect the migration**

Run:

```bash
python manage.py sqlmigrate core 0006
```

Expected: SQL includes the `core_tax` table, organization FK, and the two partial unique constraints for live rows.

- [ ] **Step 4: Run model tests**

Run:

```bash
pytest apps/core/tests/test_taxes.py -v
```

Expected: PASS for the model tests in Task 1.

### Task 3: Add Admin Registration

**Files:**
- Modify: `apps/core/admin.py`

- [ ] **Step 1: Register Tax**

Update imports and add:

```python
from .models import Module, Tax
```

```python
@admin.register(Tax)
class TaxAdmin(ERPHistoryAdmin):
    list_display = ["name", "code", "rate", "organization", "is_active"]
    list_filter = ["is_active", "organization"]
    search_fields = ["name", "code", "organization__name"]
    list_select_related = ["organization"]
```

- [ ] **Step 2: Run admin system checks**

Run:

```bash
python manage.py check
```

Expected: `System check identified no issues`.

### Task 4: Add Tax Form And Filter

**Files:**
- Modify: `apps/core/forms.py`
- Modify: `apps/core/filters.py`

- [ ] **Step 1: Write form/filter tests**

Append to `apps/core/tests/test_taxes.py`:

```python
from apps.core.filters import TaxFilter
from apps.core.forms import TaxForm
```

```python
@pytest.mark.django_db
class TestTaxFormAndFilter:
    def test_form_saves_tax_for_organization(self):
        org = OrganizationFactory()
        form = TaxForm(
            data={
                "name": "ITBIS 18%",
                "code": "ITBIS_18",
                "rate": "18.00",
                "description": "",
                "is_active": "on",
            },
            organization=org,
        )

        assert form.is_valid(), form.errors
        tax = form.save()
        assert tax.organization == org
        assert tax.code == "ITBIS_18"

    def test_filter_searches_name_and_code(self):
        org = OrganizationFactory()
        visible = Tax.objects.create(
            organization=org,
            name="ITBIS 18%",
            code="ITBIS_18",
            rate=Decimal("18.00"),
        )
        Tax.objects.create(
            organization=org,
            name="Exento",
            code="EXEMPT",
            rate=Decimal("0.00"),
        )

        f = TaxFilter({"q": "ITBIS"}, queryset=Tax.objects.for_org(org))

        assert list(f.qs) == [visible]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest apps/core/tests/test_taxes.py::TestTaxFormAndFilter -v
```

Expected: FAIL because `TaxForm` and `TaxFilter` do not exist.

- [ ] **Step 3: Add TaxForm**

In `apps/core/forms.py`, import `Tax`:

```python
from .models import Module, Tax
```

Add:

```python
class TaxForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = Tax
        fields = ["name", "code", "rate", "description", "is_active"]
        labels = {
            "name": _("Nombre"),
            "code": _("Codigo"),
            "rate": _("Tasa"),
            "description": _("Descripcion"),
            "is_active": _("Activo"),
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "rate": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }
        help_texts = {
            "rate": _("Ingrese el porcentaje. Ejemplo: 18.00 para ITBIS 18%."),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("name", css_class="col-md-6"),
                Column("code", css_class="col-md-6"),
            ),
            Row(
                Column("rate", css_class="col-md-4"),
            ),
            "description",
            Field("is_active", template="components/forms/boolean_status_card.html"),
        )

    def save(self, commit=True):
        tax = super().save(commit=False)
        if self.organization is not None:
            tax.organization = self.organization
        if commit:
            tax.save()
            self.save_m2m()
        return tax
```

- [ ] **Step 4: Add TaxFilter**

In `apps/core/filters.py`, import `Tax`:

```python
from .models import Module, Tax
```

Add:

```python
class TaxFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search_filter", label=_("Buscar"))
    is_active = django_filters.ChoiceFilter(
        choices=[
            ("", _("Activos e inactivos")),
            ("true", _("Solo activos")),
            ("false", _("Solo inactivos")),
        ],
        method="active_filter",
        empty_label=None,
        label=_("Estado"),
    )

    class Meta:
        model = Tax
        fields = ["q", "is_active"]

    def search_filter(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(name__icontains=value) | queryset.filter(code__icontains=value)

    def active_filter(self, queryset, name, value):
        if value == "true":
            return queryset.filter(is_active=True)
        if value == "false":
            return queryset.filter(is_active=False)
        return queryset
```

- [ ] **Step 5: Run form/filter tests**

Run:

```bash
pytest apps/core/tests/test_taxes.py::TestTaxFormAndFilter -v
```

Expected: PASS.

### Task 5: Add Tax CRUD Views And URLs

**Files:**
- Create: `apps/core/views_taxes.py`
- Modify: `apps/core/urls.py`

- [ ] **Step 1: Write view tests**

Append to `apps/core/tests/test_taxes.py`:

```python
from django.urls import reverse

from apps.accounts.tests.factories import MembershipFactory, UserFactory
from apps.accounts.models import Membership
```

```python
def tax_payload(name="ITBIS 18%", code="ITBIS_18", rate="18.00", is_active=True):
    return {
        "name": name,
        "code": code,
        "rate": rate,
        "description": "",
        "is_active": "on" if is_active else "",
    }
```

```python
@pytest.mark.django_db
class TestTaxViews:
    def login_member(self, client, org, role=Membership.Role.ADMIN):
        user = UserFactory()
        MembershipFactory(user=user, organization=org, role=role)
        client.force_login(user)
        session = client.session
        session["active_org_slug"] = org.slug
        session.save()
        return user

    def test_admin_can_create_tax_with_htmx(self, client):
        org = OrganizationFactory()
        self.login_member(client, org)

        response = client.post(
            reverse("core:tax_list"),
            tax_payload(),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert Tax.objects.filter(organization=org, code="ITBIS_18").exists()
        assert "showToast" in response["HX-Trigger"]

    def test_non_admin_cannot_access_tax_list(self, client):
        org = OrganizationFactory()
        self.login_member(client, org, role=Membership.Role.MEMBER)

        response = client.get(reverse("core:tax_list"))

        assert response.status_code == 403

    def test_list_is_scoped_to_active_organization(self, client):
        org = OrganizationFactory()
        other_org = OrganizationFactory()
        visible = Tax.objects.create(
            organization=org,
            name="ITBIS 18%",
            code="ITBIS_18",
            rate=Decimal("18.00"),
        )
        Tax.objects.create(
            organization=other_org,
            name="Other",
            code="OTHER",
            rate=Decimal("10.00"),
        )
        self.login_member(client, org)

        response = client.get(reverse("core:tax_list"))

        assert response.status_code == 200
        assert visible.name.encode() in response.content
        assert b"OTHER" not in response.content

    def test_admin_can_toggle_tax_with_htmx(self, client):
        org = OrganizationFactory()
        tax = Tax.objects.create(
            organization=org,
            name="ITBIS 18%",
            code="ITBIS_18",
            rate=Decimal("18.00"),
        )
        self.login_member(client, org)

        response = client.post(
            reverse("core:tax_toggle", args=[tax.pk]),
            HTTP_HX_REQUEST="true",
        )

        tax.refresh_from_db()
        assert response.status_code == 200
        assert tax.is_active is False

    def test_admin_can_soft_delete_tax_with_htmx(self, client):
        org = OrganizationFactory()
        tax = Tax.objects.create(
            organization=org,
            name="ITBIS 18%",
            code="ITBIS_18",
            rate=Decimal("18.00"),
        )
        self.login_member(client, org)

        response = client.post(
            reverse("core:tax_delete", args=[tax.pk]),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert not Tax.objects.filter(pk=tax.pk).exists()
        assert Tax.all_objects.filter(pk=tax.pk, deleted_at__isnull=False).exists()
```

- [ ] **Step 2: Run view tests to verify failure**

Run:

```bash
pytest apps/core/tests/test_taxes.py::TestTaxViews -v
```

Expected: FAIL because `core:tax_list` routes do not exist.

- [ ] **Step 3: Add views**

Create `apps/core/views_taxes.py` with org-scoped CRUD views:

```python
import json

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.datatable import DTColumn, DataTableMixin, build_datatable_context

from .filters import TaxFilter
from .forms import TaxForm
from .models import Tax


class TaxListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "core/tax_list.html"
    admin_required = True

    dt_columns = [
        DTColumn("name", _("NOMBRE"), sortable=True),
        DTColumn("code", _("CODIGO"), sortable=True),
        DTColumn("rate", _("TASA"), sortable=True, numeric=True),
        DTColumn("is_active", _("ESTADO"), sortable=True),
    ]
    dt_default_sort = "name"
    dt_url = "core:tax_list"
    dt_row_template = "core/partials/tax_row.html"
    dt_filter_template = "core/partials/tax_filters.html"
    dt_search_placeholder = _("Nombre o codigo...")
    dt_id = "core-taxes"

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        qs = Tax.objects.for_org(request.organization)
        f = TaxFilter(request.GET, queryset=qs)
        ctx = build_datatable_context(
            request,
            f.qs,
            cls.dt_columns,
            default_sort=cls.dt_default_sort,
            page_size=cls.dt_page_size,
            url=cls.dt_url,
            row_template=cls.dt_row_template,
            filter_template=cls.dt_filter_template,
            dt_id=cls.dt_id,
        )
        ctx["filter"] = f
        resp = render(request, "components/datatable/results.html", ctx)
        resp["HX-Retarget"] = "#dt-results"
        resp["HX-Reswap"] = "innerHTML"
        resp["HX-Trigger"] = json.dumps(
            {"showToast": {"message": str(msg), "type": msg_type}}
        )
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Tax.objects.for_org(self.request.organization)
        f = TaxFilter(self.request.GET, queryset=qs)
        ctx.update(self.apply_datatable(f.qs))
        ctx["filter"] = f
        ctx["form"] = TaxForm(organization=self.request.organization)
        ctx["create_url"] = reverse("core:tax_list")
        ctx["submit_label"] = _("Crear")
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Impuestos")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def post(self, request):
        form = TaxForm(request.POST, organization=request.organization)
        if form.is_valid():
            form.save()
            if request.htmx:
                return TaxListView.refresh_table(request, _("Impuesto creado correctamente."))
            messages.success(request, _("Impuesto creado correctamente."))
            return redirect("core:tax_list")

        if request.htmx:
            resp = render(
                request,
                "core/partials/tax_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("core:tax_list"),
                    "submit_label": _("Crear"),
                },
            )
            resp["HX-Retarget"] = "#tax-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp

        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)
```

Add matching `TaxUpdateView`, `TaxToggleView`, and `TaxDeleteView` in the same file. Use `get_object_or_404(Tax, pk=pk, organization=request.organization)` in every object view. Use the same HTMX retargeting pattern as `ModuleUpdateView` and `PaymentTermDeleteView`.

- [ ] **Step 4: Add URL routes**

In `apps/core/urls.py`, import the tax views:

```python
from .views_taxes import (
    TaxListView,
    TaxUpdateView,
    TaxToggleView,
    TaxDeleteView,
)
```

Add routes:

```python
path("taxes/", TaxListView.as_view(), name="tax_list"),
path("taxes/<uuid:pk>/edit/", TaxUpdateView.as_view(), name="tax_edit"),
path("taxes/<uuid:pk>/toggle/", TaxToggleView.as_view(), name="tax_toggle"),
path("taxes/<uuid:pk>/delete/", TaxDeleteView.as_view(), name="tax_delete"),
```

- [ ] **Step 5: Run view tests**

Run:

```bash
pytest apps/core/tests/test_taxes.py::TestTaxViews -v
```

Expected: Routes resolve and tests pass after templates are added in Task 6.

### Task 6: Add Tax Templates And Sidebar Link

**Files:**
- Create: `templates/core/tax_list.html`
- Create: `templates/core/tax_form.html`
- Create: `templates/core/partials/tax_row.html`
- Create: `templates/core/partials/tax_modal_form.html`
- Create: `templates/core/partials/tax_filters.html`
- Modify: `templates/partials/_sidebar.html`

- [ ] **Step 1: Add `tax_modal_form.html`**

Create `templates/core/partials/tax_modal_form.html`:

```django
{% load crispy_forms_tags i18n %}
<form hx-post="{{ action_url }}"
      hx-target="#dt-results"
      hx-swap="innerHTML"
      hx-on::after-request="if(event.detail.successful && event.target === this) bootstrap.Modal.getInstance('#taxModal').hide()"
      class="d-flex flex-column flex-grow-1 overflow-hidden">
  {% csrf_token %}
  <div class="modal-body">
    {% crispy form %}
  </div>
  <div class="modal-footer">
    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">{% trans "Cancelar" %}</button>
    <button type="submit" class="btn btn-primary">{{ submit_label }}</button>
  </div>
</form>
```

- [ ] **Step 2: Add `tax_filters.html`**

Create `templates/core/partials/tax_filters.html`:

```django
{% load i18n %}

<div class="mb-3">
  <label class="app-filter-label">{% trans "Estado" %}</label>
  {{ filter.form.is_active }}
</div>
```

- [ ] **Step 3: Add `tax_row.html`**

Create `templates/core/partials/tax_row.html` by adapting `templates/core/partials/module_row.html`:

```django
{% load i18n %}
<tr class="{% if not row.is_active %}text-muted{% endif %}" data-pk="{{ row.pk }}">
  <td data-col="name">
    <span class="cust">{{ row.name }}</span>
    <span class="dt-row-actions">
      <div class="dropdown dt-kebab">
        <button type="button" class="btn btn-link btn-sm p-0 dt-kebab-btn"
                aria-label="{% trans 'Acciones' %}" data-bs-toggle="dropdown"
                data-bs-boundary="viewport" aria-expanded="false" tabindex="-1">
          <i class="bi bi-three-dots-vertical"></i>
        </button>
        <ul class="dropdown-menu dropdown-menu-end shadow-sm">
          <li>
            <button type="button" class="dropdown-item" data-action="edit"
                    hx-get="{% url 'core:tax_edit' row.pk %}"
                    hx-target="#tax-modal-body"
                    hx-on::after-request="
                      document.getElementById('taxModalLabel').textContent = '{% trans "Editar impuesto" %}';
                      bootstrap.Modal.getOrCreateInstance('#taxModal').show();">
              <i class="bi bi-pencil me-2"></i>{% trans "Editar" %}
            </button>
          </li>
          <li>
            <button type="button"
                    class="dropdown-item {% if row.is_active %}text-warning{% else %}text-success{% endif %}"
                    onclick="Swal.fire({
                      icon: 'question',
                      title: '{% if row.is_active %}{% trans "Desactivar impuesto?" %}{% else %}{% trans "Activar impuesto?" %}{% endif %}',
                      html: '<strong>{{ row.name|escapejs }}</strong>',
                      showCancelButton: true,
                      confirmButtonText: '{% trans "Confirmar" %}',
                      cancelButtonText: '{% trans "Cancelar" %}',
                    }).then(r => {
                      if (r.isConfirmed)
                        htmx.ajax('POST', '{% url "core:tax_toggle" row.pk %}',
                          { target: '#dt-results', swap: 'innerHTML',
                            values: { csrfmiddlewaretoken: '{{ csrf_token }}' } });
                    })">
              <i class="bi bi-toggle-{% if row.is_active %}on{% else %}off{% endif %} me-2"></i>
              {% if row.is_active %}{% trans "Desactivar" %}{% else %}{% trans "Activar" %}{% endif %}
            </button>
          </li>
          <li><hr class="dropdown-divider"></li>
          <li>
            <button type="button" class="dropdown-item text-danger" data-action="delete"
                    onclick="Swal.fire({
                      icon: 'warning',
                      title: '{% trans "Eliminar impuesto?" %}',
                      html: '<strong>{{ row.name|escapejs }}</strong>',
                      showCancelButton: true,
                      confirmButtonText: '{% trans "Eliminar" %}',
                      cancelButtonText: '{% trans "Cancelar" %}',
                      confirmButtonColor: '#dc3545',
                    }).then(r => {
                      if (r.isConfirmed)
                        htmx.ajax('POST', '{% url "core:tax_delete" row.pk %}',
                          { target: '#dt-results', swap: 'innerHTML',
                            values: { csrfmiddlewaretoken: '{{ csrf_token }}' } });
                    })">
              <i class="bi bi-trash me-2"></i>{% trans "Eliminar" %}
            </button>
          </li>
        </ul>
      </div>
    </span>
  </td>
  <td data-col="code"><span class="font-monospace small">{{ row.code }}</span></td>
  <td data-col="rate" class="text-end">{{ row.rate }}%</td>
  <td data-col="is_active">
    {% if row.is_active %}
      <span class="badge-soft badge-paid">{% trans "Activo" %}</span>
    {% else %}
      <span class="badge-soft badge-default">{% trans "Inactivo" %}</span>
    {% endif %}
  </td>
</tr>
```

- [ ] **Step 4: Add `tax_list.html`**

Create `templates/core/tax_list.html` modeled on `module_list.html`, changing IDs from `moduleModal` to `taxModal`, text to `Impuestos`, and include `core/partials/tax_modal_form.html`.

- [ ] **Step 5: Add `tax_form.html`**

Create `templates/core/tax_form.html` modeled on `templates/core/module_form.html`, with title `Editar impuesto` and cancel URL `core:tax_list`.

- [ ] **Step 6: Add sidebar link**

In `templates/partials/_sidebar.html`, inside the admin-only `Organización` section, add:

```django
<li>
  <a href="{% url 'core:tax_list' %}"
     class="sidebar-nav-link {% nav_active 'core:tax_list' 'core:tax_edit' %}">
    <i class="bi bi-percent"></i>
    <span>{% trans "Impuestos" %}</span>
  </a>
</li>
```

- [ ] **Step 7: Run template/view tests**

Run:

```bash
pytest apps/core/tests/test_taxes.py::TestTaxViews -v
```

Expected: PASS.

### Task 7: Seed Default Tax Rows For Existing And New Orgs

**Files:**
- Create: `apps/core/migrations/0007_seed_default_taxes.py`
- Modify: `apps/accounts/signals.py`

- [ ] **Step 1: Write tests for default catalog creation**

Append to `apps/core/tests/test_taxes.py`:

```python
@pytest.mark.django_db
def test_default_taxes_can_be_seeded_for_an_organization():
    org = OrganizationFactory()

    Tax.ensure_defaults(org)

    assert Tax.objects.filter(organization=org, code="ITBIS_18", rate=Decimal("18.00")).exists()
    assert Tax.objects.filter(organization=org, code="EXEMPT", rate=Decimal("0.00")).exists()
```

- [ ] **Step 2: Add `Tax.ensure_defaults`**

In `apps/core/models.py`, add:

```python
    DEFAULTS = (
        {"name": _("Exento"), "code": "EXEMPT", "rate": Decimal("0.00")},
        {"name": _("ITBIS 16%"), "code": "ITBIS_16", "rate": Decimal("16.00")},
        {"name": _("ITBIS 18%"), "code": "ITBIS_18", "rate": Decimal("18.00")},
    )

    @classmethod
    def ensure_defaults(cls, organization):
        for data in cls.DEFAULTS:
            cls.objects.get_or_create(
                organization=organization,
                code=data["code"],
                defaults={
                    "name": data["name"],
                    "rate": data["rate"],
                    "is_active": True,
                },
            )
```

- [ ] **Step 3: Add a data migration**

Create a migration that calls `Tax.ensure_defaults` equivalent logic for every existing organization. Use historical models via `apps.get_model("core", "Tax")` and `apps.get_model("accounts", "Organization")`.

- [ ] **Step 4: Wire defaults into new organization creation**

In `apps/accounts/signals.py`, after personal organization creation succeeds, call:

```python
from apps.core.models import Tax

Tax.ensure_defaults(org)
```

Also add the same call to the staff org creation workflow if it creates organizations without going through the user signal.

- [ ] **Step 5: Run tests**

Run:

```bash
pytest apps/core/tests/test_taxes.py apps/accounts/tests -q
```

Expected: PASS.

### Task 8: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Run core tests**

Run:

```bash
pytest apps/core/ -q
```

Expected: PASS.

- [ ] **Step 2: Run related account tests**

Run:

```bash
pytest apps/accounts/ -q
```

Expected: PASS.

- [ ] **Step 3: Run Django checks**

Run:

```bash
python manage.py check
```

Expected: `System check identified no issues`.

- [ ] **Step 4: Run migrations check**

Run:

```bash
python manage.py migrate
```

Expected: `core.0006_tax` and `core.0007_seed_default_taxes` apply successfully.

- [ ] **Step 5: Manual browser check**

Run:

```bash
python manage.py runserver
```

Then verify:

- Admin users see `Impuestos` in the organization sidebar.
- Non-admin users cannot access `/taxes/`.
- Creating a tax via modal refreshes the DataTable and shows a toast.
- Editing invalid duplicate code shows form errors inside the modal.
- Toggle changes `Activo` to `Inactivo`.
- Delete soft-deletes the row and removes it from the list.

## Follow-Up Plan: Use Tax In Dropdowns

The next change should update document line forms to load active taxes from `Tax.objects.for_org(request.organization).filter(is_active=True)` and decide the persistence model:

- Option A: keep existing `itbis_rate` choice field and map selected `Tax.code` to existing choices.
- Option B: add nullable `tax = ForeignKey("core.Tax")` to sales and purchase line models while denormalizing the percentage onto each line for historical accuracy.
- Option C: replace `itbis_rate` entirely with `tax`, then migrate old enum values to seeded tax rows.

Option B is likely the safest because documents keep historical tax percentages even if a catalog rate is later edited.

## Self-Review

- Spec coverage: The plan adds the core TAX model, org-scoped CRUD, navigation, admin registration, tests, migrations, and later dropdown integration guidance.
- Placeholder scan: No `TBD` or undefined feature placeholders remain. The only deferred work is intentionally listed as a follow-up because the user asked to fill dropdowns later.
- Type consistency: `Tax` uses UUID primary keys through `ERPBaseModel`, so URL patterns use `<uuid:pk>`. Views, tests, and templates all reference `core:tax_*` route names consistently.

