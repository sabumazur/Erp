# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repo.

## Commands

```bash
# Run all tests
pytest

# Run a single test
pytest apps/sales/tests/test_services.py::TestNCFService::test_confirm_assigns_encf

# Run tests for a specific app
pytest apps/sales/

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
python manage.py reset_db              # Wipe all data and restore superuser account
python manage.py reset_db --no-input   # Skip confirmation prompt
python manage.py seed_db               # Seed 25 DR sample records per model into superuser's org
python manage.py seed_db --no-input    # Skip confirmation prompt
python manage.py cleanup_ghost_organizations          # Delete empty auto-created workspaces for invited users
python manage.py cleanup_ghost_organizations --dry-run # Preview without deleting
python manage.py empty_sales_doc               # Delete all invoices/quotations/sale orders + payments, reset sequences
python manage.py empty_sales_doc --no-input    # Skip confirmation prompt
python manage.py audit_module_access           # Read-only audit of team module access config
python manage.py audit_module_access --strict  # Exit non-zero if audit findings found
```

Settings split across `config/settings/base.py`, `development.py`, `production.py`. `pytest.ini` pins `DJANGO_SETTINGS_MODULE = config.settings.development`. Env vars via `python-decouple` (`.env` or env). Dev uses PostgreSQL; configure `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

## Skills

Three project skills are installed as `.skill` files in the repo root:

| Skill | File | Trigger |
|-------|------|---------|
| `sabsys-review` | `sabsys-review.skill` | Reviewing a PR or diff for sabsys-specific correctness |
| `sabsys-test` | `sabsys-test.skill` | Writing tests for any sabsys app |

## Architecture

### Multi-tenancy

Every entity has `organization` FK. All queries must be scoped:

```python
MyModel.objects.for_org(request.organization)
```

`OrganizationMiddleware` (in `MIDDLEWARE`) sets `request.organization` + `request.membership` on every auth request. Resolution: `session["active_org_slug"]` → first membership by `created_at`.

### Base models (`apps/core/models.py`)

`ERPBaseModel` = `TimeStampedModel` + `SoftDeleteModel`, UUID PK. All entity models inherit it.

**`DocumentSequence`** — unified auto-increment counter for non-fiscal documents (does NOT inherit `ERPBaseModel` — infrastructure, not business entity). One row per `(organization, doc_type)`. Call `DocumentSequence.generate(org, doc_type, *, defaults={})` from services; pass `defaults` so first-use `get_or_create` sets the correct `prefix`/`include_year`/`padding`. Doc types: `"QUOTATION"` (COT, year), `"SALE_ORDER"` (OV, year), `"PURCHASE_ORDER"` (OC, no year).

**Soft-delete behaviour:**
- `model.delete()` sets `deleted_at`; **not** emit `pre_delete`/`post_delete`. Do guardian cleanup manually before `delete()`.
- `model.hard_delete()` performs real SQL DELETE.
- `Model.objects` filters `deleted_at__isnull=True`. `Model.all_objects` bypasses — use for slug/code uniqueness to avoid collisions with soft-deleted rows.

### Auth & organizations (`apps/accounts/`)

- `User` model email-based (`USERNAME_FIELD = "email"`, no username).
- `UserManager.get_queryset()` filters out soft-deleted users.
- `post_save` on `User` (`create_default_organization`) auto-creates personal `Organization` + `OWNER` `Membership` on registration. **Guard:** skips if a pending (non-expired) `Invitation` exists for that email — invited users get no ghost workspace. Slug collision uses `all_objects` (live + soft-deleted).
- On login, `accept_pending_invitation` signal (`user_logged_in`) auto-accepts all pending non-expired invitations for user email. Uses `transaction.atomic()` + `get_or_create` for race safety. Calls `_remove_ghost_org()` to clean up any auto-created personal workspace after joining via invitation.
- `_remove_ghost_org(user, invited_org)` in `apps/accounts/signals.py` — deletes any solo-owner org with no data (customers/invoices/payments) that isn't the org just joined.
- `AcceptInvitationView` (`accounts:accept_invitation`) — GET-only view; statuses: `already_accepted` (redirects members to dashboard), `expired`, `login_required`, `wrong_email`. Uses `get_or_create` + `transaction.atomic()` in `_accept()`.
- **allauth logout is POST-only (v65+).** `next` must be in POST body, not query string. Use `<form method="post">` with `<input type="hidden" name="next" value="...">` — never `<a href="{% url 'account_logout' %}?next=...">`.
- **`ACCOUNT_RATE_LIMITS` format:** `"{count}/{digits}{unit}"` e.g. `"10/1h"`. Unit must be single char `s/m/h/d`. `"10/hour"` raises `ValueError: Invalid duration unit: r`.
- `Membership.Role` hierarchy: `OWNER` > `ADMIN` > `MEMBER` > `VIEWER`. `membership.is_admin` returns `True` for OWNER and ADMIN.
- `Team.modules` (M2M to `core.Module`) gates module access. Empty `modules` = unrestricted.
- **Org creation restricted to `is_staff`.** `CreateOrganizationView` checks `is_staff` in `dispatch`; non-staff see no "Crear organización" in navbar. Uses `StaffCreateOrganizationForm`.
- **Signup invitation-only.** `CustomSignupForm.clean_email()` blocks registration unless the email has a pending non-expired `Invitation`. Raises `"El registro es solo por invitación."` Otherwise allauth signup is open by default.
- **Account adapter** (`apps/accounts/adapter.py`) — `AccountAdapter(DefaultAccountAdapter)` suppresses allauth's built-in login/logout flash messages (`account/messages/logged_in.txt`, `account/messages/logged_out.txt`). Wired via `ACCOUNT_ADAPTER = "apps.accounts.adapter.AccountAdapter"` in settings.

### View base class

All views inherit `ERPBaseViewMixin(LoginRequiredMixin)`. Three class attrs:

```python
required_permission: str | None   # guardian codename scoped to request.organization
admin_required: bool              # True → OWNER or ADMIN only
required_module: str | None       # module slug checked via can_access_module()
```

Plain `View` subclasses using `render()` must call `self.get_context(...)` not `get_context_data()` to get sidebar vars (`organization`, `membership`, `user_memberships`).

**`ModuleStaffMixin`** (`apps/core/views_modules.py`) — `ERPBaseViewMixin` subclass for staff-only views. Checks `request.user.is_staff`, skips org context. Use for platform-level admin (Module registry, etc.).

### Invoice system (`apps/sales/`)

`SalesDocument` unified model with `doc_type` discriminator: `INVOICE`, `QUOTATION`, `SALE_ORDER`. Three scoped managers:

```python
SalesDocument.invoices      # INVOICE only
SalesDocument.quotations    # QUOTATION only
SalesDocument.sale_orders   # SALE_ORDER only
SalesDocument.objects       # all doc_types (default)
```

**All fiscal/status transitions go through service classes** in `apps/sales/services.py` — never mutate `status` directly in views:

- `NCFService` — confirms invoices, assigns e-NCF atomically via `NCFSequence.generate()` (`SELECT FOR UPDATE`). Dev fallback: fake "B"-series NCF.
- `QuotationService` — DRAFT → CONFIRMED → SENT → ACCEPTED/REJECTED/EXPIRED → CONVERTED.
- `SaleOrderService` — DRAFT → CONFIRMED → DELIVERED → INVOICED; `consolidate_and_invoice()` batch-invoices DRAFT orders for a customer: groups lines by catalog `Item` (aggregates quantities with `Sum`), skips free-text lines. Caller must pass DRAFT orders only.
- `PaymentService` — creates `Payment` + `PaymentAllocation` rows atomically; auto-marks invoices PAID when fully covered; reversal on `delete()`.

`InvoiceItem.save()` auto-calls `compute()` → `line_total`, `itbis_amount`, `line_total_with_itbis`. After add/remove items call `invoice.recompute_totals()`.

**`suspend_recompute(document)`** — context manager in `apps/sales/signals.py`. Suspends per-item `recompute_totals()` calls via thread-local flag during bulk formset saves. Wrap formset `.save()` inside it and call `document.recompute_totals()` once on exit. Prevents N+1 recompute on bulk line-item creates.

**`SalesDocument` queryset annotations** (call on any queryset before filtering):
- `.with_signed_totals()` — annotates invoices with sign-adjusted amounts (credit/debit notes negate).
- `.with_aging()` — annotates `aging_bucket_db` (`current`/`1-30`/`31-60`/`61-90`/`90+`) based on `due_date` vs today. Read via `document.aging_bucket` property; human label via `document.aging_bucket_label`.

**Materialized view** `sales_customer_revenue_mv` (migration 0032) — aggregates confirmed invoice revenue per customer. Refreshed concurrently (`REFRESH MATERIALIZED VIEW CONCURRENTLY`) via `transaction.on_commit()` signal after each invoice confirm. Manual refresh: `python manage.py refresh_revenue_mv`.

Dominican fiscal IDs in `NCFSequence` (one active per org+NCF type). Non-fiscal (quotations/sale orders/purchase orders) use `DocumentSequence` from `apps/core/models.py`.

**NCF series:** `NCFType` covers two series — physical (B) and electronic (E):

- **B-series** (traditional comprobantes): codes 1–16, e.g. `B01_CREDITO_FISCAL`, `B02_CONSUMO`. Format: `B{type:02d}{seq:08d}` → `B0100000001`. Default `max_seq` = 99,999,999.
- **E-series** (e-CF electrónico): codes 31–47, e.g. `CREDITO_FISCAL = 31`. Format: `E{type:02d}{seq:010d}` → `E310000000001`.

RNC/cedula validation in `apps/sales/validators.py`. DGII checksum uses **modulo 11** (weights `[7,9,8,6,5,4,3,2]`, check digit = `(11 - total%11) % 11`). Cedulas use different weights + modulo 10.

`NCFSequence` exposes `PHYSICAL_TYPES` + `ELECTRONIC_TYPES` frozensets. `Series`: `PHYSICAL = "B"`, `ELECTRONIC = "E"`; default `PHYSICAL`. Props: `preview_next` (next NCF without increment), `remaining` (unused slots). Dev fallback generates fake B-series 8-digit NCF — no collision with E-series.

### DataTable system (`apps/core/datatable.py`)

All list views use shared datatable pattern for sorting, pagination, HTMX filtering.

**`DataTableMixin`** — add to any `ListView`/`View`; set class attrs:

```python
dt_columns: list[DTColumn]     # column definitions (key, label, sortable, visible, numeric, classes)
dt_default_sort: str           # e.g. "name" or "-created_at"
dt_page_size: int              # rows per page (default 15)
dt_url: str                    # URL name for HTMX refreshes, e.g. "items:item_list"
dt_row_template: str           # per-row partial template path
dt_ribbon_template: str        # command ribbon actions partial (rendered in .dt-ribbon-right)
dt_filter_template: str        # filter offcanvas body template path (optional)
dt_search_placeholder: str     # search input placeholder
dt_id: str                     # localStorage key for column visibility
dt_status_pills: list          # list of (value, label) tuples for status filter pills
```

Call `ctx.update(self.apply_datatable(filtered_qs))` in `get_context_data()`. Pass `status_pills=` kwarg to override `dt_status_pills` per-request. HTMX requests → return `components/datatable/results.html`. Use `build_datatable_context()` in action views needing table refresh after CRUD.

Templates: `components/datatable/wrapper.html` (full page), `results.html` (HTMX swap target), `pagination.html` (compact page range with ellipsis). **Pagination nav always renders** — prev/next disabled on single-page results; no conditional hide when `num_pages == 1`.

**Filter offcanvas (`#dt-filter-offcanvas`)** — Bootstrap default `offcanvas-end` sets `height: 100%`. Overridden in `templates/components/app_styles.html` to `height: auto; max-height: 50vh` so it sizes to content and caps at half viewport. Action buttons inside use `btn-outline-secondary` (not `btn-primary`) to match app-wide button style.

