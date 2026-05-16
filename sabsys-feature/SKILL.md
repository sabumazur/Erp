---
name: sabsys-feature
description: >
  Full-stack Django feature generator for the sabsys ERP app. Use this skill
  whenever the user asks to add a new model, CRUD feature, app, view, service,
  or any new piece of functionality to the sabsys project. Triggers include:
  "add a X model", "create a CRUD for Y", "I need a new app for Z", "add views
  for W", "scaffold a feature", "generate the boilerplate for", "build the
  backend for", or any request that involves creating new Django files in the
  sabsys codebase. When in doubt, use this skill — it ensures every generated
  file matches sabsys's exact architectural conventions.
---

# sabsys Feature Generator

You are generating code for **sabsys** — a multi-tenant Django ERP for Dominican
businesses. Every file you produce must fit the existing architecture described
below. Read it carefully before writing a single line.

---

## Project layout

```
apps/
  <app_name>/
    __init__.py
    apps.py
    models.py
    forms.py
    filters.py        # django-filter FilterSet
    views.py          # or views/ package for large apps
    urls.py
    admin.py
    tests/
      __init__.py
      factories.py
      test_models.py
      test_views.py
      test_services.py   # if service layer exists
    migrations/
config/
  settings/base.py, development.py, production.py
  urls.py             # root URLconf
templates/
  <app_name>/
    <model>_list.html
    <model>_detail.html
    <model>_form.html   # non-HTMX fallback
    partials/
      <model>_row.html       # one <tr> for datatable
      <model>_modal_form.html
      <model>_filters.html   # filter offcanvas body
```

---

## 1. Models

Every entity model inherits `ERPBaseModel` from `apps.core.models`:

```python
# apps/core/models.py (already exists — do not re-create)
class ERPBaseModel(TimeStampedModel, SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class Meta:
        abstract = True
        ordering = ["-created_at"]
```

`ERPBaseModel` gives you: UUID PK, `created_at`, `updated_at`, `deleted_at`
(soft-delete), `.objects` (filters deleted), `.all_objects` (bypasses filter),
and `.objects.for_org(organization)` for org scoping.

### Template

```python
from django.db import models
from apps.core.models import ERPBaseModel


class MyEntity(ERPBaseModel):
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="my_entities",
    )
    # ... your fields ...

    class Meta(ERPBaseModel.Meta):
        verbose_name = "My Entity"
        verbose_name_plural = "My Entities"

    def __str__(self):
        return self.name  # or whatever makes sense
```

**Rules:**
- Always add `organization` FK — every entity is org-scoped.
- Use `all_objects` in slug/code uniqueness checks to avoid soft-deleted
  collisions: `MyEntity.all_objects.filter(code=code, organization=org).exists()`
- Never use `id` or `pk` as a URL kwarg — use the UUID directly (`str(obj.pk)`).
- Status fields use `models.TextChoices` inner class.
- `model.delete()` soft-deletes (sets `deleted_at`). Use `model.hard_delete()`
  for real SQL DELETE. `pre_delete`/`post_delete` signals are NOT emitted on
  soft-delete — do guardian cleanup manually beforehand.

---

## 2. Service layer

Business logic that changes state belongs in a service class, not in views.
Model mutations stay in models; orchestration and atomic sequences go in services.

```python
# apps/<app>/services.py
from django.db import transaction


class MyEntityService:

    @staticmethod
    @transaction.atomic
    def activate(entity, activated_by=None):
        """Transition entity from DRAFT to ACTIVE."""
        if entity.status != MyEntity.Status.DRAFT:
            raise ValueError("Only DRAFT entities can be activated.")
        entity.status = MyEntity.Status.ACTIVE
        entity.save(update_fields=["status", "updated_at"])
        return entity
```

**Rules:**
- Use `@transaction.atomic` for any multi-step mutation.
- Raise `ValueError` (not Http404 or PermissionDenied) for business-rule
  violations — views translate these into user messages.
- Never import from views or templates inside services.
- Use `SELECT FOR UPDATE` for sequences or any counter that needs
  concurrency safety: `MySequence.objects.select_for_update().get(...)`.

---

## 3. Views

All views inherit `ERPBaseViewMixin` from `apps.accounts.views`:

```python
class ERPBaseViewMixin(LoginRequiredMixin):
    required_permission: str | None = None  # guardian codename
    admin_required: bool = False            # True → OWNER or ADMIN only
    required_module: str | None = None      # module slug
```

