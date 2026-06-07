# Purchasing App — Improvement Report

Generated: 2026-06-06  
App: `apps/purchases/`  
Auditor: Senior Django developer review pass

---

## Section A — Seed Command Summary

**File:** `apps/purchases/management/commands/seed_purchasing_documents.py`

| Record type | Target | Notes |
|---|---|---|
| Suppliers | 100 | Full Dominican profile: 9-digit RNC, city, phone, contact name, credit limit, payment term |
| Purchase Orders | 1 000 | DRAFT → CONFIRMED via `PurchaseOrderService.confirm()`. 3–5 line items each. |
| Supplier Invoices | 1 000 | Created via `PurchaseOrderService.receive_and_invoice()`, then `SupplierInvoiceService.confirm()` |
| Supplier Payments | 500 | Random half of confirmed invoices, full invoice total via `SupplierPaymentService.create_payment()` |

**Dominican data used:**
- Company names: prefix + mid + legal suffix (e.g. "Distribuidora del Caribe S.R.L.")
- RNCs: random unique 9-digit integers in range 100 000 000 – 999 999 999
- Cities: 15 Dominican provinces/cities
- Contact names: DR first + last name lists
- NCFs: sequential `B01XXXXXXXXXX` (12-digit zero-padded) — unique per org

**Flags:**
- `--org <slug>` — required
- `--clear` — hard-deletes all purchasing records for the org before seeding (in safe dependency order)
- `--skip-payments` — seeds 0 payments (for faster PO/invoice-only runs)

**Services called (no business logic bypassed):**

```
PurchaseOrderService.confirm(po)
PurchaseOrderService.receive_and_invoice(po)   → creates DRAFT SI
SupplierInvoiceService.confirm(si)
SupplierPaymentService.create_payment(...)
```

Bulk creation is wrapped in `transaction.atomic` blocks of 100 records. Progress is printed every chunk.

---

## Section B — Performance Test Summary

**File:** `apps/purchases/management/commands/perf_test_purchasing.py`

Usage: `python manage.py perf_test_purchasing --org <slug> [--runs N]`

| # | Query | Expected index |
|---|---|---|
| 1 | Supplier invoice list (CONFIRMED + PAID) with totals | `pur_org_doctype_status_idx` |
| 2 | Purchase orders — last 90 days | `pur_org_dt_status_date_idx` |
| 3 | Spend by supplier — top 20 by total (SQL `ORDER BY … LIMIT 20`) | `pur_org_supplier_idx` |
| 4 | Payment coverage annotation (paid/partial/unpaid via `annotate`) | `pur_org_doctype_status_idx` + allocation join |
| 5 | Overdue bills — `due_date < today`, not fully paid | `pur_org_dt_status_date_idx` |

**Warning threshold:** 200 ms per query. The command prints `⚠ SLOW` and an advisory if exceeded.

**Indexes currently present (from models.py):**

```
pur_org_doctype_status_idx     (organization, doc_type, status)
pur_org_supplier_idx           (organization, supplier)
pur_org_dt_status_date_idx     (organization, doc_type, status, issue_date)
suppay_org_supplier_date_idx   (organization, supplier, date)
suppay_org_date_idx            (organization, date)
```

All five indexes are **unconditional** — they include soft-deleted rows (`deleted_at IS NOT NULL`). After seeding 1 000 invoices, queries 1, 2, and 5 should complete well under 200 ms on a local Postgres instance.

**Expected slow-query risk:** Query 4 (payment coverage annotation) performs a LEFT JOIN on `SupplierPaymentAllocation`. With 500 payments × ≤5 allocations each and no partial index on `(supplier_invoice_id)`, this could approach the threshold at scale; see Section F.

---

## Section C — Audit Findings

### Critical — Must Fix Now

---

**C-01 · Missing `transaction.atomic` in `PurchaseOrderCreateView.post`**