**Command ribbon pattern** — each list view has a `_ribbon.html` partial (e.g. `sales/partials/invoice_ribbon.html`). Registered via `dt_ribbon_template`. Rendered inside `.dt-ribbon-right`. Ribbon buttons bind to Alpine.js row selection state:
- `canAct` — `true` when a row is selected
- `selectedStatus` — `data-status` value of selected `<tr>`
- `selectedPk` — `data-pk` value of selected `<tr>`
- `:disabled="!canAct"` gates context-sensitive buttons (Ver, Editar, etc.)
- `:disabled="!canAct || selectedStatus !== 'DRAFT'"` for edit (status-gated)

**Row `<tr>` data attributes** (required for ribbon + selection):
```html
<tr data-pk="{{ row.pk }}"
    data-status="{{ row.status }}"
    data-detail-url="{% url 'sales:model_detail' row.pk %}">
```

**Row action pattern** — all list row templates use a kebab dropdown (`.dt-kebab`) embedded in the primary text cell. Do **not** add a separate action `<td>` and do **not** use the old `.dt-hover-actions` pattern. Structure:
```html
<span class="dt-row-actions">
  <div class="dropdown dt-kebab">
    <button type="button" class="btn btn-link btn-sm p-0 dt-kebab-btn"
            data-bs-toggle="dropdown" data-bs-boundary="viewport" tabindex="-1">
      <i class="bi bi-three-dots-vertical"></i>
    </button>
    <ul class="dropdown-menu dropdown-menu-end shadow-sm">
      <li><a class="dropdown-item" href="..." data-action="view">...</a></li>
      {% if row.status == 'DRAFT' %}
      <li><a class="dropdown-item" href="..." data-action="edit">...</a></li>
      {% endif %}
    </ul>
  </div>
</span>
```
`data-action="view"` / `data-action="edit"` on kebab items let ribbon buttons locate the correct link via `querySelector('[data-action=view]')`. Selection clears automatically on HTMX swap.

