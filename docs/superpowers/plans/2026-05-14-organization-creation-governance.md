# Organization Creation Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict organization creation to `is_staff` platform admins, replacing the name-only form with a full-detail form that atomically creates the org and sends an OWNER invitation.

**Architecture:** `CreateOrganizationView` gains an `is_staff` guard in `dispatch()`. `CreateOrganizationForm` (name-only) is replaced by `StaffCreateOrganizationForm` (ModelForm with all org fields + `owner_email`). On POST, the view creates the org and an OWNER `Invitation` inside `transaction.atomic()`, calls `send_invitation_email()`, and redirects back to the staff admin's current dashboard without switching their active org. UI surfaces via a staff-only "Plataforma" sidebar section; the navbar link is hidden from non-staff.

**Tech Stack:** Django 4.x, crispy-forms (bootstrap5), pytest-django, Bootstrap 5

---

## File Map

| File | Change |
|------|--------|
| `apps/accounts/forms.py` | Remove `CreateOrganizationForm`; add `StaffCreateOrganizationForm` (ModelForm + owner_email) |
| `apps/accounts/views.py` | Rewrite `CreateOrganizationView`; update import line; add `transaction` import |
| `apps/accounts/tests/test_create_org.py` | New test file — access control + creation behaviour |
| `templates/accounts/create_org.html` | Full rewrite — warning notice, crispy form, cancel link |
| `templates/partials/_navbar.html` | Wrap "Nueva organización" link with `{% if request.user.is_staff %}` |
| `templates/partials/_sidebar.html` | Add "Plataforma" section guarded by `{% if request.user.is_staff %}` |

---

## Task 1: Form — Replace `CreateOrganizationForm` with `StaffCreateOrganizationForm`

**Files:**
- Modify: `apps/accounts/forms.py`

- [ ] **Step 1: Remove `CreateOrganizationForm` and add `StaffCreateOrganizationForm`**

In `apps/accounts/forms.py`, delete the entire `CreateOrganizationForm` class:
```python
class CreateOrganizationForm(forms.Form):
    name = forms.CharField(
        max_length=255,
        label=_("Nombre de la organización"),
        widget=forms.TextInput(attrs={"placeholder": "Mi Empresa S.R.L.", "autofocus": True}),
    )
```

Add `StaffCreateOrganizationForm` in its place:

```python
class StaffCreateOrganizationForm(forms.ModelForm):
    owner_email = forms.EmailField(
        label=_("Correo del propietario"),
        help_text=_("Se enviará una invitación de propietario a esta dirección."),
        widget=forms.EmailInput(attrs={"placeholder": "propietario@empresa.com"}),
    )

    class Meta:
        model = Organization
        fields = [
            "name",
            "tax_id", "email", "phone", "website",
            "address", "city", "state", "zip_code", "country",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs["autofocus"] = True
        for field_name, field in self.fields.items():
            if field_name not in ("name", "owner_email"):
                field.required = False
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            "name",
            HTML(f'<hr class="my-3"><p class="text-muted small text-uppercase mb-3">{_("Contacto")}</p>'),
            Row(
                Column("tax_id", css_class="col-md-6"),
                Column("email", css_class="col-md-6"),
            ),
            Row(
                Column("phone", css_class="col-md-6"),
                Column("website", css_class="col-md-6"),
            ),
            HTML(f'<hr class="my-3"><p class="text-muted small text-uppercase mb-3">{_("Dirección")}</p>'),
            "address",
            Row(
                Column("city", css_class="col-md-5"),
                Column("state", css_class="col-md-4"),
                Column("zip_code", css_class="col-md-3"),
            ),
            "country",
            HTML(f'<hr class="my-3"><p class="text-muted small text-uppercase mb-3">{_("Propietario")}</p>'),
            "owner_email",
        )

    def clean_owner_email(self):
        return self.cleaned_data["owner_email"].lower()
```

- [ ] **Step 2: Verify the form imports compile**

```bash
python manage.py shell -c "from apps.accounts.forms import StaffCreateOrganizationForm; print('OK')"
```

Expected output: `OK`

---

## Task 2: View — Rewrite `CreateOrganizationView`

**Files:**
- Modify: `apps/accounts/views.py`

- [ ] **Step 1: Update the import lines at the top of the file**

Find line 20:
```python
from .forms import ProfileForm, OrganizationForm, InvitationForm, TeamForm, CreateOrganizationForm
```
Replace with:
```python
from .forms import ProfileForm, OrganizationForm, InvitationForm, TeamForm, StaffCreateOrganizationForm
```

Find the existing Django imports block (lines ~1–18). Add `transaction` import — find:
```python
from django.contrib import messages
```
Add after it (or alongside other `django.db` imports if any):
```python
from django.db import transaction
```

- [ ] **Step 2: Replace the entire `CreateOrganizationView` class**

Find the class starting at `class CreateOrganizationView(ERPBaseViewMixin, TemplateView):` through its last line (`return redirect("accounts:org_settings")`). Replace with:

```python
class CreateOrganizationView(ERPBaseViewMixin, TemplateView):
    template_name = "accounts/create_org.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, _("No tienes permiso para crear organizaciones."))
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", StaffCreateOrganizationForm())
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Plataforma")},
            {"label": _("Nueva organización")},
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        form = StaffCreateOrganizationForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        owner_email = form.cleaned_data["owner_email"]
        name = form.cleaned_data["name"]
        base_slug = slugify(name) or "org"
        slug = base_slug
        counter = 1
        while Organization.all_objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        with transaction.atomic():
            org = form.save(commit=False)
            org.slug = slug
            org.owner = request.user
            org.save()
            invitation = Invitation.create_for(
                email=owner_email,
                organization=org,
                role=Membership.Role.OWNER,
                invited_by=request.user,
            )

        send_invitation_email(invitation, request)
        messages.success(
            request,
            _('Organización "%(name)s" creada. Invitación enviada a %(email)s.') % {
                "name": org.name,
                "email": owner_email,
            },
        )
        return redirect("accounts:dashboard")
```

- [ ] **Step 3: Verify the view imports compile**

```bash
python manage.py shell -c "from apps.accounts.views import CreateOrganizationView; print('OK')"
```

Expected output: `OK`

---

## Task 3: Tests — Access control and creation behaviour

**Files:**
- Create: `apps/accounts/tests/test_create_org.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/accounts/tests/test_create_org.py` with:

```python
import pytest
from django.urls import reverse
from apps.accounts.models import Organization, Membership, Invitation


CREATE_URL = reverse("accounts:create_org")


@pytest.mark.django_db
class TestCreateOrganizationAccess:

    def test_anonymous_redirected(self, client):
        response = client.get(CREATE_URL)
        assert response.status_code == 302
        assert "/auth/login/" in response["Location"]

    def test_non_staff_redirected_to_dashboard(self, client, owner_membership):
        client.force_login(owner_membership.user)
        session = client.session
        session["active_org_slug"] = owner_membership.organization.slug
        session.save()
        response = client.get(CREATE_URL)
        assert response.status_code == 302
        assert response["Location"] == reverse("accounts:dashboard")

    def test_staff_can_access(self, client, owner_membership):
        owner_membership.user.is_staff = True
        owner_membership.user.save()
        client.force_login(owner_membership.user)
        session = client.session
        session["active_org_slug"] = owner_membership.organization.slug
        session.save()
        response = client.get(CREATE_URL)
        assert response.status_code == 200


@pytest.mark.django_db
class TestCreateOrganizationPost:

    def _staff_client(self, client, owner_membership):
        owner_membership.user.is_staff = True
        owner_membership.user.save()
        client.force_login(owner_membership.user)
        session = client.session
        session["active_org_slug"] = owner_membership.organization.slug
        session.save()
        return client

    def test_creates_organization(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        assert Organization.objects.filter(name="Acme S.R.L.").exists()

    def test_creates_owner_invitation(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        org = Organization.objects.get(name="Acme S.R.L.")
        inv = Invitation.objects.get(organization=org)
        assert inv.email == "owner@acme.com"
        assert inv.role == Membership.Role.OWNER

    def test_sends_invitation_email(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        assert len(mailoutbox) == 1
        assert "owner@acme.com" in mailoutbox[0].to

    def test_staff_admin_not_added_as_member(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        org = Organization.objects.get(name="Acme S.R.L.")
        assert not Membership.objects.filter(
            user=owner_membership.user, organization=org
        ).exists()

    def test_active_org_unchanged(self, client, owner_membership, mailoutbox):
        original_slug = owner_membership.organization.slug
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        session = client.session
        assert session.get("active_org_slug") == original_slug

    def test_redirects_to_dashboard(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        response = c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        assert response.status_code == 302
        assert response["Location"] == reverse("accounts:dashboard")

    def test_invalid_form_rerenders(self, client, owner_membership):
        c = self._staff_client(client, owner_membership)
        response = c.post(CREATE_URL, {"name": "", "owner_email": "owner@acme.com"})
        assert response.status_code == 200

    def test_owner_email_normalised_to_lowercase(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "Owner@ACME.com"})
        org = Organization.objects.get(name="Acme S.R.L.")
        inv = Invitation.objects.get(organization=org)
        assert inv.email == "owner@acme.com"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest apps/accounts/tests/test_create_org.py -v
```

Expected: Most tests FAIL — `StaffCreateOrganizationForm` not yet wired in view (Task 2 handles this), or `CreateOrganizationView` still uses old form.

After completing Tasks 1 and 2, all tests should pass.

- [ ] **Step 3: Run tests to verify they pass**

