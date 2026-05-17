# django-simple-history End-to-End Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `django-simple-history` into SabSys so every `ERPBaseModel` entity has an audit trail, a reusable history UI component, and `change_reason` prompts on sensitive edit forms.

**Architecture:** `HistoricalRecords(inherit=True)` on `ERPBaseModel` propagates audit logging to all concrete entity models automatically. A thin `apps/core/history.py` helper exposes `record_change_reason()`. A `HistoryMixin` + two template partials provide a plug-in timeline panel for any detail page. `change_reason` is added as a non-model `CharField` to edit forms for Customer, Item, and PaymentTerm, wired to their update views.

**Tech Stack:** Django 5.2.14, django-simple-history (already in `INSTALLED_APPS` at `config/settings/base.py:30`), Bootstrap 5, HTMX, crispy-forms (bootstrap5 pack).

---

## Pre-flight: verified codebase state

Before starting:
- `simple_history` **already** in `INSTALLED_APPS` (`config/settings/base.py:30`) — no change needed.
- `HistoryRequestMiddleware` **not yet** in `MIDDLEWARE`.
- `ERPBaseModel` (`apps/core/models.py:82`) **does not** have `HistoricalRecords` yet.
- `apps/core/history.py`, `apps/core/services.py`, `apps/core/mixins.py` — do not exist.
- `templates/components/history/` — does not exist.

Models that inherit `ERPBaseModel` (will get history tables):
| App | Models |
|---|---|
| accounts | User, Organization, Team, Membership, Invitation |
| items | Item |
| invoices | Customer, CustomerDepartment, Invoice, Payment, PaymentAllocation, PaymentTerm |
| core | Notification |

Models that do **NOT** inherit `ERPBaseModel` (skip their admins):
- `NCFSequence`, `DocumentSequence` (invoices)
- `ItemCodeSequence` (items)
- `Module` (core)

---

## File map

| Action | Path |
|---|---|
| Modify | `config/settings/base.py` |
| Modify | `apps/core/models.py` |
| **Create** | `apps/core/history.py` |
| **Create** | `apps/core/services.py` |
| Modify | `apps/core/admin.py` |
| Modify | `apps/accounts/admin.py` |
| Modify | `apps/items/admin.py` |
| Modify | `apps/invoices/admin.py` |
| **Create** | `apps/core/mixins.py` |
| **Create** | `templates/components/history/timeline.html` |
| **Create** | `templates/components/history/timeline_panel.html` |
| Modify | `apps/invoices/forms.py` |
| Modify | `apps/invoices/views/customers.py` |
| Modify | `apps/invoices/views/payment_terms.py` |
| Modify | `apps/items/forms.py` |
| Modify | `apps/items/views.py` |

---

## Task 1 — Phase 1: Middleware + ERPBaseModel + migrations

**Files:**
- Modify: `config/settings/base.py:42-56`
- Modify: `apps/core/models.py:82-98`

- [ ] **Step 1: Add HistoryRequestMiddleware to MIDDLEWARE**

Open `config/settings/base.py`. After line 47 (`"django.contrib.sessions.middleware.SessionMiddleware"`) insert the middleware. The result should look like:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",   # ← add this line
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.accounts.middleware.OrganizationMiddleware",
]
```

- [ ] **Step 2: Add HistoricalRecords to ERPBaseModel**

Open `apps/core/models.py`. Add the import at the top (after existing imports) and add `history` to `ERPBaseModel`. The class becomes:

```python
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords   # ← add


# ... TimeStampedModel, SoftDeleteQuerySet, SoftDeleteManager, SoftDeleteModel unchanged ...