**`.dt-kebab` dropdown positioning** — `static/js/core.js` patches `bootstrap.Dropdown.prototype._getPopperConfig` for any toggle inside `.dt-kebab` to use `strategy: 'fixed'` (escapes `app-table-wrap { overflow: hidden }`) and `placement: 'auto'` (Popper picks best direction, so dropdown is fully visible even when the table has only one row). Patch applies globally including HTMX-swapped content.

**Detail page sidebar tables** — status/meta tables inside `app-table-wrap` on detail pages (e.g. "Estado del documento") use `overflow-x: auto` on their `p-3` wrapper and `min-width: max-content` on the `<table>` so values are never clipped by the parent `overflow: hidden`. Value `<td>` elements carry `white-space: nowrap`. Apply this pattern to any new sidebar info table.

### New app checklist

When scaffolding an entirely new Django app:

1. Create `apps/<app_name>/` with `__init__.py`, `apps.py`, `models.py`, `forms.py`, `filters.py`, `views.py` (or `views/`), `urls.py`, `admin.py`, `tests/`, `migrations/`.
2. Add `"apps.<app_name>"` to `INSTALLED_APPS` in `config/settings/base.py`.
3. Register URLs in `config/urls.py` with an appropriate prefix.
4. Create templates under `templates/<app_name>/` and `templates/<app_name>/partials/`.
5. Run `python manage.py makemigrations <app_name>`.
6. Register models in `admin.py`.
7. If module-gated, add module slug to `seed_modules` management command so it can be seeded.

### Full-text search (`apps/core/search.py`)

```python
fts_search(qs, q, fts_fields, trgm_fields=(), config="spanish")
```

- `fts_fields` — natural-language text columns (SearchVector / SearchRank via `pg_trgm` + FTS).
- `trgm_fields` — codes / IDs (reliable `icontains` matching).
- `q < 3 chars` → plain `icontains` on all fields; `q >= 3` → FTS ranked + trigram fallback.
- Needs `django.contrib.postgres` + `pg_trgm` extension (migration `core/0003_pg_trgm`).
- GIN indexes for FTS + trigram per-model in migrations `invoices/0018` + `items/0006`.

All customer, invoice, payment, quotation, sale order, item list views call `fts_search`.

### Caching

Dev uses `LocMemCache` (`config/settings/development.py`). Prod uses `DatabaseCache` with 5-min TTL (`config/settings/production.py`).

**Dashboard cache** (`apps/accounts/views.py` `DashboardView`):
- Key: `f"dashboard:{org.pk}"`, TTL 900s.
- Cached: all KPI aggregations + chart data (primitive types only — Decimal, int, list, dict).
- **Not cached:** table rows (`recent_invoices`, `overdue_invoices`, `recent_payments`) — model instances go stale.
- Invalidated by signals in `apps/sales/signals.py` via `_bust_dashboard(org_id)` → `cache.delete(f"dashboard:{org_id}")` on `post_save`/`post_delete` of `SalesDocument` and `Payment`.

