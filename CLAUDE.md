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

Dominican fiscal identifiers are tracked in `NCFSequence` (one active sequence per org+NCF type). Non-fiscal document numbers (quotations/sale orders) use `DocumentSequence`.

**NCF series:** `NCFType` covers two series — physical (B) and electronic (E):

- **B-series** (traditional comprobantes): codes 1–16, e.g. `B01_CREDITO_FISCAL`, `B02_CONSUMO`. Format: `B{type:02d}{seq:08d}` → `B0100000001`. Default `max_seq` = 99,999,999.
- **E-series** (e-CF electrónico): codes 31–47, e.g. `CREDITO_FISCAL = 31`. Format: `E{type:02d}{seq:010d}` → `E310000000001`.

`NCFSequence` exposes `NCFSequence.PHYSICAL_TYPES` and `NCFSequence.ELECTRONIC_TYPES` frozensets. The `Series` inner class has `PHYSICAL = "B"` and `ELECTRONIC = "E"`; default series is `PHYSICAL`. Helper properties: `preview_next` (next NCF string without incrementing), `remaining` (unused slots). Dev-mode fallback in `NCFService` generates a fake B-series 8-digit NCF so it never collides with real E-series sequences.

### DataTable system (`apps/core/datatable.py`)

All list views use a shared datatable pattern for sorting, pagination, and HTMX filtering.

**`DataTableMixin`** — add to any `ListView`/`View` and set these class attributes:

```python
dt_columns: list[DTColumn]     # column definitions (key, label, sortable, visible, numeric)
dt_default_sort: str           # e.g. "name" or "-created_at"
dt_page_size: int              # rows per page (default 25)
dt_url: str                    # URL name for HTMX refreshes, e.g. "items:item_list"
dt_row_template: str           # per-row partial template path
dt_filter_template: str        # filter offcanvas body template path (optional)
dt_search_placeholder: str     # search input placeholder
dt_id: str                     # localStorage key for column visibility
```

Call `ctx.update(self.apply_datatable(filtered_qs))` in `get_context_data()`. For HTMX requests return `components/datatable/results.html`. Use `build_datatable_context()` directly in action views that need a table refresh after a CRUD op.

Templates: `components/datatable/wrapper.html` (full page), `results.html` (HTMX swap target), `pagination.html` (compact page range with ellipsis).

### Full-text search (`apps/core/search.py`)

```python
fts_search(qs, q, fts_fields, trgm_fields=(), config="spanish")
```

- `fts_fields` — natural-language text columns (SearchVector / SearchRank via `pg_trgm` + FTS).
- `trgm_fields` — codes / IDs (reliable `icontains` matching).
- `q < 3 chars` → plain `icontains` on all fields; `q >= 3` → FTS ranked + trigram fallback.
- Requires `django.contrib.postgres` and the `pg_trgm` extension (migration `core/0003_pg_trgm`).
- GIN indexes for FTS and trigram are added per-model in migrations `invoices/0018` and `items/0006`.

All customer, invoice, payment, quotation, sale order, and item list views already call `fts_search`.

### Reports (`apps/invoices/views/reports.py`)

All report views are `admin_required = True`, module `"invoices"`. Available reports:

| View | URL name | Description |
|------|----------|-------------|
| `ReportIndexView` | `invoices:reports` | Report hub with DGII deadline reminder |
| `Report607View` | `invoices:report_607` | DGII 607 CSV (sales by month/year) |
| `Report608View` | `invoices:report_608` | DGII 608 CSV (purchases by month/year) |
| `ReportAgingView` | `invoices:report_aging` | AR aging buckets (current, 1–30, 31–60, 61–90, 90+) |
| `ReportStatementView` | `invoices:report_statement` | Customer account statement |
| `ReportSalesByPeriodView` | `invoices:report_sales_period` | Sales summary by day/month |
| `ReportInvoicesByCustomerView` | `invoices:report_invoices_by_customer` | Invoices grouped by customer |
| `ReportCollectionsView` | `invoices:report_collections` | Collections / payments received |
| `ReportITBISView` | `invoices:report_itbis` | ITBIS (VAT) summary by period |
| `ReportSalesByNCFTypeView` | `invoices:report_ncf_type` | Sales grouped by NCF type |

### KPI cards (`templates/components/_kpi_cards.html`)

Reusable partial for summary metric grids. Include with:
```django
{% include "components/_kpi_cards.html" with cards=kpi_cards %}
```
Each card in `kpi_cards` is a dict with keys `label`, `value`, `icon`, `color` (Bootstrap color name), and optional `url`.

### Test factories

All factories in `apps/accounts/tests/factories.py` and `apps/invoices/tests/factories.py` use `@mute_signals(post_save)` to suppress `create_default_organization`. Tests that specifically assert signal behaviour call `User.objects.create_user()` directly.

Global fixtures (`user`, `org`, `owner_membership`, `admin_membership`, `member_membership`, `viewer_membership`) are defined in the root `conftest.py`.

### Deletion pattern

All delete views (`ItemDeleteView`, `CustomerDeleteView`, `NCFSequenceDeleteView`) are POST-only, `admin_required = True`. They guard against referential integrity before calling `model.delete()`:

- `ItemDeleteView` — blocked if any `InvoiceItem` references the item.
- `CustomerDeleteView` — blocked if the customer has invoices **or** payments.
- `NCFSequenceDeleteView` — no guard; sequences can always be deleted (confirmation handled in the template).

HTMX-aware: when `request.htmx` is truthy, deletion views return a partial response with `HX-Trigger` headers instead of a redirect. Success triggers `showToast`; blocked deletes trigger `showSwal` (SweetAlert2). Non-HTMX paths fall back to `messages` + redirect.

### Items app (`apps/items/`)

`Item` has an `ItemType` discriminator (`SALE`, `PURCHASE`, `BOTH`). Codes are auto-generated for `SALE` and `BOTH` items via `ItemCodeSequence.generate()` when left blank. `cost_price` is nullable/optional; `margin` property is only valid when set. `InvoiceItem` FK to `Item` is optional — line items can be free-text.

Search is indexed: GIN trgm on `name`/`code` (migration `items/0006`); the item list uses `fts_search` with `fts_fields=["name"]` and `trgm_fields=["code"]`.

### Settings & i18n

- Default language: Spanish (`LANGUAGE_CODE = "es"`); English also enabled.
- Timezone: `America/Santo_Domingo`.
- Crispy forms use the `bootstrap5` pack.
- `MESSAGE_TAGS` maps `ERROR` → `"danger"` to match Bootstrap 5 alert classes.
- `ANONYMOUS_USER_NAME = None` (disables the guardian anonymous user).
- `django.contrib.humanize` is installed (use `{% load humanize %}` for `intcomma`, `naturaltime`, etc. in templates).