- **File:** `apps/purchases/views/purchase_orders.py`, lines 97–116
- **Problem:** `po.save()` (line 107), `formset.save()` (line 109), and `po.recompute_totals()` (line 110) run in three separate DB transactions. If `formset.save()` raises an `IntegrityError` (e.g. item org mismatch), the PO header row persists with no line items and an incorrect total of 0.00.
- **Fix:**

```python
def post(self, request):
    form = PurchaseOrderForm(...)
    formset = PurchaseDocumentItemFormSet(...)
    if form.is_valid() and formset.is_valid():
        with transaction.atomic():          # ← add this
            po = form.save(commit=False)
            po.organization = request.organization
            po.doc_type = PurchaseDocument.DocType.PURCHASE_ORDER
            po.save()
            formset.instance = po
            formset.save()
            po.recompute_totals()
        ...
```

- **Severity:** Critical

---

**C-02 · Missing `transaction.atomic` in `SupplierInvoiceCreateView.post`**

- **File:** `apps/purchases/views/supplier_invoices.py`, lines 102–121
- **Problem:** Identical to C-01. `si.save()` + `formset.save()` + `si.recompute_totals()` are three separate writes. Failed formset leaves an orphaned header with zero total and no NCF.
- **Fix:** Wrap lines 109–115 in `with transaction.atomic():`.
- **Severity:** Critical

---

**C-03 · Missing `transaction.atomic` in `PurchaseOrderUpdateView.post`**

- **File:** `apps/purchases/views/purchase_orders.py`, lines 167–182
- **Problem:** `form.save()` + `formset.save()` + `recompute_totals()` are three separate transactions. A mid-save formset failure leaves the PO header in a new state (e.g. new supplier) while line items are still from the old state.
- **Fix:** Wrap lines 175–179 in `with transaction.atomic():`.
- **Severity:** Critical

---

**C-04 · Missing `transaction.atomic` in `SupplierInvoiceUpdateView.post`**

- **File:** `apps/purchases/views/supplier_invoices.py`, lines 172–187
- **Problem:** Same as C-03 for supplier invoice edits.
- **Fix:** Wrap lines 180–184 in `with transaction.atomic():`.
- **Severity:** Critical

---

### Warning — Should Fix Soon

---

**W-01 · Python-side aggregation in `SupplierDetailView`**

- **File:** `apps/purchases/views/suppliers.py`, lines 157–168
- **Problem:** All non-cancelled invoices for a supplier are loaded into Python as a list (`list(...)`) to compute `total_invoiced` with `sum(...)`. A busy supplier with 10 000 invoices pulls the entire result set into memory for one number.
- **Fix:**

```python
from django.db.models import Sum
total_invoiced = (
    PurchaseDocument.supplier_invoices.filter(
        organization=request.organization, supplier=supplier
    ).exclude(status=PurchaseDocument.Status.CANCELLED)
    .aggregate(t=Sum("total"))["t"] or Decimal("0.00")
)
```

Then fetch only the invoices you actually render (paginate or limit to recent N).
- **Severity:** Warning

---

**W-02 · Python-side aggregation in `Report606View`**

- **File:** `apps/purchases/views/reports.py`, lines 117–119
- **Problem:** `total_subtotal`, `total_itbis`, `total_total` are computed with Python `sum()` over the full `invoices` list. With hundreds of invoices in a month this is wasteful; with thousands it degrades.
- **Fix:** Replace with `.aggregate(subtotal=Sum("subtotal"), itbis_18=Sum("itbis_18"), itbis_16=Sum("itbis_16"), total=Sum("total"))` before converting `qs` to a list, then derive `total_itbis = agg["itbis_18"] + agg["itbis_16"]`.
- **Severity:** Warning

---

**W-03 · Full table scan + Python bucketing in `ReportAPAgingView`**