**Report cache** (`apps/sales/views/reports.py`):
- Key: `f"report_{name}:{org.pk}:{request.GET.urlencode()}"`, TTL 600s.
- Applied to: `ReportAgingView`, `ReportStatementView`, `ReportSalesByPeriodView`, `ReportInvoicesByCustomerView`, `ReportCollectionsView`, `ReportITBISView`, `ReportSalesByNCFTypeView`.
- **Not cached:** `Report607View` / `Report608View` (return file downloads with `Content-Disposition`), `customers` dropdown (always fresh), error and empty states.

### Reports (`apps/sales/views/reports.py`)

All report views: `admin_required = True`, module `"sales"`.

| View | URL name | Description |
|------|----------|-------------|
| `ReportIndexView` | `sales:reports` | Report hub with DGII deadline reminder |
| `Report607View` | `sales:report_607` | DGII 607 CSV (sales by month/year) |
| `Report608View` | `sales:report_608` | DGII 608 CSV (purchases by month/year) |
| `ReportAgingView` | `sales:report_aging` | AR aging buckets (current, 1–30, 31–60, 61–90, 90+) |
| `ReportStatementView` | `sales:report_statement` | Customer account statement |
| `ReportSalesByPeriodView` | `sales:report_sales_period` | Sales summary by day/month |
| `ReportInvoicesByCustomerView` | `sales:report_invoices_by_customer` | Invoices grouped by customer |
| `ReportCollectionsView` | `sales:report_collections` | Collections / payments received |
| `ReportITBISView` | `sales:report_itbis` | ITBIS (VAT) summary by period |
| `ReportSalesByNCFTypeView` | `sales:report_ncf_type` | Sales grouped by NCF type |

### Module management (`apps/core/views_modules.py`)

Staff-only CRUD for global `Module` registry. Uses `ModuleStaffMixin` (no org context). URL namespace: `core`.

| View | URL name | Description |
|------|----------|-------------|
| `ModuleListView` | `core:module_list` | Datatable list + inline create (ribbon `core/partials/module_ribbon.html`) |
| `ModuleDetailView` | `core:module_detail` | Read-only detail |
| `ModuleUpdateView` | `core:module_edit` | HTMX modal edit |
| `ModuleToggleView` | `core:module_toggle` | Toggle `is_active` |
| `ModuleDeleteView` | `core:module_delete` | Delete (blocked if teams use module) |

Registered in `config/urls.py` at `plataforma/modules/`.

### Payment Terms (`apps/sales/views/payment_terms.py`)

Org-scoped CRUD for `PaymentTerm` (name, days_due, description). `admin_required = True`, `required_module = "sales"`. Sidebar after "Secuencias NCF" for admins.

| View | URL name | Description |
|------|----------|-------------|
| `PaymentTermListView` | `sales:payment_term_list` | Datatable list + inline create |
| `PaymentTermUpdateView` | `sales:payment_term_edit` | HTMX modal edit |
| `PaymentTermDeleteView` | `sales:payment_term_delete` | Delete (blocked if customers reference term) |

### Customers (`apps/sales/views/customers.py`)

Customer CRUD uses **full-page forms** (two-column layout, not HTMX modals). List "Nuevo" button navigates to create page; kebab "Editar" navigates to edit page.

| View | URL name | Description |
|------|----------|-------------|
| `CustomerListView` | `sales:customer_list` | Datatable list |
| `CustomerCreateView` | `sales:customer_create` | Full-page create form |
| `CustomerUpdateView` | `sales:customer_edit` | Full-page edit form |
| `CustomerDetailView` | `sales:customer_detail` | Detail with smart buttons |
| `CustomerDeleteView` | `sales:customer_delete` | Delete (blocked if has invoices/payments) |

**`Customer.id_type`** — restricted to `RNC` or `CED` only (Pasaporte/Exterior removed). `CheckConstraint customer_id_type_rnc_or_cedula` + `clean()` enforce it. `rnc_cedula` validated via `validate_rnc_cedula` (length only; no passport branch).

**`CustomerDepartment`** — org-scoped sub-entity of `Customer` (name, is_active). Used to tag sale orders for departmental billing. Managed from the customer detail page via HTMX modals. `SaleOrderForm` disables the `department` field (`disabled` attr) when the selected customer has no departments.

| View | URL name | Description |
|------|----------|-------------|
| `CustomerDepartmentCreateView` | `sales:department_create` | HTMX inline create |
| `CustomerDepartmentUpdateView` | `sales:department_edit` | HTMX modal edit |
| `CustomerDepartmentToggleView` | `sales:department_toggle` | Toggle `is_active` |
| `CustomerDepartmentDeleteView` | `sales:department_delete` | Delete (blocked if sale order references it) |
| `CustomerDepartmentsView` | `sales:departments_for_customer` | HTMX partial — dropdown options for a customer |

### Document email (`apps/sales/email.py`)

Sends HTML emails with inline org logo (base64 data URI, no external fetch). All three functions attach a PDF if WeasyPrint is installed; silently omit PDF if not.

- `send_invoice_email(invoice, request)` — sends `sales/email/invoice_email.html` + attaches `factura_{doc_ref}.pdf` via `invoice_print.html`.
- `send_quotation_email(quotation, request)` — sends `sales/email/quotation_email.html` + attaches `cotizacion_{doc_ref}.pdf` via `quotation_print.html`; includes sender signature.
- `send_sale_order_email(order, request)` — sends `sales/email/sale_order_email.html` + attaches `orden_{doc_ref}.pdf` via `sale_order_print.html`.
- `QuotationEmailView` (`sales:quotation_email`) — POST-only; triggers `send_quotation_email` and redirects with success/error message.

