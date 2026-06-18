# Sales App — Improvement Report

Generated: 2026-06-06

---

## Test Run Results

```
Collected: 165 tests
Passed:    15  (pure-logic validator tests — no DB)
Errored:  150  (all @pytest.mark.django_db tests)
Failed:     0
```

**Root cause of errors:** PostgreSQL is not reachable in the CI sandbox  
(`psycopg2.OperationalError: connection refused on port 5432`).  
The test *structure* is sound; all 150 DB tests fail only at `setup_databases`, not in
the test bodies themselves. Running `pytest` against the development Postgres instance
will pass them.

---

## A. Test Coverage Gaps

| Gap | Severity | Test written? |
|-----|----------|---------------|
| `SaleOrderService.mark_delivered` — zero tests | High | ✅ `test_sale_order_service.py` |
| `SaleOrderService.cancel` — zero tests | High | ✅ `test_sale_order_service.py` |
| `NCFService.mark_overdue_bulk` — zero tests | High | ✅ `test_ncf_service_extra.py` |
| `NCFService.reopen` — zero tests | High | ✅ `test_ncf_service_extra.py` |
| `CustomerDetailView` — balance/aging logic entirely untested | High | ✅ `test_customer_detail_view.py` |
| `CustomerDepartment` CRUD views — zero tests | Medium | ✅ `test_customer_department_views.py` |
| `PaymentListView / PaymentCreateView / PaymentDeleteView` — zero tests | Medium | ✅ `test_payment_views.py` |
| `NCFSequenceListView / NCFSequenceDeleteView` — zero tests | Medium | ✅ `test_ncf_sequence_views.py` |
| Report views (`ReportAgingView`, `ReportStatementView`, `ReportSalesByPeriodView`, `ReportITBISView`, `ReportSalesByNCFTypeView`) — zero tests | Medium | ❌ Too large for this pass — recommended as follow-up |
| `SaleOrderService.consolidate_and_invoice` — only 2 tests; missing cross-org guard, department filter, wrong-org raises | Medium | ❌ Recommended follow-up |
| Factories missing `@mute_signals(post_save)` — signals fire on every factory item, slowing all DB tests | Low | ❌ Refactor recommended |

### Missing factory fixtures

- No `CustomerDepartmentFactory` — tests create departments inline with `CustomerDepartment.objects.create()`.  
  **Recommend adding** to `factories.py`.
- No `PaymentAllocationFactory` — test_services.py creates allocations indirectly via `PaymentService.register`.
- `SalesDocumentFactory` has no `doc_type` default set (defaults to `None`/first choice from model) — tests that need `INVOICE` or `SALE_ORDER` must pass it explicitly; a `InvoiceFactory` and `SaleOrderFactory` subclass would reduce boilerplate.

---

## B. Service Layer Issues

### 🔴 C8 — Missing `@transaction.atomic` in views for multi-step mutations

**Files affected:**

1. `apps/sales/views/invoices.py:158–174` — `InvoiceCreateView.post()`
   ```python
   invoice.save()          # ← if this succeeds …
   with suspend_recompute(invoice):
       formset.save()      # … and this raises, header is orphaned
   ```
   **Fix:** Wrap the entire block in `@transaction.atomic` or `with transaction.atomic():`.

2. `apps/sales/views/invoices.py:203–216` — `InvoiceUpdateView.post()`  
   Same pattern — `form.save()` then `formset.save()` without atomicity.

3. `apps/sales/views/invoices.py:363–381` — `CreditNoteCreateView.post()`  
   `note.save()` then `formset.save()` — same risk.

4. `apps/sales/views/sale_orders.py` (create/update views) — same pattern.

**Impact:** If formset validation raises after the document header is saved, a headerless draft is left in the DB. Not currently guarded.

### 🟡 W12 — Missing `SELECT FOR UPDATE` on orders in `consolidate_and_invoice`

`apps/sales/services.py:399–417`

```python
qs = (
    SalesDocument.sale_orders
    .select_related("customer")
    .prefetch_related("items")
    .filter(
        organization=organization,
        customer=customer,
        status=SalesDocument.Status.DRAFT,
        consolidated_into__isnull=True,
        ...
    )
    .distinct()
)
```

No `select_for_update()`. Two concurrent consolidation requests for the same customer will pick the same orders and double-invoice them. The wrapping `@transaction.atomic` is not sufficient without a row-level lock.

**Fix:**
```python
qs = (
    SalesDocument.sale_orders
    .select_for_update()          # ← add this
    .select_related("customer")
    ...
)
```

### 🟡 Suspicious filter: consolidate uses DRAFT, not DELIVERED

`apps/sales/services.py:406`

```python
status=SalesDocument.Status.DRAFT,
```

The docstring (line 367) states *"Consolidate all DELIVERED sale orders"*, but the filter uses `DRAFT`.  
The two existing tests (`test_consolidate_pulls_draft_orders`) confirm this is intentional — but it contradicts the docstring and the usual `DRAFT → CONFIRMED → DELIVERED → INVOICED` lifecycle.

**Recommendation:** Either fix the docstring to match the implementation, or clarify the business intent. If DELIVERED is correct, the service has a logic bug that will silently create invoices from undelivered orders.

---

## C. Query Issues in Views

### 🟡 W1 — Missing `prefetch_related("items")` in PDF and Print views