- **File:** `apps/purchases/views/reports.py`, lines 164–184
- **Problem:** All CONFIRMED invoices with a `due_date` are fetched into Python. The aging bucket (`_bucket_for`) is computed in a Python loop. With 5 000+ unpaid invoices this is both slow and memory-heavy. The result set is then sorted in Python (`sorted(..., key=...)`).
- **Fix:** Use `annotate(days_overdue=...)` with `django.db.models.functions.Now()` and a `Case/When` to compute bucket labels in SQL; then `values("supplier_id", "supplier__name", "bucket").annotate(total=Sum("total"))` to get one row per supplier-bucket from the DB.
- **Severity:** Warning

---

**W-04 · No `only()` on list querysets — wide rows fetched**

- **File:** `apps/purchases/views/purchase_orders.py` line 48, `supplier_invoices.py` line 48
- **Problem:** `PurchaseDocument` has 20+ columns. List views fetch every column even though the datatable rows render only 5–6 fields. On large tables this wastes I/O and memory.
- **Fix:** Add `.only("id", "number", "supplier_id", "issue_date", "expected_date", "total", "status")` to the list queryset. Note: `select_related("supplier")` must remain.
- **Severity:** Warning

---

**W-05 · Multiple independent COUNT queries for stats boxes**

- **File:** `apps/purchases/views/purchase_orders.py` lines 59–69, `supplier_invoices.py` lines 62–73
- **Problem:** The stats ribbon makes 3–4 separate COUNT / aggregate queries per page load (non-HTMX). These run synchronously and are not cached.
- **Fix:** Combine into a single `annotate` + `values` query using `Count` with filters, or wrap with `django.core.cache` (600 s TTL) keyed on `org.pk` — matching the pattern already used in report views.
- **Severity:** Warning

---

### Suggestions

---

**S-01 · Partial indexes missing on hot query columns**

- **Problem:** The indexes `pur_org_doctype_status_idx`, `pur_org_dt_status_date_idx`, and `pur_org_supplier_idx` are unconditional — they include soft-deleted rows (`deleted_at IS NOT NULL`). The `PurchaseDocumentManager` always filters `.alive()` (`deleted_at IS NULL`), so every index scan drags in tombstone rows unnecessarily.
- **Fix:** Add `condition=Q(deleted_at__isnull=True)` to each index definition in `PurchaseDocument.Meta.indexes`, then generate and apply a migration.
- **Severity:** Suggestion

---

**S-02 · `SupplierPaymentAllocation` has no index on `supplier_invoice_id`**

- **Problem:** `SupplierPaymentAllocation.objects.filter(supplier_invoice=inv)` appears in `_outstanding()` inside `SupplierPaymentService.create_payment()`. There is no explicit index on `supplier_invoice_id`; Django creates one for FK fields by default but a partial index `WHERE amount > 0` would be faster for the balance lookup.
- **Fix:** Add `models.Index(fields=["supplier_invoice"], name="suppayalloc_invoice_idx")` to `SupplierPaymentAllocation.Meta`.
- **Severity:** Suggestion

---

**S-03 · `delete_payment` uses bare `get()` without `select_for_update()`**

- **File:** `apps/purchases/services.py`, line 294
- **Problem:** After `payment.hard_delete()` removes the allocations, the code does `PurchaseDocument.objects.get(pk=inv_pk)` to check if the invoice should revert to CONFIRMED. Two concurrent `delete_payment` calls on different payments for the same invoice could both read the invoice before either writes, leading to a lost update.
- **Fix:** Wrap the reversal loop in a `select_for_update()` on the invoice:
  ```python
  inv = PurchaseDocument.objects.select_for_update().get(pk=inv_pk)
  ```
- **Severity:** Suggestion (low risk today given single-user usage, higher risk in multi-staff scenario)

---

## Section D — Test Coverage Map

### Models