Shared helper `_pdf_bytes(template, context, request)` renders any print template to PDF via WeasyPrint; returns `None` on `ImportError`. All three PDF helpers (`_invoice_pdf_bytes`, `_quotation_pdf_bytes`, `_sale_order_pdf_bytes`) delegate to it.

Email templates embed logo as `data:image/...;base64,...` so email clients don't need to fetch external URLs.

### HTMX document-form views (`apps/sales/views/htmx.py`)

Inline helpers used by the invoice/quotation/sale-order create/edit forms via HTMX.

| View | URL name | Description |
|------|----------|-------------|
| `ItemSearchView` | `sales:item_search` | Returns item picker results partial (`sales/partials/item_picker_results.html`) |
| `ItemQuickCreateView` | `sales:item_quick_create` | Creates `Item` inline via `ItemQuickCreateForm`; returns picker row |
| `CustomerQuickCreateView` | `sales:customer_quick_create` | Creates `Customer` inline; returns updated customer picker |

`ItemQuickCreateForm` (`apps/sales/forms.py`) — minimal item creation (name, unit_price, itbis_rate) scoped to org. Used from item picker modal without leaving the document form.

### Shared picker base (`static/js/picker-base.js`)

All document pickers (items, customers, suppliers) are built via `createPicker(cfg)` factory. Config keys: `modalId`, `searchInputId`, `quickCreateUrl`, `apply(row)` callback. Returns `{ open, select, highlight, refresh, showSearch, showCreate }`. Old separate `initItemModal()` / `initModuleModal()` etc. replaced by `initEditableModals()` which reads a declarative `EDITABLE_MODALS` array. When adding a new picker, define a config object and call `createPicker(cfg)` — do not clone the old per-picker pattern.

### Document forms UI (`static/js/document-form.js`, `apps/core/layout.py`)

All invoice/quotation/sale-order/payment create+edit forms share `static/js/document-form.js`. Exposes on `window`: `itemRow` (Alpine row factory), `deleteRow`, `recalcGrandTotal`, `addDocumentLine`, `initInvoiceItemFormset`, `initInvoiceItemHtmx`, `initCustomerDefaults`, `initIssueDateDeliverySync`, `initHeaderCardCollapse`. Line totals + grand totals (`grand-subtotal`, `grand-itbis18`, `grand-itbis16`, `grand-total`) recompute client-side; ITBIS split by rate (`RATE_18`/`RATE_16`). New lines cloned from `#empty-item-row` template, formset `TOTAL_FORMS` bumped, Alpine + TomSelect re-init.

- **Customer defaults** — `window.CUSTOMER_DEFAULTS[pk]` carries `payment_condition` + `days_due`; selecting a customer sets payment condition and computes `due_date` from `issue_date + days_due`. On sale orders, also clears `#id_department`.
- **Collapsible header card** (`initHeaderCardCollapse`) — `.doc-order-card` head becomes accessible toggle (role/tabindex/chevron); body wrapped in `.doc-card-collapse` for grid-rows height animation. State persisted in `localStorage` key `sabsys.docHead.<path-with-:id>` (UUID/numeric segments stripped so create + edit share state). Default open.

**Optional fields** — `optional_fields(*specs)` in `apps/core/layout.py` builds a crispy fragment of "chips" that reveal hidden field wrappers on click (`static/js/optional-fields.js`). Each spec is a `(field_name, chip_label)` tuple. Used for `terms`/`notes` on invoice/quotation/credit-note forms, `notes` on sale-order/payment forms. Pre-filled fields auto-reveal; `doc-optfield-remove` button clears + hides.

**Page title** — `templates/base.html` renders `<title>SabSys - {% block title %}{% trans "Inicio" %}{% endblock %}</title>` (SabSys **prefix**, default "Inicio"). Page templates set only their own name in `{% block title %}` — no `— SabSys` suffix. `{% block extra_css %}` added to `<head>`.

### KPI cards (`templates/components/_kpi_cards.html`)

App-wide standard for summary metric grids. Emits the `.db-kpi` tile (mono `tnum`
digits, `RD$` currency affix, semantic accent stripe + tinted icon, uppercase label).
CSS lives in `static/css/components.css` (`.db-kpi*`, global). The dashboard and all
7 sales/purchases list views feed it a `stats` list:
```django
{% include "components/_kpi_cards.html" with stats=stats %}
```
Each `stats` dict — required: `label`, `value` (pre-formatted), `icon` (e.g. `bi-receipt`).
Optional:
- `variant` — semantic class: `is-ar` (blue/receivable), `is-ap` (amber/payable),
  `is-neg` (red), `is-pos` (green), `is-net` (navy).
- `color` — legacy Bootstrap token, mapped for back-compat when `variant` absent:
  `primary→is-ar`, `success→is-pos`, `danger→is-neg`, `warning→is-ap`, `info→is-net`.
- `currency` — affix before value (e.g. `"RD$"`); omit for counts.
- `value_class` — `num-pos` / `num-neg` to colour the value.
- `href` — renders the card as a link instead of a div.
- `trend` + `trend_up` — secondary line with up/down arrow.

Include-level `col_class` overrides the per-card Bootstrap columns
(default `col-12 col-sm-6 col-xl-3`). `DashboardView._build_kpi_stats()`
(`apps/accounts/views.py`) builds `admin_stats`/`sales_stats`/`purchase_stats`
per-request from cached primitives (cache stays primitive-only).