### Plain `View` subclasses (most CRUD views)

Use `self.get_context(**kwargs)` — NOT `get_context_data()` — to inject sidebar
variables (`organization`, `membership`, `user_memberships`):

```python
from django.views import View
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from apps.accounts.views import ERPBaseViewMixin


class MyEntityDetailView(ERPBaseViewMixin, View):
    required_module = "my_module"

    def get(self, request, pk):
        entity = get_object_or_404(
            MyEntity, pk=pk, organization=request.organization
        )
        return render(request, "my_app/entity_detail.html", self.get_context(
            entity=entity,
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Entities"), "url": reverse("my_app:entity_list")},
                {"label": entity.name},
            ],
        ))
```

### TemplateView subclasses (list views with DataTableMixin)

Use `get_context_data()` (calls `super()`) and call `self.render_to_response(ctx)`:

```python
from django.views.generic import TemplateView
from apps.core.datatable import DTColumn, DataTableMixin, build_datatable_context


class MyEntityListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "my_app/entity_list.html"
    required_module = "my_module"

    dt_columns = [
        DTColumn("name",       _("Nombre"),    sortable=True),
        DTColumn("status",     _("Estado"),    sortable=True),
        DTColumn("created_at", _("Creado"),    sortable=True),
    ]
    dt_default_sort  = "-created_at"
    dt_page_size     = 25
    dt_url           = "my_app:entity_list"
    dt_row_template  = "my_app/partials/entity_row.html"
    dt_filter_template = "my_app/partials/entity_filters.html"
    dt_search_placeholder = _("Buscar entidades…")
    dt_id            = "my_app_entities"

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        import json
        f = MyEntityFilter(request.GET, queryset=MyEntity.objects.for_org(request.organization))
        ctx = build_datatable_context(
            request, f.qs, cls.dt_columns,
            default_sort=cls.dt_default_sort,
            page_size=cls.dt_page_size,
            url=cls.dt_url,
            row_template=cls.dt_row_template,
            filter_template=cls.dt_filter_template,
        )
        ctx["filter"] = f
        resp = render(request, "components/datatable/results.html", ctx)
        resp["HX-Retarget"] = "#dt-results"
        resp["HX-Reswap"]   = "innerHTML"
        resp["HX-Trigger"]  = json.dumps(
            {"showToast": {"message": str(msg), "type": msg_type}}
        )
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        f = MyEntityFilter(
            self.request.GET,
            queryset=MyEntity.objects.for_org(self.request.organization),
        )
        ctx.update(self.apply_datatable(f.qs))
        ctx["filter"]      = f
        ctx["form"]        = MyEntityForm()
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Entities")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)
```

### Delete views

Delete views are always POST-only, `admin_required = True`, and guard
referential integrity before calling `model.delete()`:

```python
class MyEntityDeleteView(ERPBaseViewMixin, View):
    admin_required = True
    required_module = "my_module"

    def post(self, request, pk):
        import json
        entity = get_object_or_404(
            MyEntity, pk=pk, organization=request.organization
        )

        # Guard referential integrity before soft-deleting
        if entity.related_things.exists():
            msg = _("No se puede eliminar: tiene elementos asociados.")
            if request.htmx:
                resp = HttpResponse(status=200)
                resp["HX-Trigger"] = json.dumps(
                    {"showSwal": {"message": str(msg), "type": "error"}}
                )
                return resp
            messages.error(request, msg)
            return redirect("my_app:entity_list")

        name = str(entity)
        entity.delete()
        msg = _(f"«{name}» eliminado.")

        if request.htmx:
            return MyEntityListView.refresh_table(request, msg)
        messages.success(request, msg)
        return redirect("my_app:entity_list")
```

### HTMX modal form pattern (update view)

GET renders the form into the modal body; POST handles validation:

