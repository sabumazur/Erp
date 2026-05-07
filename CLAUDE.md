# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
pytest

# Run a single test
pytest apps/invoices/tests/test_services.py::TestNCFService::test_confirm_assigns_encf

# Run tests for a specific app
pytest apps/invoices/

# Development server
python manage.py runserver

# Migrations
python manage.py makemigrations
python manage.py migrate

# Management commands
python manage.py seed_modules          # Populate core.Module registry
python manage.py configure_site        # Set django.contrib.sites entry
python manage.py mark_overdue_invoices # Transition SENT → OVERDUE past due_date
python manage.py expire_quotations     # Transition SENT/CONFIRMED → EXPIRED past valid_until
```

Settings are split across `config/settings/base.py`, `development.py`, and `production.py`. `pytest.ini` pins `DJANGO_SETTINGS_MODULE = config.settings.development`. Environment variables are loaded via `python-decouple` (`.env` file or environment). The development settings use PostgreSQL by default; configure `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

## Architecture

### Multi-tenancy

Every entity has an `organization` FK. All queries must be scoped:

```python
MyModel.objects.for_org(request.organization)
```

`OrganizationMiddleware` (loaded in `MIDDLEWARE`) sets `request.organization` and `request.membership` on every authenticated request. Resolution priority: `session["active_org_slug"]` → first membership by `created_at`.

### Base models (`apps/core/models.py`)

`ERPBaseModel` = `TimeStampedModel` + `SoftDeleteModel`, UUID primary key. All entity models inherit from it.

**Soft-delete behaviour:**
- `model.delete()` sets `deleted_at`; it does **not** emit `pre_delete`/`post_delete` signals. Guardian permission cleanup must be done manually before calling `delete()`.
- `model.hard_delete()` performs a real SQL DELETE.
- `Model.objects` filters `deleted_at__isnull=True`. `Model.all_objects` bypasses the filter — use this when checking for slug/code uniqueness to avoid collisions with soft-deleted rows.

### Auth & organizations (`apps/accounts/`)

- Custom `User` model is email-based (`USERNAME_FIELD = "email"`, no username).
- `UserManager.get_queryset()` always filters out soft-deleted users.
- A `post_save` signal on `User` (`create_default_organization`) auto-creates a personal workspace `Organization` and an `OWNER` `Membership` on every new registration. The slug collision resolution uses `all_objects` to check both live and soft-deleted orgs.
- On login, the `accept_pending_invitation` signal auto-accepts any pending `Invitation` for the user's email.
- `Membership.Role` hierarchy: `OWNER` > `ADMIN` > `MEMBER` > `VIEWER`. `membership.is_admin` returns `True` for OWNER and ADMIN.
- `Team.modules` (M2M to `core.Module`) gates module access. An empty `modules` set means unrestricted access.

### View base class

All views inherit `ERPBaseViewMixin(LoginRequiredMixin)`. It supports three class attributes:

```python
required_permission: str | None   # guardian codename scoped to request.organization
admin_required: bool              # True → OWNER or ADMIN only
required_module: str | None       # module slug checked via can_access_module()
```

Class-based views that use `render()` directly (plain `View` subclasses) must call `self.get_context(...)` instead of `get_context_data()` to get the sidebar context variables (`organization`, `membership`, `user_memberships`) injected.

### Invoice system (`apps/invoices/`)

`Invoice` is a single unified model with a `doc_type` discriminator: `INVOICE`, `QUOTATION`, `SALE_ORDER`. Three scoped managers exist:

```python
Invoice.invoices      # INVOICE only
Invoice.quotations    # QUOTATION only
Invoice.sale_orders   # SALE_ORDER only
Invoice.objects       # all doc_types (default)
```

**All fiscal and status transitions go through service classes** in `apps/invoices/services.py` — never mutate `status` directly in views:

- `NCFService` — confirms invoices, assigns e-NCF atomically via `NCFSequence.generate()` (`SELECT FOR UPDATE`). In dev mode with no active sequence, it falls back to a fake "B"-series NCF.
- `QuotationService` — DRAFT → CONFIRMED → SENT → ACCEPTED/REJECTED/EXPIRED → CONVERTED.
- `SaleOrderService` — DRAFT → CONFIRMED → DELIVERED → INVOICED; includes `consolidate_and_invoice()` to batch-invoice all DELIVERED orders for a customer/period.
- `PaymentService` — creates `Payment` + `PaymentAllocation` rows atomically; auto-marks invoices PAID when fully covered; reversal on `delete()`.

`InvoiceItem.save()` auto-calls `compute()` to populate `line_total`, `itbis_amount`, and `line_total_with_itbis`. After adding/removing items call `invoice.recompute_totals()`.

Dominican fiscal identifiers (NCF/e-CF) are tracked in `NCFSequence` (one active sequence per org+NCF type). Non-fiscal document numbers (quotations/sale orders) use `DocumentSequence`.

### Test factories

All factories in `apps/accounts/tests/factories.py` and `apps/invoices/tests/factories.py` use `@mute_signals(post_save)` to suppress `create_default_organization`. Tests that specifically assert signal behaviour call `User.objects.create_user()` directly.

Global fixtures (`user`, `org`, `owner_membership`, `admin_membership`, `member_membership`, `viewer_membership`) are defined in the root `conftest.py`.

### Settings & i18n

- Default language: Spanish (`LANGUAGE_CODE = "es"`); English also enabled.
- Timezone: `America/Santo_Domingo`.
- Crispy forms use the `bootstrap5` pack.
- `MESSAGE_TAGS` maps `ERROR` → `"danger"` to match Bootstrap 5 alert classes.
- `ANONYMOUS_USER_NAME = None` (disables the guardian anonymous user).