```bash
pytest apps/accounts/tests/test_create_org.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 4: Run full test suite to check for regressions**

```bash
pytest apps/accounts/ -v
```

Expected: All existing tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/forms.py apps/accounts/views.py apps/accounts/tests/test_create_org.py
git commit -m "feat: restrict org creation to is_staff, add StaffCreateOrganizationForm

- CreateOrganizationForm removed; StaffCreateOrganizationForm adds full
  org fields (ModelForm) plus required owner_email field
- CreateOrganizationView guarded by is_staff check in dispatch()
- Creates org + OWNER invitation atomically; staff admin not added as
  member and active org unchanged after creation"
```

---

## Task 4: Template — Rewrite `create_org.html`

**Files:**
- Modify: `templates/accounts/create_org.html`

- [ ] **Step 1: Replace the entire template**

```django
{% extends "base.html" %}
{% load i18n crispy_forms_tags %}

{% block title %}{% trans "Nueva organización" %} — SabSys{% endblock %}

{% block content %}
<div class="row justify-content-center">
  <div class="col-12 col-xl-8">

    <div class="d-flex align-items-center justify-content-between mb-4">
      <div>
        <h4 class="fw-bold mb-0">{% trans "Nueva organización" %}</h4>
        <span class="text-muted small">{% trans "Crear espacio de trabajo para un cliente" %}</span>
      </div>
      <a href="{% url 'accounts:dashboard' %}" class="btn btn-outline-secondary btn-sm">
        <i class="bi bi-arrow-left me-1"></i>{% trans "Cancelar" %}
      </a>
    </div>

    <div class="alert alert-warning d-flex align-items-start gap-2 mb-4" role="alert">
      <i class="bi bi-exclamation-triangle-fill flex-shrink-0 mt-1"></i>
      <div>
        <strong>{% trans "Acción irreversible." %}</strong>
        {% trans "Esta acción crea un espacio de trabajo independiente. Los datos no pueden transferirse entre organizaciones." %}
      </div>
    </div>

    <div class="card border-0 shadow-sm">
      <div class="card-body p-4">
        <form method="post" novalidate>
          {% csrf_token %}
          {% crispy form %}
          <div class="d-flex justify-content-end gap-2 mt-4">
            <a href="{% url 'accounts:dashboard' %}" class="btn btn-outline-secondary btn-sm">
              {% trans "Cancelar" %}
            </a>
            <button type="submit" class="btn btn-primary btn-sm">
              <i class="bi bi-building-add me-1"></i>
              {% trans "Crear organización y enviar invitación" %}
            </button>
          </div>
        </form>
      </div>
    </div>

  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add templates/accounts/create_org.html
git commit -m "feat: rewrite create_org template for staff flow

- Warning notice about irreversibility
- Full crispy form with all org fields + owner_email section
- Cancel links to dashboard"
```

---

## Task 5: Navigation — Guard navbar link + add sidebar Plataforma section

**Files:**
- Modify: `templates/partials/_navbar.html`
- Modify: `templates/partials/_sidebar.html`

- [ ] **Step 1: Wrap "Nueva organización" link in `_navbar.html` with `is_staff` guard**

In `templates/partials/_navbar.html`, find this block (lines ~52–57):
```html
      <li><hr class="dropdown-divider"></li>
      <li>
        <a class="dropdown-item" href="{% url 'accounts:create_org' %}">
          <i class="bi bi-plus-circle me-1"></i>{% trans "Nueva organización" %}
        </a>
      </li>
```

Replace with:
```html
      {% if request.user.is_staff %}
      <li><hr class="dropdown-divider"></li>
      <li>
        <a class="dropdown-item" href="{% url 'accounts:create_org' %}">
          <i class="bi bi-plus-circle me-1"></i>{% trans "Nueva organización" %}
        </a>
      </li>
      {% endif %}
```

- [ ] **Step 2: Add "Plataforma" section to `_sidebar.html`**

In `templates/partials/_sidebar.html`, find the closing `{% endif %}` of the "Organización" section (line ~160, the one that closes `{% if membership.is_admin %}`). Insert after that `{% endif %}`:

```html
    {% if request.user.is_staff %}
    <div class="sidebar-section-label">{% trans "Plataforma" %}</div>
    <ul class="sidebar-nav">
      <li>
        <a href="{% url 'accounts:create_org' %}"
           class="sidebar-nav-link {% if 'org/create' in request.path %}active{% endif %}">
          <i class="bi bi-building-add"></i>
          <span>{% trans "Nueva organización" %}</span>
        </a>
      </li>
    </ul>
    {% endif %}
```

- [ ] **Step 3: Verify templates render without errors**

```bash
python manage.py shell -c "
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
print('Template syntax OK — run server to visually verify')
"
```

Expected output: `Template syntax OK — run server to visually verify`

- [ ] **Step 4: Commit**

```bash
git add templates/partials/_navbar.html templates/partials/_sidebar.html
git commit -m "feat: hide org creation from non-staff users, add Plataforma sidebar section

- Navbar 'Nueva organización' link guarded by request.user.is_staff
- Sidebar gains 'Plataforma' section (is_staff only) with create org link"
```