```python
class MyEntityUpdateView(ERPBaseViewMixin, View):
    required_module = "my_module"
    admin_required = True

    def get(self, request, pk):
        entity = get_object_or_404(MyEntity, pk=pk, organization=request.organization)
        form = MyEntityForm(instance=entity)
        if request.htmx:
            return render(request, "my_app/partials/entity_modal_form.html", {
                "form": form,
                "action_url": reverse("my_app:entity_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })
        return render(request, "my_app/entity_form.html", self.get_context(
            form=form, entity=entity,
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Entities"), "url": reverse("my_app:entity_list")},
                {"label": str(entity)},
                {"label": _("Editar")},
            ],
        ))

    def post(self, request, pk):
        entity = get_object_or_404(MyEntity, pk=pk, organization=request.organization)
        form = MyEntityForm(request.POST, instance=entity)
        if form.is_valid():
            form.save()
            if request.htmx:
                return MyEntityListView.refresh_table(request, _("Entidad actualizada."))
            messages.success(request, _("Entidad actualizada."))
            return redirect("my_app:entity_list")
        if request.htmx:
            resp = render(request, "my_app/partials/entity_modal_form.html", {
                "form": form,
                "action_url": reverse("my_app:entity_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })
            resp["HX-Retarget"] = "#entity-modal-body"
            resp["HX-Reswap"]   = "innerHTML"
            return resp
        return render(request, "my_app/entity_form.html", self.get_context(
            form=form, entity=entity,
            breadcrumbs=[...],
        ))
```

---

## 4. Forms

```python
from django import forms
from crispy_forms.helper import FormHelper


class MyEntityForm(forms.ModelForm):
    class Meta:
        model = MyEntity
        fields = ["name", "status", ...]  # never include organization or deleted_at

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False  # modal renders its own <form>
```

---

## 5. Filters

```python
import django_filters
from .models import MyEntity


class MyEntityFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search", label="")

    def search(self, queryset, name, value):
        from apps.core.search import fts_search
        return fts_search(queryset, value, fts_fields=["name"], trgm_fields=["code"])

    class Meta:
        model = MyEntity
        fields = ["status"]
```

---

## 6. URLs

```python
# apps/my_app/urls.py
from django.urls import path
from . import views

app_name = "my_app"

urlpatterns = [
    path("",                  views.MyEntityListView.as_view(),   name="entity_list"),
    path("<uuid:pk>/",        views.MyEntityDetailView.as_view(), name="entity_detail"),
    path("<uuid:pk>/edit/",   views.MyEntityUpdateView.as_view(), name="entity_edit"),
    path("<uuid:pk>/delete/", views.MyEntityDeleteView.as_view(), name="entity_delete"),
]
```

Register in `config/urls.py`:

```python
path("my-app/", include("apps.my_app.urls")),
```

---

## 7. Templates

UI language is **Spanish**. Use Bootstrap 5, Bootstrap Icons (`bi-*`),
HTMX attributes, and Alpine.js where needed. Always `{% load i18n humanize %}`.

### List page (`my_app/entity_list.html`)

```django
{% extends "base.html" %}
{% load i18n humanize %}

{% block content %}
<div class="container-fluid py-3">
  {% include "components/datatable/wrapper.html" with
      title="Entities"
      create_modal_target="#entity-modal"
      create_label="Nueva entidad" %}
</div>

<!-- Create/Edit modal -->
<div class="modal fade" id="entity-modal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">{% trans "Entidad" %}</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body" id="entity-modal-body">
        {% include "my_app/partials/entity_modal_form.html" with
            form=form action_url=create_url submit_label=submit_label %}
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

### Row partial (`my_app/partials/entity_row.html`)

```django
{% load i18n %}
<tr>
  <td><a href="{% url 'my_app:entity_detail' row.pk %}">{{ row.name }}</a></td>
  <td>{{ row.get_status_display }}</td>
  <td>{{ row.created_at|naturaltime }}</td>
  <td class="text-end">
    <button class="btn btn-sm btn-outline-secondary"
            hx-get="{% url 'my_app:entity_edit' row.pk %}"
            hx-target="#entity-modal-body"
            hx-swap="innerHTML"
            data-bs-toggle="modal"
            data-bs-target="#entity-modal">
      <i class="bi bi-pencil"></i>
    </button>
    <button class="btn btn-sm btn-outline-danger"
            hx-post="{% url 'my_app:entity_delete' row.pk %}"
            hx-confirm="¿Eliminar esta entidad?"
            hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
      <i class="bi bi-trash"></i>
    </button>
  </td>
</tr>
```

### Modal form partial (`my_app/partials/entity_modal_form.html`)

```django
{% load crispy_forms_tags %}
<form hx-post="{{ action_url }}"
      hx-target="#entity-modal-body"
      hx-swap="innerHTML"
      hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
  {% csrf_token %}
  {% crispy form %}
  <div class="d-flex justify-content-end gap-2 mt-3">
    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
      {% trans "Cancelar" %}
    </button>
    <button type="submit" class="btn btn-primary">{{ submit_label }}</button>
  </div>