| Model | Factory | Unit tests |
|---|---|---|
| `Supplier` | ✅ `SupplierFactory` | Partial (validation in existing `test_views.py`) |
| `PurchaseDocument` (PO) | ✅ `PurchaseDocumentFactory` | ✅ service tests + view tests |
| `PurchaseDocument` (SI) | ✅ (same factory, `doc_type` param) | ✅ service tests + view tests |
| `PurchaseDocumentItem` | ✅ `PurchaseDocumentItemFactory` | Covered via service tests |
| `SupplierPayment` | ✅ `SupplierPaymentFactory` | ✅ service tests |
| `SupplierPaymentAllocation` | ❌ no direct factory | Covered implicitly via payment service tests |
| `PurchaseSequence` | ❌ no factory | ✅ tested via `PurchaseOrderService.confirm()` |

### Services

| Service method | Tested |
|---|---|
| `PurchaseOrderService.confirm()` | ✅ happy path, wrong-status, wrong-type, org isolation |
| `PurchaseOrderService.receive_and_invoice()` | Partial (called in cancel tests) |
| `PurchaseOrderService.cancel()` | ✅ draft, confirmed, received guard, already-cancelled guard |
| `SupplierInvoiceService.confirm()` | ✅ happy path, no-NCF, duplicate-NCF, cross-org NCF, already-confirmed |
| `SupplierInvoiceService.cancel()` | ✅ happy path, paid guard, allocated guard |
| `SupplierInvoiceService.reopen()` | ❌ not yet tested |
| `SupplierPaymentService.create_payment()` | ✅ full payment, partial, overpayment, duplicate invoice, wrong org, empty allocations |
| `SupplierPaymentService.delete_payment()` | ✅ revert-to-confirmed, allocation cleanup |

### Views

| View | Login-req | Member | Admin | Org isolation | HTMX |
|---|---|---|---|---|---|
| `PurchaseOrderListView` | ✅ | ✅ | — | ✅ | ✅ |
| `PurchaseOrderDetailView` | — | ✅ | — | ✅ | — |
| `PurchaseOrderConfirmView` | — | ✅ (403) | ✅ | ✅ | — |
| `PurchaseOrderCancelView` | — | ✅ (403) | ✅ | — | — |
| `PurchaseOrderDeleteView` | — | ✅ (403) | ✅ status guard | — | — |
| `SupplierInvoiceListView` | ✅ | ✅ | — | ✅ | ✅ |
| `SupplierInvoiceConfirmView` | — | ✅ (403) | ✅ | ✅ | — |
| `SupplierInvoiceDeleteView` | — | — | ✅ status guard | — | — |
| `SupplierPaymentListView` | ✅ | ✅ | — | ✅ | ✅ |
| `SupplierListView` | ✅ | ✅ | — | ✅ | ✅ HTMX create |
| Report 606 | ✅ | ✅ (403) | ✅ | ✅ | — |
| Report Aging | ✅ | ✅ (403) | ✅ | ✅ | — |
| Report Statement | ✅ | ✅ (403) | ✅ | ✅ (404) | — |
| Report Spend Period | ✅ | ✅ (403) | ✅ | ✅ | — |
| Report By Supplier | ✅ | ✅ (403) | ✅ | ✅ | — |
| Report Payments | ✅ | ✅ (403) | ✅ | ✅ | — |
| Report ITBIS | ✅ | ✅ (403) | ✅ | ✅ | — |

**Still untested:**
- `PurchaseOrderCreateView` (POST with formset — needs `RequestFactory` + formset data)
- `PurchaseOrderUpdateView` (POST with formset)
- `SupplierInvoiceCreateView` / `UpdateView` (POST with formset)
- `SupplierPaymentCreateView` (POST with allocation rows)
- `PurchaseOrderReceiveView`
- `PurchaseOrderCloneView` / `SupplierInvoiceCloneView`
- `SupplierInvoiceReopenView`
- `SupplierUpdateView` / `SupplierDeleteView`
- `SupplierPaymentDeleteView`

---

## Section E — Top 3 Highest-Risk Issues

### Risk #1 — Orphaned PO/SI headers (C-01, C-02, C-03, C-04)