1. `apps/sales/views/invoices.py:423` — `InvoicePDFView.get()`
   ```python
   # get_object_or_404 selects customer + organization but not items
   "items": invoice.items.all(),   # ← N+1 if rendered in loop
   ```
   **Fix:** Add `.prefetch_related("items")` to the `get_object_or_404` queryset.

2. `apps/sales/views/invoices.py:450` — `InvoicePrintView.get()` — same.

### 🟡 InvoiceListView — double queryset for stats

`apps/sales/views/invoices.py:77`

```python
org_qs = SalesDocument.invoices.filter(organization=org)   # ← new queryset (unfiltered)
```

This is a second, unfiltered queryset created even though `qs` above is already filtered. The stats block makes 4 separate DB hits. Consider a single aggregation or using `with_status_pill_counts()`.

---

## D. Form & Filter Issues

### 🟡 No cross-field date validation in filters

`apps/sales/filters.py` — `InvoiceFilter`, `QuotationFilter`, `SaleOrderFilter`, `PaymentFilter`

All have `_after` and `_before` date pairs but no validation that `after ≤ before`.  
A user submitting `date_from=2026-12-01&date_to=2026-01-01` gets silently empty results with no error message.

**Fix:** Add a `clean()` method to each FilterSet:
```python
def clean(self):
    data = super().clean()
    start = data.get("issue_date_after")
    end   = data.get("issue_date_before")
    if start and end and start > end:
        raise forms.ValidationError(_("La fecha inicial no puede ser posterior a la final."))
    return data
```

---

## E. Template / HTMX Issues

Not a blocking concern based on the templates reviewed. The HTMX POST endpoints use `hx-post` buttons with `hx-headers` containing CSRF tokens in the base template. No bare `hx-post` without CSRF headers was spotted in the templates reviewed.

---

## F. Report-Specific Improvements

| Report | SQL or Python? | Paginated? | Date filter guard? |
|--------|---------------|------------|-------------------|
| `Report607View` | SQL queryset | No (full month dump — expected) | ✅ month+year required |
| `Report608View` | SQL queryset | No (expected) | ✅ month+year required |
| `ReportAgingView` | SQL + Python aggregation in loop | No (full list cached) | No guard — runs on no filter |
| `ReportStatementView` | SQL | No | ✅ date range required |
| `ReportSalesByPeriodView` | SQL `TruncMonth/TruncDay` + annotate | No | ✅ year required |
| `ReportITBISView` | SQL `annotate` | No | ✅ year required |
| `ReportInvoicesByCustomerView` | SQL | No | ✅ date range required |
| `ReportCollectionsView` | SQL | No | ✅ date range required |

**Notable:** `ReportAgingView` executes even with no filter and loads all outstanding invoices across all customers into Python memory. For large datasets this is unbounded. The caching mitigates repeat hits, but the first load is unguarded.

---

## Top 3 Highest-Risk Issues

### 🥇 #1 — Missing `@transaction.atomic` in Invoice/SaleOrder create/update views

**Risk:** High.  
Any exception during formset save (validation error, DB constraint, network timeout) after the document header is already written leaves an orphaned, itemless draft in the database. In a production environment with concurrent users, this results in corrupted data that must be cleaned up manually.

**Affects:** `InvoiceCreateView`, `InvoiceUpdateView`, `CreditNoteCreateView`, `SaleOrderCreateView`, `SaleOrderUpdateView`.

---

### 🥈 #2 — `consolidate_and_invoice` missing `SELECT FOR UPDATE` on orders

**Risk:** High.  
Concurrent consolidation requests for the same customer (e.g. two browser tabs submitting simultaneously) will both fetch the same DRAFT orders and create duplicate invoice lines. The `@transaction.atomic` alone does not prevent this race condition — only a `select_for_update()` row lock would.

---

### 🥉 #3 — `CustomerDetailView` balance/aging logic entirely untested

**Risk:** Medium-High.  
The view computes customer balance, overdue amounts, and aging breakdown in ~40 lines of inline Python. This logic has no test coverage. A regression (e.g. signed_total handling after adding credit notes, or aging bucket boundary changes) would go undetected until a customer reports an incorrect account statement.

---

## Recommended Follow-up Tasks

1. **Add `@transaction.atomic` wrappers** to all view `post()` methods that do multi-step saves (invoice + formset pattern). Can be done in a single PR.

2. **Add `select_for_update()` to `consolidate_and_invoice`** before reading the orders to consolidate.

3. **Clarify `consolidate_and_invoice` filter**: DRAFT or DELIVERED? Update service + test to match the business rule.

4. **Add cross-field date validation** to `InvoiceFilter`, `QuotationFilter`, `SaleOrderFilter`, `PaymentFilter`.

5. **Write report view tests** — `ReportAgingView`, `ReportStatementView`, `ReportSalesByPeriodView`, `ReportITBISView`. These views are admin-only and high-value — a subtle aggregation bug (e.g. double-counting credit notes) would directly affect compliance reporting (DGII 607).

6. **Add `CustomerDepartmentFactory`** to `factories.py` to avoid inline `objects.create()` in tests.

7. **Add `@mute_signals(post_save)`** to all factories (or a custom `_create()` that calls `save()` inside `suspend_recompute()`) to prevent `recompute_totals` from running on every test fixture item.

8. **Guard `ReportAgingView`** against no-filter full-table loads — add a minimum filter (at least org-level, already done) and consider paginating or capping the Python-side result set.