</form>
```

---

## 8. Admin

```python
# apps/my_app/admin.py
from django.contrib import admin
from .models import MyEntity


@admin.register(MyEntity)
class MyEntityAdmin(admin.ModelAdmin):
    list_display   = ["name", "organization", "status", "created_at"]
    list_filter    = ["status", "organization"]
    search_fields  = ["name"]
    raw_id_fields  = ["organization"]
    readonly_fields = ["id", "created_at", "updated_at", "deleted_at"]
```

---

## 9. Tests

```python
# apps/my_app/tests/factories.py
import factory
from factory.django import DjangoModelFactory, mute_signals
from django.db.models.signals import post_save
from apps.accounts.tests.factories import OrganizationFactory
from apps.my_app.models import MyEntity


@mute_signals(post_save)
class MyEntityFactory(DjangoModelFactory):
    class Meta:
        model = MyEntity

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Entity {n}")
    status = MyEntity.Status.DRAFT
```

```python
# apps/my_app/tests/test_views.py
import pytest
from django.urls import reverse
from apps.my_app.tests.factories import MyEntityFactory


@pytest.mark.django_db
class TestMyEntityViews:

    def _login(self, client, membership):
        client.force_login(membership.user)
        session = client.session
        session["active_org_slug"] = membership.organization.slug
        session.save()

    def test_list_requires_login(self, client):
        response = client.get(reverse("my_app:entity_list"))
        assert response.status_code == 302

    def test_list_accessible_to_member(self, client, member_membership):
        self._login(client, member_membership)
        response = client.get(reverse("my_app:entity_list"))
        assert response.status_code == 200

    def test_delete_requires_admin(self, client, member_membership):
        entity = MyEntityFactory(organization=member_membership.organization)
        self._login(client, member_membership)
        response = client.post(reverse("my_app:entity_delete", args=[entity.pk]))
        assert response.status_code == 403

    def test_delete_removes_entity(self, client, admin_membership):
        entity = MyEntityFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        response = client.post(reverse("my_app:entity_delete", args=[entity.pk]))
        assert response.status_code == 302
        entity.refresh_from_db()
        assert entity.deleted_at is not None  # soft-deleted
```

Global fixtures from root `conftest.py` (`user`, `org`, `owner_membership`,
`admin_membership`, `member_membership`, `viewer_membership`) are available
automatically — no need to import them.

---

## 10. New Django app checklist

When scaffolding an entirely new app:

1. Create `apps/<app_name>/` directory with all required files.
2. Add `"apps.<app_name>"` to `INSTALLED_APPS` in `config/settings/base.py`.
3. Register URLs in `config/urls.py` with an appropriate prefix.
4. Create templates under `templates/<app_name>/` and `templates/<app_name>/partials/`.
5. Run `python manage.py makemigrations <app_name>`.
6. Register the model in `admin.py`.
7. If module-gated, document the module slug so it can be seeded via
   `python manage.py seed_modules`.

---

## Quick-reference conventions

| Topic | Rule |
|-------|------|
| Language | Spanish UI (`gettext_lazy`), `LANGUAGE_CODE = "es"` |
| Auth | `ERPBaseViewMixin` on every view; `admin_required=True` for write ops |
| Org scoping | Always `Model.objects.for_org(request.organization)` |
| Context (View) | `self.get_context(...)` — not `get_context_data()` |
| Context (TemplateView) | `super().get_context_data(**kwargs)` |
| HTMX responses | Check `request.htmx`; partial or full page accordingly |
| Delete | POST-only, guard refs first, then `model.delete()` (soft) |
| HTMX success | `HX-Trigger: {"showToast": {...}}` via `refresh_table()` |
| HTMX blocked | `HX-Trigger: {"showSwal": {...}}` with type "error" |
| Crispy forms | `bootstrap5` pack; `form_tag = False` for modals |
| Breadcrumbs | `[{"label": ..., "url": ...}, ..., {"label": ...}]` — last has no url |
| Humanize | `{% load humanize %}` → `intcomma`, `naturaltime` |
| UUIDs in URLs | `<uuid:pk>` path converter |
| Uniqueness checks | Use `.all_objects` to avoid soft-deleted collisions |
| Tests login | `client.force_login(m.user)` + set `session["active_org_slug"]` |
