# Organization Creation Governance Design

**Date:** 2026-05-14
**Scope:** Restrict organization creation to platform admins (`is_staff`), upgrade the creation form, surface a staff-only "Plataforma" sidebar section.

---

## Goal

Creating an organization is irreversible in practice — data cannot be transferred between orgs, and a carelessly created org pollutes the platform. Restrict creation to `is_staff` users (platform admins) and give them a proper creation flow: full org details + owner invitation in a single form.

---

## Current State

- `CreateOrganizationView` at `/org/create/` is accessible to **any authenticated user** — only guarded by `LoginRequiredMixin`.
- `CreateOrganizationForm` collects **name only**.
- "Nueva organización" link is visible to all users in the navbar org-switcher dropdown (`_navbar.html:54`).
- On creation, the creator is auto-assigned OWNER and the active org switches to the new one.

---

## What Changes

### 1. Access Control

`CreateOrganizationView.dispatch()` checks `request.user.is_staff`. Non-staff users are redirected to `accounts:dashboard` with an error message. No new permission model — `is_staff` is the existing Django platform-admin flag.

`LeaveOrganizationView` is unchanged.

### 2. Form — `StaffCreateOrganizationForm`

New form in `apps/accounts/forms.py` replacing `CreateOrganizationForm` (which is deleted).

**Fields:**

| Group | Fields |
|-------|--------|
| Información general | `name` (required), `tax_id`, `logo` |
| Contacto | `email`, `phone`, `website` |
| Dirección | `address`, `city`, `state`, `zip_code`, `country` |
| Propietario | `owner_email` (EmailField, required) |

Layout mirrors `OrganizationForm` (crispy sections). `OrganizationForm` itself is **not modified** — it remains used by `OrganizationSettingsView`.

Slug is auto-generated from `name` (existing slug logic in `CreateOrganizationView`).

### 3. Creation Logic — Atomic, No Org Switch

On valid POST, inside a single `transaction.atomic()`:

1. Generate unique slug from `name` (existing collision-avoidance logic: try clean slug, fall back to UUID suffix on `IntegrityError`).
2. Create `Organization(name=..., slug=..., owner=request.user)` — staff admin is the technical creator; the FK is informational.
3. Do **not** create a `Membership` for the staff admin — they are not a member of this org.
4. Do **not** update `session["active_org_slug"]` — staff admin stays in their current org.
5. Create `Invitation` via `Invitation.create_for(org, email=owner_email, role=Membership.Role.OWNER, invited_by=request.user)`.
6. Send invitation email (same `InviteMemberView` email path).
7. Redirect to `accounts:dashboard` (staff admin's current org) with success message: `"Organización '{name}' creada. Invitación enviada a {owner_email}."`.

**Edge case:** If `owner_email` belongs to an existing `User`, the invitation auto-accepts on their next login via the existing `accept_pending_invitation` signal — no special handling needed.

**Error case:** If `Invitation.create_for()` fails (e.g., email already has pending invite — impossible since org just created), surface as form error.

### 4. UI Placement

**Navbar (`templates/partials/_navbar.html`):**

Wrap the existing "Nueva organización" `<li>` (line 53–57) with `{% if request.user.is_staff %}...{% endif %}`. Non-staff users no longer see this link in the org-switcher dropdown.

**Sidebar (`templates/partials/_sidebar.html`):**

Add a "Plataforma" section after the "Organización" section, visible only to `{% if request.user.is_staff %}`:

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

**Create org template (`templates/accounts/create_org.html`):**

Full rewrite. Layout:
- Page header: "Crear organización" + subtitle
- Warning notice (Bootstrap `alert-warning`): "Esta acción crea un espacio de trabajo independiente. Los datos no pueden transferirse entre organizaciones."
- Crispy form with sections matching `org_settings.html` style
- Submit button: "Crear organización y enviar invitación"
- Cancel link → `accounts:dashboard`

---

## Files Changed

| File | Change |
|------|--------|
| `apps/accounts/forms.py` | Remove `CreateOrganizationForm`; add `StaffCreateOrganizationForm` |
| `apps/accounts/views.py` | Rewrite `CreateOrganizationView` — `is_staff` guard, new form, atomic creation, no org switch |
| `templates/accounts/create_org.html` | Full rewrite — full form, warning notice |
| `templates/partials/_navbar.html` | Wrap "Nueva organización" link with `{% if request.user.is_staff %}` |
| `templates/partials/_sidebar.html` | Add "Plataforma" section guarded by `{% if request.user.is_staff %}` |

---

## Out of Scope

- Platform admin org listing / overview page
- Transferring org ownership after creation (done via existing invitation system)
- Deactivating or deleting organizations
- Billing / subscription limits on org count
- Any change to the auto-create-on-signup signal (`create_default_organization`)