**Two intentional roles:** `_kpi_cards.html` (`.db-kpi`) is the standard interactive
metric tile (dashboard + list pages). The ~10 report templates deliberately keep the
compact, centered, print-tuned `.app-metric-card` tile (icon-less, dense) — by design,
not a pending migration. Shim/rule for both in `components.css`.

### Test factories

All factories in `apps/accounts/tests/factories.py` + `apps/sales/tests/factories.py` use `@mute_signals(post_save)` to suppress `create_default_organization`. Signal tests call `User.objects.create_user()` directly.

Global fixtures (`user`, `org`, `owner_membership`, `admin_membership`, `member_membership`, `viewer_membership`) in root `conftest.py`.

### Deletion pattern

All delete views POST-only, `admin_required = True`. Guard referential integrity before `model.delete()`:

- `ItemDeleteView` — blocked if any `InvoiceItem` references item.
- `CustomerDeleteView` — blocked if customer has invoices **or** payments.
- `NCFSequenceDeleteView` — no guard; sequences always deletable (confirmation in template).
- `PaymentTermDeleteView` — blocked if any `Customer` references term.
- `CustomerDepartmentDeleteView` — blocked if any `SalesDocument` (sale order) references department.

HTMX-aware: `request.htmx` → partial response with `HX-Trigger` instead of redirect. Success → `showToast`; blocked → `showSwal` (SweetAlert2). Non-HTMX → `messages` + redirect.

### Items app (`apps/items/`)

`Item` has `ItemType` discriminator (`SALE`, `PURCHASE`, `BOTH`). Codes auto-generated for `SALE`/`BOTH` via `ItemCodeSequence.generate()` if blank — generation retries up to 5× on uniqueness race (checks `all_objects` including soft-deleted). `cost_price` nullable; `margin` valid only when set. `unit_price` and `cost_price` have `MinValueValidator(0.00)`. `InvoiceItem` FK to `Item` optional — line items can be free-text.

Search: GIN trgm on `name`/`code` (migration `items/0006`); item list uses `fts_search` with `fts_fields=["name"]`, `trgm_fields=["code"]`. `default_supplier` FK to `purchases.Supplier` (nullable, `SET_NULL`); auto-set on `SupplierInvoiceService.confirm()` if not already set.

### Purchases app (`apps/purchases/`)

Module slug `"purchasing"`. URL namespace `purchases`. Registered in `config/urls.py`.

**Models:**

- **`Supplier`** — `id_type` (RNC/CEDULA only; `CheckConstraint supplier_id_type_rnc_or_cedula`), `rnc_cedula` (validated via `validate_rnc_cedula`), `payment_term` FK to `sales.PaymentTerm`, `is_active`. Unique constraint: `(organization, rnc_cedula)` where rnc_cedula non-empty and not soft-deleted. `delete()` blocked if has `PurchaseDocument` or `SupplierPayment`. GIN trgm indexes on `name` and `rnc_cedula`.
- **`PurchaseDocument`** — unified model for purchase orders and supplier invoices, mirroring `SalesDocument`:
  - `doc_type`: `PURCHASE_ORDER` | `SUPPLIER_INVOICE`
  - `status`: `DRAFT` → `CONFIRMED` → `RECEIVED`/`PAID`/`CANCELLED`
  - Currency fields: `currency` (DOP/USD/EUR), `exchange_rate`
  - ITBIS split: `itbis_18`, `itbis_16` (separate fields for DGII 606)
  - DGII 606 fields: `supplier_ncf`, `supplier_ncf_type`, `supplier_rnc` (copied from supplier on confirm)
  - `linked_purchase_order` self-FK (null) — SI created from a PO
  - Scoped managers: `PurchaseDocument.purchase_orders`, `PurchaseDocument.supplier_invoices`, `PurchaseDocument.objects` (all), `PurchaseDocument.all_objects` (bypasses soft-delete)
  - `recompute_totals()` sums `PurchaseDocumentItem` rows into `subtotal`, `itbis_18`, `itbis_16`, `total`
- **`PurchaseDocumentItem`** — ITBIS rates: `EXEMPT`/`RATE_0`/`RATE_16`/`RATE_18`. `save()` calls `compute()` → `line_total`, `itbis_amount`, `line_total_with_itbis`. FK to `items.Item` optional (free-text lines allowed).
- **`DocumentSequence`** (`apps/core/models.py`) — unified auto-numbering for all non-fiscal documents. One row per `(organization, doc_type)`. Fields: `prefix`, `current_seq`, `padding`, `include_year`. `generate(org, doc_type, *, defaults={})` uses `SELECT FOR UPDATE` + `get_or_create`. Format: `PREFIX-YYYY-NNNN` when `include_year=True` (COT/OV), `PREFIX-NNNNN` when `False` (OC). Replaces the former per-app `sales.DocumentSequence` and `purchases.PurchaseSequence`.
- **`SupplierPayment`** + **`SupplierPaymentAllocation`** — same pattern as sales `Payment`/`PaymentAllocation`. `SupplierPayment.delete()` raises `ValueError` — always use `SupplierPaymentService.delete_payment()`.

**Service classes** (`apps/purchases/services.py`) — all status transitions go through services:

- **`PurchaseOrderService`**:
  - `confirm(po)` — assigns `DocumentSequence` number (`"OC-NNNNN"`), DRAFT → CONFIRMED
  - `receive_and_invoice(po)` — CONFIRMED → RECEIVED; auto-creates draft `SUPPLIER_INVOICE` copying all lines + setting `linked_purchase_order`; due date from supplier's payment term
  - `cancel(po)` — blocks if RECEIVED/already CANCELLED