**Justification:** All four create/update views write the document header and line items in separate transactions. Any database-level constraint violation on the formset (item belongs to wrong org, unit_price < 0, etc.) after the header `.save()` will succeed for the header and fail for the lines. The result is a PO/SI row with `total = 0.00`, no line items, and no user-visible error (Django's form error display will show the error, but the database will have the orphan). This is silent data corruption — it won't crash the app, but it will distort totals, the 606 report, and AP aging.

**Immediate fix:** 4 one-liner `with transaction.atomic():` wrappers.

---

### Risk #2 — Memory explosion on supplier detail and Report 606 at scale (W-01, W-02)

**Justification:** `SupplierDetailView` loads every invoice row for a supplier into Python. A supplier with 5 000 invoices in the system forces Django to deserialize 5 000 `PurchaseDocument` objects (each ~20 fields, many Decimal) before doing a Python `sum()`. At ~2 KB/object that's 10 MB per page view. The Report 606 view has the same pattern. Both are cached with a 600 s TTL, but only after the first computation — and cache is per-org, per-URL, so concurrent requests to different months/suppliers all materialize full querysets. On a server with limited RAM this causes OOM kills under normal load.

**Fix:** Replace Python `sum()` with DB `aggregate(Sum(...))` in both views; the invoice list in `SupplierDetailView` should be paginated or limited to the most recent 50.

---

### Risk #3 — Python-only AP Aging report with unbounded growth (W-03)

**Justification:** `ReportAPAgingView` loads **all** CONFIRMED invoices with a due date into Python — there is no date range filter, no pagination, no limit. As the org accumulates unpaid invoices over years, this query will grow linearly. At 10 000 invoices it pulls a ~20 MB result set per cache miss. The Python bucket loop is O(n) but the Django ORM deserialisation overhead is the dominant cost. Because the cache key includes the full query string (`request.GET.urlencode()`), the base view (no params) and any filtered view are cached separately, multiplying the cold-cache cost.

**Fix:** Rewrite using SQL `annotate(days_overdue=ExpressionWrapper(Now() - F("due_date"), output_field=DurationField()))` + `Case/When` for buckets, then `.values("supplier_id", "supplier__name", "bucket").annotate(total=Sum("total"))`. This reduces the result to ≤ (number of suppliers × 5 buckets) rows, regardless of invoice count.

---

## Section F — Recommended Follow-up Tasks

### Migrations (run after fixing)

1. Add `condition=Q(deleted_at__isnull=True)` to `pur_org_doctype_status_idx`, `pur_org_dt_status_date_idx`, `pur_org_supplier_idx` → `makemigrations` + `migrate`.
2. Add `models.Index(fields=["supplier_invoice"], name="suppayalloc_invoice_idx")` to `SupplierPaymentAllocation.Meta`.

### Refactors

3. Wrap all create/update view POST handlers in `transaction.atomic` (C-01 through C-04).
4. Replace Python aggregations in `SupplierDetailView` and `Report606View` with DB `aggregate()` (W-01, W-02).
5. Rewrite `ReportAPAgingView` with SQL bucketing (W-03).
6. Add `.only(...)` to list view querysets (W-04).
7. Cache or combine the stats-box queries in list views (W-05).
8. Add `select_for_update()` in `delete_payment` reversal loop (S-03).

### Missing features / test gaps

9. Write formset POST tests for `PurchaseOrderCreateView` and `SupplierInvoiceCreateView` using `RequestFactory`.
10. Write tests for `SupplierPaymentCreateView.post` with allocation rows.
11. Write tests for `SupplierInvoiceService.reopen()`.
12. Add `SupplierPaymentAllocationFactory` to `tests/factories.py` for cleaner payment service tests.
13. Consider a `receive_and_invoice` service test — currently only called indirectly via `cancel` tests.
14. Add a `SupplierDeleteView` test verifying that suppliers with documents raise `ValueError` and return 400/redirect with message.