class ERPBaseModel(TimeStampedModel, SoftDeleteModel):
    """
    Root abstract model for every SabSys entity.

    Entity models (anything with an org scope) must declare:
        organization = models.ForeignKey("accounts.Organization", ...)

    Identity models (Organization and User) are exempt — they ARE the root.

    Queries are always written as:
        MyModel.objects.for_org(request.organization)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
```

Do NOT change `Meta.ordering` or any existing field.

- [ ] **Step 3: Run makemigrations and verify output**

```bash
python manage.py makemigrations
```

Expected: One migration file created per app that has an ERPBaseModel subclass. Verify these migration files are created (filenames will vary):

```
apps/accounts/migrations/000X_historical_user_historical_organization_historical_team_historical_membership_historical_invitation.py
apps/items/migrations/000X_historical_item.py
apps/invoices/migrations/000X_historical_customer_historical_invoice_historical_payment_historical_paymentterm.py
apps/core/migrations/000X_historical_notification.py
```

If you see errors about `history` field conflicts on concrete models, that means some model already has a `history` attribute — report it and do not proceed.

Do NOT run `migrate` yet.

- [ ] **Step 4: Commit**

```bash
git add config/settings/base.py apps/core/models.py apps/*/migrations/
git commit -m "feat(history): add HistoricalRecords to ERPBaseModel, add HistoryRequestMiddleware"
```

---

## Task 2 — Phase 2: Core history helper + service convention

**Files:**
- Create: `apps/core/history.py`
- Create: `apps/core/services.py`

- [ ] **Step 1: Create apps/core/history.py**

```python
from simple_history.utils import update_change_reason


def record_change_reason(instance, reason: str):
    """Attach a human-readable change reason to the latest history record."""
    if reason:
        update_change_reason(instance, reason)
```

- [ ] **Step 2: Create apps/core/services.py**

```python
"""
Service layer conventions for SabSys.

Every service module must follow these rules for history integration:

1. Import the helper:
       from apps.core.history import record_change_reason

2. After any .save() call where a change_reason string is available:
       instance.save()
       record_change_reason(instance, reason)

3. For mutations outside a request context (management commands, Celery tasks),
   attach the acting user before saving so history records the correct user:
       instance._history_user = acting_user
       instance.save()
       record_change_reason(instance, reason)