- **`SupplierInvoiceService`**:
  - `confirm(invoice)` — requires `supplier_ncf`; checks NCF uniqueness in org; copies `supplier_rnc` from supplier; DRAFT → CONFIRMED; updates `item.cost_price` and `item.default_supplier` for all linked items
  - `cancel(invoice)` — blocked if PAID or has payment allocations
  - `reopen(invoice)` — CANCELLED → DRAFT; blocked if has allocations
- **`SupplierPaymentService`**:
  - `create_payment(supplier, org, date, method, reference, notes, allocations)` — atomic; `SELECT FOR UPDATE` on invoices; creates `SupplierPayment` + `SupplierPaymentAllocation` rows; marks invoices PAID when fully covered
  - `delete_payment(payment)` — reverses PAID → CONFIRMED on affected invoices; uses `hard_delete()`

**Views** (all `required_module = "purchasing"`):

| View | URL name | Description |
|------|----------|-------------|
| `SupplierListView` | `purchases:supplier_list` | Datatable list |
| `SupplierCreateView` | `purchases:supplier_create` | Full-page form with DGII RNC lookup |
| `SupplierDetailView` | `purchases:supplier_detail` | Detail with smart buttons |
| `SupplierUpdateView` | `purchases:supplier_edit` | HTMX modal edit |
| `SupplierDeleteView` | `purchases:supplier_delete` | Delete (blocked if has documents/payments) |
| `PurchaseOrderListView` | `purchases:po_list` | Datatable list |
| `PurchaseOrderCreateView` | `purchases:po_create` | Full-page form with item picker |
| `PurchaseOrderDetailView` | `purchases:po_detail` | Detail view |
| `PurchaseOrderUpdateView` | `purchases:po_edit` | Edit (DRAFT only) |
| `PurchaseOrderConfirmView` | `purchases:po_confirm` | DRAFT → CONFIRMED |
| `PurchaseOrderReceiveView` | `purchases:po_receive` | CONFIRMED → RECEIVED + creates SI |
| `PurchaseOrderCancelView` | `purchases:po_cancel` | Cancel |
| `PurchaseOrderCloneView` | `purchases:po_clone` | Clone to new DRAFT |
| `PurchaseOrderDeleteView` | `purchases:po_delete` | Delete DRAFT only |
| `SupplierInvoiceListView` | `purchases:supplier_invoice_list` | Datatable list |
| `SupplierInvoiceCreateView` | `purchases:supplier_invoice_create` | Full-page form |
| `SupplierInvoiceDetailView` | `purchases:supplier_invoice_detail` | Detail view |
| `SupplierInvoiceUpdateView` | `purchases:supplier_invoice_edit` | Edit (DRAFT only) |
| `SupplierInvoiceConfirmView` | `purchases:supplier_invoice_confirm` | DRAFT → CONFIRMED |
| `SupplierInvoiceCancelView` | `purchases:supplier_invoice_cancel` | Cancel |
| `SupplierInvoiceReopenView` | `purchases:supplier_invoice_reopen` | CANCELLED → DRAFT |
| `SupplierInvoiceCloneView` | `purchases:supplier_invoice_clone` | Clone to new DRAFT |
| `SupplierInvoiceDeleteView` | `purchases:supplier_invoice_delete` | Delete DRAFT only |
| `SupplierPaymentListView` | `purchases:supplier_payment_list` | Datatable list |
| `SupplierPaymentCreateView` | `purchases:supplier_payment_create` | Full-page form with invoice allocations |
| `SupplierPaymentDetailView` | `purchases:supplier_payment_detail` | Detail view |
| `SupplierPaymentDeleteView` | `purchases:supplier_payment_delete` | Reversal via service |
| `OutstandingSupplierInvoicesView` | `purchases:outstanding_supplier_invoices` | HTMX partial — unpaid invoices for payment form |

**HTMX views** (`apps/purchases/views/htmx.py`):

| View | URL name | Description |
|------|----------|-------------|
| `SupplierSearchView` | `purchases:supplier_search` | Supplier picker results (`purchases/partials/supplier_picker_results.html`) |
| `SupplierQuickCreateView` | `purchases:supplier_quick_create` | Quick-create supplier inline; returns JSON `{pk, name, rnc_cedula}` |
| `PurchaseItemSearchView` | `purchases:purchase_item_search` | Item picker — PURCHASE+BOTH items only |
| `PurchaseItemQuickCreateView` | `purchases:item_quick_create` | Quick-create purchase item; sets `item_type=PURCHASE` |

Supplier picker uses `static/js/supplier-picker.js` + `purchases/partials/supplier_picker_modal.html`. Pattern mirrors the sales customer picker. Both use the shared `createPicker(cfg)` factory — see [Shared picker base](#shared-picker-base-staticjspicker-basejs).

**Purchasing management commands:**

```bash
python manage.py seed_purchasing_documents          # Seed 50 items, 50 suppliers, 500 POs, 500 invoices (requires --org <slug>)
python manage.py seed_purchasing_documents --clear  # Wipe then re-seed
python manage.py seed_purchasing_documents --skip-payments
```

**Reports** (`apps/purchases/views/reports.py`, `admin_required = True`):

| View | URL name | Description |
|------|----------|-------------|
| `ReportPurchasesIndexView` | `purchases:reports` | Report hub |
| `Report606View` | `purchases:report_606` | DGII 606 CSV (supplier invoices by month/year) |
| `ReportAPAgingView` | `purchases:report_aging` | AP aging buckets — confirmed SI with due_date |
| `ReportSupplierStatementView` | `purchases:report_statement` | Supplier account statement |
| `ReportSpendByPeriodView` | `purchases:report_spend_period` | Spend by day/month |
| `ReportPurchasesBySupplierView` | `purchases:report_by_supplier` | Invoices grouped by supplier |
| `ReportSupplierPaymentsView` | `purchases:report_payments` | Payments by date range |
| `ReportITBISCreditsView` | `purchases:report_itbis` | ITBIS credits (16%/18%) by period |

Report cache keys: `f"report_606:{org.pk}:..."`, `f"report_ap_aging:{org.pk}:..."`, etc. TTL 600s. `Report606View` with `format=csv` skips cache (file download).

**Deletion pattern** additions:
- `SupplierDeleteView` — blocked if has `PurchaseDocument` or `SupplierPayment`.
- Purchase order/invoice delete — DRAFT only; raises `PermissionDenied` otherwise.

### Unified report center (`apps/core/views_reports.py`)

`ReportCenterView` (`core:reports`, staff-only) consolidates all sales + purchasing report links in one template (`templates/core/reports.html`). Sidebar links to `core:reports`. The old per-app `sales:reports` and `purchases:reports` index views are removed; their individual report views remain.

### Customer service (`apps/sales/services.py`)

`CustomerService.get_account_summary(customer, organization)` — returns dict: `invoices` (confirmed queryset), `totals` (subtotal/itbis/total), `balance` (outstanding), `aging` (bucket breakdown), `recent_payments`, `credit`. Used by `CustomerDetailView` context.

### CI / CD

`.github/workflows/ci.yml` runs on every push/PR to `main`:

1. **Security audit** (`pip-audit`) — scans `requirements.txt` for known vulnerabilities.
2. **Tests** — spins up `postgres:16-alpine` service container, runs `pytest` using `config.settings.development`.

CI env vars: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `SECRET_KEY`, `ALLOWED_HOSTS`.

### Production deployment

`docker-compose.prod.yml` runs two services:

- **`db`** — `postgres:16-alpine` with named `postgres_data` volume; requires `DB_PASSWORD` env var.
- **`app`** — built from `Dockerfile`; reads `.env` via `env_file`; uses `config.settings.production`; exposes port 8000; mounts `media/` + `logs/` volumes.

Start with: `docker compose -f docker-compose.prod.yml up -d`

Custom error pages: `templates/404.html` + `templates/500.html` (Bootstrap 5, no JS).

### Auth templates (`templates/account/`, `templates/accounts/`, `templates/base_anon.html`)

`base_anon.html` provides a two-column split layout — **do not** wrap auth page content in Bootstrap grid rows.

**Layout:**
- Left panel (`.auth-brand`, `#1e2130`, 400px sticky) — logo, eyebrow label, Cormorant Garamond headline, feature list, copyright. Hidden on mobile (`< 768px`).
- Right panel (`.auth-panel`, `#f4f6fb`, flex-grows) — vertically centers `{% block content %}`.

**CSS classes** (all inlined in `base_anon.html` `<style>` block, auth-only):

| Class | Purpose |
|-------|---------|
| `.auth-card` | White card, `border-top: 4px solid #1e2130`, `border-radius: 10px`, max-width 420px |
| `.auth-eyebrow` | `0.6rem` uppercase `#5b9af5` label above title |
| `.auth-card-title` | Cormorant Garamond 1.75rem serif heading |
| `.auth-card-sub` | `0.8rem` muted subtitle, `margin-bottom: 24px` |
| `.auth-divider` | `1px solid #eef0f6` horizontal rule |
| `.auth-foot` | Centered small footer link line |
| `.auth-btn` | Base button: full-width flex, `border-radius: 8px`, `font-weight: 600` |
| `.auth-btn-primary` | Dark fill (`#1e2130`) — primary CTA |
| `.auth-btn-secondary` | Outline (`border: 1px solid #d1d5db`) — secondary action |
| `.auth-status-icon` | 56×56px rounded icon bubble; variants: `is-success`, `is-warning`, `is-primary`, `is-danger`, `is-muted` |

**Each auth page template** puts exactly one `.auth-card` div in `{% block content %}`. Status/confirmation pages add `.text-center` to the card. No Bootstrap `row`/`col` wrappers.

### Settings & i18n

- Default language: Spanish (`LANGUAGE_CODE = "es"`); English also enabled.
- Timezone: `America/Santo_Domingo`.
- Crispy forms use `bootstrap5` pack.
- `MESSAGE_TAGS` maps `ERROR` → `"danger"` to match Bootstrap 5 alert classes.
- `ANONYMOUS_USER_NAME = None` (disables guardian anonymous user).
- `django.contrib.humanize` installed (`{% load humanize %}` → `intcomma`, `naturaltime`, etc.).
- **`BEHIND_PROXY`** (env var, default `False`) — set `True` when app is behind a reverse proxy (e.g. Cloudflare Tunnel). Enables `SECURE_PROXY_SSL_HEADER`, secure cookies, and `CSRF_TRUSTED_ORIGINS`. Do NOT combine with `SECURE_SSL_REDIRECT=True` (causes redirect loop). Use `BEHIND_PROXY=true` for Cloudflare Tunnel deployments.
- **Date/time widgets** (`apps/core/widgets.py`) — `DateInput` (type="date"), `DateTimeInput` (type="datetime-local", format `%Y-%m-%dT%H:%M`), `TimeInput` (type="time"). Native browser pickers — no Flatpickr JS dependency.