These rules apply to all services in apps/<app>/services.py.
Existing services are not modified; this file documents the convention only.
"""
```

- [ ] **Step 3: Commit**

```bash
git add apps/core/history.py apps/core/services.py
git commit -m "feat(history): add record_change_reason helper and service convention doc"
```

---

## Task 3 — Phase 3: Admin integration

**Files:**
- Modify: `apps/core/admin.py`
- Modify: `apps/accounts/admin.py`
- Modify: `apps/items/admin.py`
- Modify: `apps/invoices/admin.py`

### Step 1: Add ERPHistoryAdmin to apps/core/admin.py

Current file registers `ModuleAdmin`. `Module` does NOT inherit `ERPBaseModel`, so `ModuleAdmin` stays as `admin.ModelAdmin`. We only ADD the `ERPHistoryAdmin` class. Full replacement of `apps/core/admin.py`:

- [ ] **Step 1: Rewrite apps/core/admin.py**

```python
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Module


class ERPHistoryAdmin(SimpleHistoryAdmin):
    """Base admin for all SabSys models — includes history tab automatically."""
    history_list_display = ["history_user", "history_date", "history_change_reason"]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "icon", "is_active"]
    list_editable = ["is_active"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "slug"]
```

- [ ] **Step 2: Update apps/accounts/admin.py**

`UserAdmin` extends `BaseUserAdmin` (not plain `admin.ModelAdmin`) and has complex fieldsets — leave it unchanged. Update the remaining four admins. Full replacement:

```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organization, Team, Membership, Invitation
from apps.core.admin import ERPHistoryAdmin


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "is_staff", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "avatar")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )


@admin.register(Organization)
class OrganizationAdmin(ERPHistoryAdmin):
    list_display = ["name", "slug", "owner", "is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Team)
class TeamAdmin(ERPHistoryAdmin):
    list_display = ["name", "organization"]
    list_filter = ["organization"]


@admin.register(Membership)
class MembershipAdmin(ERPHistoryAdmin):
    list_display = ["user", "organization", "team", "role"]
    list_filter = ["role", "organization"]


@admin.register(Invitation)
class InvitationAdmin(ERPHistoryAdmin):
    list_display = ["email", "organization", "role", "invited_by", "expires_at", "accepted_at"]
    list_filter = ["organization", "role"]
    search_fields = ["email"]
    readonly_fields = ["accepted_at", "expires_at", "invited_by"]
```

- [ ] **Step 3: Update apps/items/admin.py**

`ItemCodeSequence` does NOT inherit `ERPBaseModel` — leave `ItemCodeSequenceAdmin` as `admin.ModelAdmin`. Only `ItemAdmin` changes. Full replacement:

```python
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.core.admin import ERPHistoryAdmin
from .models import Item, ItemCodeSequence


@admin.register(Item)
class ItemAdmin(ERPHistoryAdmin):
    list_display   = ["__str__", "item_type", "unit", "unit_price", "cost_price",
                      "itbis_rate", "is_active", "organization"]
    list_filter    = ["organization", "item_type", "itbis_rate", "unit", "is_active"]
    search_fields  = ["name", "code"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (_("General"), {
            "fields": ("organization", "code", "name", "item_type"),
        }),
        (_("Precio y unidad"), {
            "fields": ("unit", "unit_price", "cost_price", "itbis_rate"),
        }),
        (_("Estado"), {
            "fields": ("is_active", "notes"),
        }),
        (_("Auditoría"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(ItemCodeSequence)
class ItemCodeSequenceAdmin(admin.ModelAdmin):
    list_display  = ["organization", "prefix", "current_seq", "next_code", "updated_at"]
    readonly_fields = ["current_seq", "updated_at", "next_code"]
    fields        = ["organization", "prefix", "current_seq", "next_code", "updated_at"]

    def next_code(self, obj):
        """Preview of the next code that would be generated."""
        return f"{obj.prefix}-{obj.current_seq + 1:04d}"
    next_code.short_description = _("próximo código")
```

- [ ] **Step 4: Update apps/invoices/admin.py**

`NCFSequence`, `DocumentSequence` do NOT inherit `ERPBaseModel` — leave their admins as `admin.ModelAdmin`. Update all others. Full replacement:

```python
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.core.admin import ERPHistoryAdmin
from .models import (
    Customer, CustomerDepartment, DocumentSequence, Invoice, InvoiceItem,
    NCFSequence, Payment, PaymentAllocation, PaymentTerm,
)


class CustomerDepartmentInline(admin.TabularInline):
    model   = CustomerDepartment
    extra   = 0
    fields  = ["name", "contact_name", "phone", "address", "is_active"]
    ordering = ["name"]


@admin.register(Customer)
class CustomerAdmin(ERPHistoryAdmin):
    list_display   = ["name", "id_type", "rnc_cedula", "email", "organization", "default_ncf_type"]
    list_filter    = ["organization", "id_type", "default_ncf_type"]
    search_fields  = ["name", "rnc_cedula", "email"]
    readonly_fields = ["created_at", "updated_at"]
    inlines        = [CustomerDepartmentInline]


@admin.register(CustomerDepartment)
class CustomerDepartmentAdmin(ERPHistoryAdmin):
    list_display  = ["name", "customer", "contact_name", "phone", "is_active", "organization"]
    list_filter   = ["organization", "is_active"]
    search_fields = ["name", "customer__name", "contact_name"]
    readonly_fields = ["created_at", "updated_at"]


class InvoiceItemInline(admin.TabularInline):
    model  = InvoiceItem
    extra  = 0
    fields = ["item", "description", "quantity", "unit_price", "itbis_rate",
              "line_total", "itbis_amount", "line_total_with_itbis"]
    readonly_fields = ["line_total", "itbis_amount", "line_total_with_itbis"]


@admin.register(Invoice)
class InvoiceAdmin(ERPHistoryAdmin):
    list_display   = ["display_number", "doc_type", "customer", "issue_date", "total", "status", "organization"]
    list_filter    = ["doc_type", "status", "ncf_type", "organization"]
    search_fields  = ["encf", "doc_number", "customer__name", "customer__rnc_cedula"]
    readonly_fields = [
        "encf", "doc_number", "created_at", "updated_at",
        "subtotal", "itbis_18", "itbis_16", "total",
        "dgii_status", "dgii_track_id", "xml_content",
    ]
    inlines = [InvoiceItemInline]
    fieldsets = (
        (_("Tipo"), {
            "fields": ("doc_type", "organization", "customer", "status"),
        }),
        (_("Comprobante fiscal (Factura)"), {
            "fields": ("encf", "ncf_type", "encf_modified"),
            "classes": ("collapse",),
        }),
        (_("Documento no fiscal (Cotización / Orden)"), {
            "fields": ("doc_number", "valid_until", "delivery_date", "signed_by", "consolidated_into"),
            "classes": ("collapse",),
        }),
        (_("Fechas y condiciones"), {
            "fields": ("issue_date", "due_date", "payment_condition", "currency", "exchange_rate"),
        }),
        (_("Totales"), {
            "fields": ("subtotal", "itbis_18", "itbis_16", "total"),
            "classes": ("collapse",),
        }),
        (_("Notas"), {
            "fields": ("notes", "terms"),
            "classes": ("collapse",),
        }),
        (_("DGII (Fase 2)"), {
            "fields": ("dgii_status", "dgii_track_id", "xml_content"),
            "classes": ("collapse",),
        }),
        (_("Auditoría"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display   = ["organization", "doc_type", "current_seq", "updated_at"]
    list_filter    = ["organization", "doc_type"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(NCFSequence)
class NCFSequenceAdmin(admin.ModelAdmin):
    list_display   = ["organization", "ncf_type", "series", "current_seq", "max_seq", "is_active"]
    list_filter    = ["organization", "ncf_type", "is_active"]
    readonly_fields = ["created_at", "updated_at"]


class PaymentAllocationInline(admin.TabularInline):
    model   = PaymentAllocation
    extra   = 0
    fields  = ["invoice", "amount"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["invoice"]


@admin.register(Payment)
class PaymentAdmin(ERPHistoryAdmin):
    list_display    = ["customer", "amount", "date", "method", "reference", "organization"]
    list_filter     = ["method", "organization", "date"]
    search_fields   = ["customer__name", "reference"]
    readonly_fields = ["created_at", "updated_at"]
    inlines         = [PaymentAllocationInline]


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(ERPHistoryAdmin):
    list_display  = ["payment", "invoice", "amount", "created_at"]
    search_fields = ["payment__reference", "invoice__encf", "invoice__doc_number"]
    readonly_fields = ["created_at"]


@admin.register(PaymentTerm)
class PaymentTermAdmin(ERPHistoryAdmin):
    list_display   = ["name", "days_due", "description"]
    search_fields  = ["name"]
    ordering       = ["days_due"]
```

**Note on PaymentAllocation:** Verify `PaymentAllocation` inherits `ERPBaseModel` before changing its admin. If it does not, revert `PaymentAllocationAdmin` to `admin.ModelAdmin`.

- [ ] **Step 5: Commit**

```bash
git add apps/core/admin.py apps/accounts/admin.py apps/items/admin.py apps/invoices/admin.py
git commit -m "feat(history): add ERPHistoryAdmin to all ERPBaseModel admin classes"
```

---

## Task 4 — Phase 4: HistoryMixin + timeline template components

**Files:**
- Create: `apps/core/mixins.py`
- Create: `templates/components/history/timeline.html`
- Create: `templates/components/history/timeline_panel.html`

- [ ] **Step 1: Create apps/core/mixins.py**

```python
class HistoryMixin:
    history_limit = 20

    def get_history(self, obj):
        records = list(
            obj.history.select_related("history_user").order_by("-history_date")[: self.history_limit]
        )
        for record in records:
            record.delta = record.diff_against(record.prev_record) if record.prev_record else None
        return records
```

The `.delta` attribute is computed once here so Django templates (which cannot call methods with arguments) can access it as `record.delta`.

- [ ] **Step 2: Create templates/components/history/timeline.html**

First create the directory: `mkdir -p templates/components/history`

```django
{% load i18n humanize %}
<div class="history-timeline">
  {% if history_records %}
    {% for record in history_records %}
    <div class="d-flex gap-3 py-3 {% if not forloop.last %}border-bottom{% endif %}">
      {# Icon column #}
      <div class="flex-shrink-0 text-center" style="width: 2rem;">
        {% if record.history_type == "+" %}
          <span class="badge bg-success">+</span>
        {% elif record.history_type == "~" %}
          <span class="badge bg-warning text-dark">~</span>
        {% else %}
          <span class="badge bg-danger">-</span>
        {% endif %}
      </div>

      {# Content column #}
      <div class="flex-grow-1">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            {# Change type label #}
            {% if record.history_type == "+" %}
              <span class="badge bg-success me-1">{% trans "Creado" %}</span>
            {% elif record.history_type == "~" %}
              <span class="badge bg-warning text-dark me-1">{% trans "Modificado" %}</span>
            {% else %}
              <span class="badge bg-danger me-1">{% trans "Eliminado" %}</span>
            {% endif %}

            {# Actor #}
            <span class="fw-semibold small">
              {% if record.history_user %}
                {{ record.history_user.get_full_name|default:record.history_user.email }}
              {% else %}
                {% trans "Sistema" %}
              {% endif %}
            </span>
          </div>

          {# Timestamp #}
          <small class="text-muted text-nowrap ms-2">
            {{ record.history_date|naturaltime }}
          </small>
        </div>

        {# Diff: field-level changes #}
        {% if record.delta and record.delta.changes %}
          <dl class="row small mb-1 mt-1">
            {% for change in record.delta.changes %}
            <dt class="col-sm-4 text-muted fw-normal">{{ change.field }}</dt>
            <dd class="col-sm-8 mb-0">
              <span class="text-decoration-line-through text-muted me-1">{{ change.old|default:"—" }}</span>
              <i class="bi bi-arrow-right text-secondary"></i>
              <span class="ms-1">{{ change.new|default:"—" }}</span>
            </dd>
            {% endfor %}
          </dl>
        {% endif %}

        {# Change reason #}
        {% if record.history_change_reason %}
          <em class="small text-secondary">{{ record.history_change_reason }}</em>
        {% endif %}
      </div>
    </div>
    {% endfor %}
  {% else %}
    <p class="text-muted small px-3 py-2 mb-0">{% trans "Sin historial registrado." %}</p>
  {% endif %}
</div>
```

- [ ] **Step 3: Create templates/components/history/timeline_panel.html**

```django
{% load i18n %}
<div class="card mt-4">
  <div class="card-header d-flex align-items-center gap-2">
    <i class="bi bi-clock-history"></i>
    <strong>{% trans "Historial de cambios" %}</strong>
  </div>
  <div class="card-body p-0">
    {% include "components/history/timeline.html" with history_records=history_records %}
  </div>
</div>
```

- [ ] **Step 4: Commit**

```bash
git add apps/core/mixins.py templates/components/history/
git commit -m "feat(history): add HistoryMixin and timeline template components"
```

---

## Task 5 — Phase 5a: change_reason on Customer

**Files:**
- Modify: `apps/invoices/forms.py` (CustomerForm section, lines 29–117)
- Modify: `apps/invoices/views/customers.py` (CustomerUpdateView.form_valid, lines 173–196)

The `customer_modal_form.html` uses `{% crispy form %}` — adding `change_reason` to the form's crispy `Layout` is sufficient; no template changes needed.

- [ ] **Step 1: Add change_reason to CustomerForm**

In `apps/invoices/forms.py`, add the field declaration after the class `Meta` block and before `__init__`:

```python
class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name", "id_type", "rnc_cedula", "email", "phone",
            "contact_name", "contact_number", "address", "city",
            "province", "country", "default_ncf_type", "payment_term",
            "credit_limit", "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    change_reason = forms.CharField(
        required=False,
        label=_("Motivo del cambio"),
        widget=forms.TextInput(attrs={
            "placeholder": _("Ej. Corrección de datos, actualización de crédito…")
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ... all existing __init__ code unchanged ...
```

Then in `__init__`, append `"change_reason"` as the last item in the crispy `Layout`, after the `"notes"` column. The final `Layout` block should end:

```python
        self.helper.layout = Layout(
            # ... all existing layout items unchanged ...
            Row(
                Column("default_ncf_type", css_class="col-md-6"),
                Column("payment_term", css_class="col-md-6"),
                Column("credit_limit", css_class="col-md-4"),
                Column("notes", css_class="col-md-12"),
            ),
            "change_reason",   # ← add as last item
        )
```

- [ ] **Step 2: Wire change_reason in CustomerUpdateView.form_valid**

In `apps/invoices/views/customers.py`, add the import at the top of the file:

```python
from apps.core.history import record_change_reason
```

Then in `CustomerUpdateView.form_valid`, call `record_change_reason` immediately after the parent's `form_valid` saves the instance:

```python
    def form_valid(self, form):
        response = super().form_valid(form)
        record_change_reason(self.object, form.cleaned_data.get("change_reason", ""))
        if self.request.htmx:
            # ... rest of existing htmx logic unchanged ...
```

**Important:** `super().form_valid(form)` calls `form.save()` internally and sets `self.object`. Call `record_change_reason` after `super().form_valid()` so `self.object` is the saved instance.

- [ ] **Step 3: Verify the field works in the modal**

Since `customer_modal_form.html` renders `{% crispy form %}`, the `change_reason` field will appear automatically as the last field in the form body before the modal footer buttons. No template changes needed.

- [ ] **Step 4: Commit**

```bash
git add apps/invoices/forms.py apps/invoices/views/customers.py
git commit -m "feat(history): add change_reason to CustomerForm and CustomerUpdateView"
```

---

## Task 6 — Phase 5b: change_reason on Item

**Files:**
- Modify: `apps/items/forms.py`
- Modify: `apps/items/views.py` (ItemUpdateView.post, lines 166–196)

The `item_modal_form.html` uses `{% crispy form %}` — adding `change_reason` to Layout is sufficient.

- [ ] **Step 1: Add change_reason to ItemForm**

In `apps/items/forms.py`, add the field declaration after `class Meta:` and before `def __init__`:

```python
class ItemForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = Item
        fields = [
            "code", "name", "item_type", "unit",
            "unit_price", "cost_price", "itbis_rate",
            "is_active", "notes",
        ]
        widgets = {
            "notes":       forms.Textarea(attrs={"rows": 1}),
            "unit_price":  forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "cost_price":  forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "item_type":   forms.Select(attrs={"x-model": "itemType"}),
            "code":        forms.TextInput(attrs={":placeholder": "codePlaceholder"}),
        }
        error_messages = {
            "name":       {"required": _("El nombre es obligatorio.")},
            "item_type":  {"required": _("El tipo de artículo es obligatorio.")},
            "unit":       {"required": _("La unidad de medida es obligatoria.")},
            "unit_price": {"required": _("El precio de venta es obligatorio.")},
            "itbis_rate": {"required": _("La tasa ITBIS es obligatoria.")},
        }

    change_reason = forms.CharField(
        required=False,
        label=_("Motivo del cambio"),
        widget=forms.TextInput(attrs={
            "placeholder": _("Ej. Corrección de precio, ajuste de inventario…")
        }),
    )

    def __init__(self, *args, **kwargs):
        # ... all existing __init__ code unchanged ...
```

In `__init__`, append `"change_reason"` as the last item in the crispy Layout, after `"notes"`:

```python
        self.helper.layout = Layout(
            # ... all existing layout items unchanged ...
            Field("is_active"),
            "notes",
            "change_reason",   # ← add as last item
        )
```

- [ ] **Step 2: Wire change_reason in ItemUpdateView.post**

In `apps/items/views.py`, add the import at the top:

```python
from apps.core.history import record_change_reason
```

In `ItemUpdateView.post`, after `form.save()` succeeds:

```python
    def post(self, request, pk):
        item = get_object_or_404(Item, pk=pk, organization=_org(request))
        form = ItemForm(request.POST, instance=item)

        if form.is_valid():
            item = form.save()
            record_change_reason(item, form.cleaned_data.get("change_reason", ""))
            if request.htmx:
                return ItemListView.refresh_table(request, _("Artículo actualizado correctamente."))
            messages.success(request, _("Artículo actualizado correctamente."))
            return redirect("items:item_detail", pk=item.pk)

        # ... rest of existing error handling unchanged ...
```

Note: `form.save()` returns the saved instance; assign it back to `item` so `record_change_reason` operates on the refreshed object.

- [ ] **Step 3: Commit**

```bash
git add apps/items/forms.py apps/items/views.py
git commit -m "feat(history): add change_reason to ItemForm and ItemUpdateView"
```

---

## Task 7 — Phase 5c: change_reason on PaymentTerm

**Files:**
- Modify: `apps/invoices/forms.py` (PaymentTermForm section, lines 543–575)
- Modify: `apps/invoices/views/payment_terms.py` (PaymentTermUpdateView.post, lines 138–168)

- [ ] **Step 1: Add change_reason to PaymentTermForm**

In `apps/invoices/forms.py`, in `PaymentTermForm`, add the field after `class Meta:` and before `def __init__`:

```python
class PaymentTermForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = PaymentTerm
        fields = ["name", "description", "days_due"]
        labels = {
            "name":        _("Nombre"),
            "description": _("Descripción"),
            "days_due":    _("Días de vencimiento"),
        }
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": _("Ej. Pago a 30 días")}),
        }
        help_texts = {
            "days_due": _("Número de días desde la emisión hasta el vencimiento."),
        }
        error_messages = {
            "name":     {"required": _("El nombre es obligatorio.")},
            "days_due": {"required": _("Los días de vencimiento son obligatorios.")},
        }

    change_reason = forms.CharField(
        required=False,
        label=_("Motivo del cambio"),
        widget=forms.TextInput(attrs={
            "placeholder": _("Ej. Corrección de nombre, ajuste de días…")
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("name",     css_class="col-md-8"),
                Column("days_due", css_class="col-md-4"),
            ),
            "description",
            "change_reason",   # ← add as last item
        )
```

- [ ] **Step 2: Wire change_reason in PaymentTermUpdateView.post**

In `apps/invoices/views/payment_terms.py`, add the import at the top:

```python
from apps.core.history import record_change_reason
```

In `PaymentTermUpdateView.post`, after `form.save()` succeeds:

```python
    def post(self, request, pk):
        term = get_object_or_404(PaymentTerm, pk=pk, organization=_org(request))
        form = PaymentTermForm(request.POST, instance=term)

        if form.is_valid():
            term = form.save()
            record_change_reason(term, form.cleaned_data.get("change_reason", ""))
            if request.htmx:
                return PaymentTermListView.refresh_table(
                    request, _("Término de pago actualizado correctamente.")
                )
            messages.success(request, _("Término de pago actualizado correctamente."))
            return redirect("invoices:payment_term_list")

        # ... rest of existing error handling unchanged ...
```

- [ ] **Step 3: Commit**

```bash
git add apps/invoices/forms.py apps/invoices/views/payment_terms.py
git commit -m "feat(history): add change_reason to PaymentTermForm and PaymentTermUpdateView"
```

---

## Task 8 — Run migrate and smoke test

- [ ] **Step 1: Run migrate**

```bash
python manage.py migrate
```

Expected: All historical tables created without errors. Any error here is a blocker — do not proceed.

- [ ] **Step 2: Start dev server and verify admin**

```bash
python manage.py runserver
```

Navigate to `/admin/` → open any Customer, Item, or Invoice record. Verify a "History" button or inline appears showing the record's history entries.

- [ ] **Step 3: Verify change_reason modal field**

In the SabSys UI, open the edit modal for a Customer or Item. Verify "Motivo del cambio" field appears as the last form field before the action buttons.

Make a small change, fill in a reason, save. Go to the Django admin for that record → History → verify the reason appears in `history_change_reason`.

- [ ] **Step 4: Final commit if everything passes**

```bash
git commit --allow-empty -m "chore: verify django-simple-history integration complete"
```

---

## Summary: files changed per phase

| Phase | Files |
|---|---|
| Phase 1 | `config/settings/base.py`, `apps/core/models.py`, `apps/*/migrations/` |
| Phase 2 | `apps/core/history.py` *(new)*, `apps/core/services.py` *(new)* |
| Phase 3 | `apps/core/admin.py`, `apps/accounts/admin.py`, `apps/items/admin.py`, `apps/invoices/admin.py` |
| Phase 4 | `apps/core/mixins.py` *(new)*, `templates/components/history/timeline.html` *(new)*, `templates/components/history/timeline_panel.html` *(new)* |
| Phase 5 | `apps/invoices/forms.py`, `apps/invoices/views/customers.py`, `apps/invoices/views/payment_terms.py`, `apps/items/forms.py`, `apps/items/views.py` |
