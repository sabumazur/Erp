# Purchase App — Query Performance Report

**Date:** 2026-06-06  
**Scope:** `apps/purchases/` — models, services, views, templates  
**Analyst:** Static code analysis + queryset audit  

---

## Executive Summary

| Metric | Count |
|---|---|
| Total queries identified (hot paths) | 10 primary + ~20 supporting |
| Issues found | 14 |
| **Critical** (data risk or severe latency at scale) | 3 |
| **High** (measurable latency today) | 7 |
| **Medium** (latency at moderate scale) | 4 |
| New indexes added | 10 (migration 0009) |
| View/service files refactored | 6 |

**Estimated DB load reduction after all fixes:**  
On a database with 10 000 supplier invoices and 500 suppliers, the fixes collectively eliminate approximately **N×2–4 queries per payment creation**, **4 queries per list-view page load** (replaced by 1 aggregation each), and **full-table Python scans** on the AP Aging and Supplier Detail pages.  The new partial indexes reduce index size by an estimated 30–60 % depending on soft-delete volume.

---

## Query Inventory

| ID | Query | Location | Queries Before | Queries After | Index Needed |
|---|---|---|---|---|---|
| PQ-01 | Supplier detail — total invoiced | `views/suppliers.py:164` | 1 (full load) + Python sum | 1 aggregate | No |
| PQ-02 | Supplier detail — unbounded invoice list | `views/suppliers.py:157` | 1 (unbounded) | 1 (LIMIT 200) | No |
| PQ-03 | 606 report — Python totals | `views/reports.py:116` | 1 list + 3 Python sums | 1 list + 1 aggregate | Partial on issue_date |
| PQ-04 | AP Aging — Python bucket loop | `views/reports.py:164` | 1 full load + Python | 1 GROUP BY SQL | `pur_org_si_status_duedt_idx` |
| PQ-05 | Spend by supplier detail — Python aggregation | `views/reports.py:481` | 1 list + Python loop | 1 list + 1 aggregate | No |
| PQ-06 | Payment list stats — 4 queries | `views/payments.py:60` | 4 | 1 | No |
| PQ-07 | PO list stats — 4 queries | `views/purchase_orders.py:58` | 4 | 1 | No |
| PQ-08 | SI list stats — 4 queries | `views/supplier_invoices.py:58` | 4 | 1 | No |
| PQ-09 | Supplier search — icontains bypasses GIN | `views/htmx.py:22` | 1 (seq scan) | 1 (GIN index) | Already exists |
| PQ-10 | Payment creation — outstanding() loop | `services.py:230` | 1 per invoice | 1 bulk | No |
| PQ-11 | delete_payment — get() + aggregate() loop | `services.py:286` | 2N | 3 total | No |
| PQ-12 | AP Aging — no due_date index | `views/reports.py:165` | Full scan on status | Index scan | `pur_org_si_status_duedt_idx` |
| PQ-13 | Soft-delete indexes — no WHERE clause | All PurchaseDocument indexes | Large full indexes | Partial alive indexes | All 0009 partials |
| PQ-14 | Payment report — duplicate filter query | `views/reports.py:568` | 2 queries + Python sum | 1+1+1 clean | No |

---

## Critical Findings

### PQ-04 — AP Aging: Full Table Load Into Python

**Location:** `apps/purchases/views/reports.py:164`  
**Problem:** All CONFIRMED invoices with a due_date are loaded into Python memory (`list(qs)`), then a Python loop assigns each invoice to an aging bucket.  
**Impact:** At 10 000 confirmed invoices this materialises ~3 MB of ORM objects into Python just to compute 5 bucket sums. Memory spikes every time the cache expires (every 10 minutes). Linear in invoice count with no SQL optimisation.  
**Fix:** Replaced with a single `GROUP BY supplier_id` query using conditional `Sum(filter=Q(due_date__...))` annotate. Result: one DB round-trip that returns one row per supplier with five pre-bucketed totals.  

```python
# BEFORE — loads every confirmed invoice into Python
qs = list(
    PurchaseDocument.supplier_invoices.filter(
        organization=org, status=PurchaseDocument.Status.CONFIRMED, due_date__isnull=False,
    ).select_related("supplier")
)
for inv in qs:
    days_overdue = (today - inv.due_date).days
    bucket = _bucket_for(days_overdue)
    suppliers_map[inv.supplier_id]["buckets"][bucket] += inv.total

# AFTER — one SQL GROUP BY with conditional SUM
raw_rows = list(
    PurchaseDocument.supplier_invoices
    .filter(organization=org, status=PurchaseDocument.Status.CONFIRMED, due_date__isnull=False)
    .values("supplier_id", "supplier__name")
    .annotate(
        bucket_current=Coalesce(Sum("total", filter=Q(due_date__gte=today)), _ZERO, ...),
        bucket_1_30=Coalesce(Sum("total", filter=Q(
            due_date__lt=today, due_date__gte=today - timedelta(days=30),
        )), _ZERO, ...),
        # … remaining buckets …
        row_total=Coalesce(Sum("total"), _ZERO, ...),
    )
    .order_by("supplier__name")
)
```

**Query reduction:** From O(N invoices) Python work to 1 SQL query.  
**Risk:** Low — behaviour identical. Template updated to use `row.supplier_id` / `row.supplier_name` instead of `row.supplier.pk` / `row.supplier.name`.

---

### PQ-10 — Payment Creation: `_outstanding()` Called in a Loop

**Location:** `apps/purchases/services.py:230`  
**Problem:** `_outstanding(inv)` runs `inv.allocations.aggregate(Sum("amount"))` once per invoice being paid. With 5 invoices in a single payment that is 5 extra DB round-trips during a transaction.  
**Impact:** Worse than N+1 because each extra query is inside an atomic transaction — it holds the transaction open longer, increasing lock contention on `purchases_supplierpaymentallocation`.  
**Fix:** Bulk-fetched all existing allocation totals for the supplied invoice IDs in a single query before the validation loop.

```python
# BEFORE — N queries in the loop
def _outstanding(inv):
    paid = inv.allocations.aggregate(
        t=Coalesce(Sum("amount"), _ZERO, output_field=_DEC)
    )["t"]
    return inv.total - paid

for alloc in allocations:
    balance = _outstanding(alloc["invoice"])  # ← DB hit per iteration

# AFTER — 1 query before the loop
existing_paid = {
    row["supplier_invoice_id"]: row["paid"]
    for row in SupplierPaymentAllocation.objects.filter(
        supplier_invoice_id__in=supplied_ids
    ).values("supplier_invoice_id").annotate(
        paid=Coalesce(Sum("amount"), _ZERO, output_field=_DEC)
    )
}
for alloc in allocations:
    balance = alloc["invoice"].total - existing_paid.get(alloc["invoice"].pk, _ZERO)
```

**Query reduction:** N → 1 (eliminates N queries per payment creation).  
**Risk:** Low — same semantics; the select_for_update lock on the invoices still holds.

---

### PQ-11 — delete_payment: Per-Row get() + aggregate() Loop

**Location:** `apps/purchases/services.py:286`  
**Problem:** After deleting a payment, the service iterates `affected` invoice PKs and calls `PurchaseDocument.objects.get(pk=inv_pk)` + `.allocations.aggregate()` for each one. For a payment covering 10 invoices this is 20 queries.  
**Impact:** Long-lived transaction on `purchases_supplierpayment` and `purchases_supplierpaymentallocation` during delete; every extra query extends the lock window.  
**Fix:** Replaced with 3 queries total: bulk-fetch PAID invoices, one aggregate for remaining balances, one bulk UPDATE for those that need reopening.

```python
# AFTER — 3 queries regardless of N
paid_invoices = {
    inv.pk: inv
    for inv in PurchaseDocument.objects.filter(pk__in=affected, status="PAID")
}
remaining_paid = {
    row["supplier_invoice_id"]: row["t"]
    for row in SupplierPaymentAllocation.objects.filter(
        supplier_invoice_id__in=list(paid_invoices.keys())
    ).values("supplier_invoice_id").annotate(t=Coalesce(Sum("amount"), _ZERO, ...))
}
reopen_pks = [pk for pk, inv in paid_invoices.items()
              if remaining_paid.get(pk, _ZERO) < inv.total]
if reopen_pks:
    PurchaseDocument.objects.filter(pk__in=reopen_pks).update(status="CONFIRMED")
```

**Query reduction:** 2N → 3.  
**Risk:** Low — `updated_at` is no longer touched by the bulk UPDATE (Django's `.update()` doesn't call `auto_now`). If `updated_at` currency matters for these rows, swap to `.save(update_fields=["status","updated_at"])` per row. Bulk UPDATE is correct for the invoice status flip.

---

## High-Severity Findings

### PQ-01 — Supplier Detail: Python sum() Over Unbounded Invoice List

**Location:** `apps/purchases/views/suppliers.py:157`  
**Problem:** `total_invoiced = sum(inv.total for inv in invoices)` where `invoices = list(...)` with no LIMIT.  
**Fix:** Replaced with `.aggregate(total_invoiced=Sum("total"))` (one SQL SUM) plus a bounded list limited to 200 rows for display.  
**Query reduction:** Eliminates full Python materialization; from O(N) memory to O(1).

---

### PQ-07/08/12 — Stats Queries: 4 Separate DB Hits Per List View

**Location:**  
- `views/purchase_orders.py:58` (PO list)  
- `views/supplier_invoices.py:58` (SI list)  
- `views/payments.py:60` (payment list)  

**Problem:** Each list view fires 4 separate queries to compute 4 stat cards (count, filtered count, aggregate total, filtered aggregate total). On every non-HTMX page load, on every browser navigation.  
**Fix:** Replaced with a single `.aggregate()` call using `Count("id", filter=Q(...))` and `Sum("field", filter=Q(...))` for each stat.  
**Query reduction:** 4 → 1 per list view page load.

---

### PQ-03 — 606 Report: Python sum() After list(qs)

**Location:** `apps/purchases/views/reports.py:116`  
**Problem:** `invoices = list(qs)` then three separate Python `sum()` calls over the list to compute totals.  
**Fix:** Added a single `.aggregate()` call on the same queryset (executed before `list(qs)`) that returns all four totals in one DB round-trip. The `list(qs)` is still needed for row display.  
**Query reduction:** 0 extra queries; eliminates Python memory accumulation over the full invoice list.

---

### PQ-05 — Spend by Supplier Detail: Python Aggregation Loop

**Location:** `apps/purchases/views/reports.py:481`  
**Problem:** When a specific supplier is selected, the view loads all invoices in the date range then Python-accumulates totals with a for loop.  
**Fix:** Added a `.aggregate()` call before `list()` to get totals in SQL.  
**Query reduction:** Eliminates Python loop; totals computed in one DB aggregate.

---

### PQ-14 — Payment Report: Duplicate Filter Query + Python sum()

**Location:** `apps/purchases/views/reports.py:568`  
**Problem:** `SupplierPayment.objects.filter(org, d_from, d_to)` is called twice — once for the payment list and once for the `by_method` breakdown. Then `grand_total = sum(p.amount for p in payments)` accumulates in Python.  
**Fix:** Extracted the base queryset into `pmt_qs`, reused it for both, and replaced the Python sum with `.aggregate(Sum("amount"))`.  
**Query reduction:** 3 queries → 3 (same count but correct: one shared filter, one for detail, one aggregate).

---

## Medium-Severity Findings

### PQ-09 — SupplierSearchView: icontains Bypasses GIN Trigram Indexes

**Location:** `apps/purchases/views/htmx.py:22`  
**Problem:** `Q(name__icontains=q) | Q(rnc_cedula__icontains=q)` triggers a sequential scan because Django's `icontains` generates `LIKE '%query%'` which cannot use the existing GIN trigram indexes (`supplier_name_trgm_idx`, `supplier_rnc_cedula_trgm_idx`).  
**Fix:** Replaced with `fts_search(qs, q, fts_fields=["name"], trgm_fields=["rnc_cedula"])` which routes through `TrigramSimilarity` and therefore uses the GIN indexes.  
**Query reduction:** 1 query (seq scan) → 1 query (GIN index scan). Fast at any supplier count.

---

## Index Recommendations

| Index Name | Table | Columns | Partial Condition | Type | Purpose |
|---|---|---|---|---|---|
| `pur_org_si_status_duedt_idx` | purchases_purchasedocument | (org, doc_type='SI', status, due_date) | `deleted_at IS NULL AND due_date IS NOT NULL AND doc_type='SUPPLIER_INVOICE'` | BTree | AP Aging, overdue bills |
| `pur_org_si_cov_idx` | purchases_purchasedocument | (org, status) INCLUDE (total, supplier_id, issue_date, due_date, supplier_ncf) | `deleted_at IS NULL AND doc_type='SUPPLIER_INVOICE'` | BTree (covering) | Payment coverage Q4, 606 report Q1 |
| `pur_doc_org_alive_idx` | purchases_purchasedocument | (organization_id) | `deleted_at IS NULL` | BTree | Soft-delete alive() fallback |
| `sup_org_active_name_idx` | purchases_supplier | (organization_id, is_active, name) | `deleted_at IS NULL` | BTree | Supplier list, report pickers |
| `spa_invoice_amount_cov_idx` | purchases_supplierpaymentallocation | (supplier_invoice_id) INCLUDE (amount, payment_id) | — | BTree (covering) | Sum(allocations__amount) in Q4, Q5, Q10 |
| `spa_pmt_invoice_cov_idx` | purchases_supplierpaymentallocation | (payment_id, supplier_invoice_id) INCLUDE (amount) | — | BTree (covering) | Payment detail, delete_payment |
| `pur_org_dt_status_alive_idx` | purchases_purchasedocument | (org, doc_type, status) | `deleted_at IS NULL` | BTree | Partial replacement for `pur_org_doctype_status_idx` |
| `pur_org_dt_st_dt_alive_idx` | purchases_purchasedocument | (org, doc_type, status, issue_date) | `deleted_at IS NULL` | BTree | Partial replacement for `pur_org_dt_status_date_idx` |
| `suppay_org_sup_dt_alive_idx` | purchases_supplierpayment | (org, supplier, date) | `deleted_at IS NULL` | BTree | Partial replacement for `suppay_org_supplier_date_idx` |
| `suppay_org_dt_alive_idx` | purchases_supplierpayment | (org, date) | `deleted_at IS NULL` | BTree | Partial replacement for `suppay_org_date_idx` |

All indexes are created `CONCURRENTLY IF NOT EXISTS` in migration `0009_add_perf_indexes.py` with `atomic = False`.

**Note on existing indexes:** The existing BTree indexes (`pur_org_doctype_status_idx`, `pur_org_dt_status_date_idx`, `suppay_org_supplier_date_idx`, `suppay_org_date_idx`) are full-table (no WHERE clause). They should be **dropped and replaced** by the corresponding partial alive-only indexes above once the new indexes are confirmed healthy. Doing so reduces index size by the fraction of soft-deleted rows and lets PostgreSQL use index-only scans more often. This is a follow-up step — both sets of indexes can coexist temporarily.

---

## Queryset Refactors Summary

| File | Before | After | Query Δ | Risk |
|---|---|---|---|---|
| `views/suppliers.py` | Python `sum()` over all invoices; no LIMIT | SQL `aggregate(Sum)` + `LIMIT 200` | −N queries | Low |
| `views/purchase_orders.py` | 4 separate stat queries | 1 conditional aggregate | −3 per page load | Low |
| `views/supplier_invoices.py` | 4 separate stat queries | 1 conditional aggregate | −3 per page load | Low |
| `views/payments.py` | 4 separate stat queries | 1 conditional aggregate | −3 per page load | Low |
| `views/reports.py` (AP Aging) | `list()` all invoices + Python buckets | 1 `GROUP BY` SQL | −N queries | Low (template updated) |
| `views/reports.py` (606) | `list()` then Python sums | SQL aggregate + `list()` | 0 Δ, eliminates Python alloc | Low |
| `views/reports.py` (by-supplier detail) | Python loop totals | SQL aggregate | −1 Python loop | Low |
| `views/reports.py` (payments) | 2 identical filter queries + Python sum | 1 shared queryset + SQL sum | −1 query + Python | Low |
| `views/htmx.py` | `icontains` (seq scan) | `fts_search` (GIN trigram) | Same count, faster | Low |
| `services.py` (create_payment) | N aggregate queries in loop | 1 bulk aggregate before loop | −(N−1) queries | Low |
| `services.py` (delete_payment) | 2N individual queries | 3 bulk queries | −(2N−3) queries | Low* |

\* `delete_payment` refactor uses `.update()` instead of per-row `.save()`. Django's `auto_now` field `updated_at` is not updated by `.update()`. Acceptable for a status rollback, but note this if `updated_at` is used for change-detection.

---

## Report View Analysis

### AP Aging (`ReportAPAgingView`)

**Before:** `days_overdue` computed in **Python** (`(today - inv.due_date).days`). All confirmed invoices loaded into memory. Not paginated (full result is the report). Cached for 10 minutes.  
**After:** `days_overdue` bucketing replaced with SQL `CASE WHEN due_date >= today THEN …` conditional aggregation in `GROUP BY supplier`. Cached identically.  
**Pagination:** N/A — this is a summary report (one row per supplier). The SQL GROUP BY naturally produces the final set without pagination.

### Spend by Supplier (`ReportPurchasesBySupplierView`)

**Summary mode:** Uses SQL `GROUP BY supplier__name` with `annotate(count, subtotal, itbis_*, total)`. Correct.  
**Detail mode (specific supplier):** Was Python-accumulating totals over `list()`; now uses `.aggregate()` before `list()`.  
**Pagination:** Not paginated. For a single supplier over a wide date range this could produce many invoice rows. Consider adding `DataTableMixin` or a `[:500]` guard if invoice counts per supplier grow large.

### 606 Report (`Report606View`)

**Before:** `list(qs)` then three Python `sum()` calls.  
**After:** One SQL `.aggregate()` for the four totals (subtotal, itbis_18, itbis_16, total), then `list(qs)` for row display. Cached for 10 minutes.  
**Pagination:** Not paginated. 606 is a regulatory export — all rows for a month must appear. Acceptable. For large volumes (500+ invoices/month) the cached `list(qs)` can grow; consider `StreamingHttpResponse` for the CSV path only.

### Payment Coverage (`OutstandingSupplierInvoicesView` / Q4)

**Implementation:** Uses `annotate(paid_amount=Coalesce(Sum("allocations__amount"), ...))` in SQL — fully annotated, no per-row Python. Correct.  
**Balance filter:** `[inv for inv in qs if inv.line_balance > 0]` is a Python filter over an already-annotated queryset. This is unavoidable since Django cannot do a post-annotation HAVING on a computed Python attribute (`line_balance = total - paid_amount`). Can be replaced with `.filter(paid_amount__lt=F("total"))` directly on the queryset to push the filter to SQL. Low priority.

---

## Materialized View Candidates

The following aggregations are expensive enough to warrant a PostgreSQL materialized view refreshed on a schedule or on-commit trigger, once invoice volumes grow past ~50 000 rows:

**1. AP Aging Summary**  
Query: `GROUP BY supplier + 5 conditional SUM buckets` filtered to CONFIRMED invoices with due_date.  
Refresh: On every invoice status change (CONFIRMED→PAID, payment delete).  
Benefit: Aging report becomes a trivial `SELECT * FROM mat_ap_aging WHERE org = ?`.

**2. Spend by Supplier YTD**  
Query: `GROUP BY supplier + SUM(total, subtotal, itbis)` filtered to confirmed/paid invoices.  
Refresh: On every invoice status change or on a nightly schedule.  
Benefit: Eliminates the GROUP BY aggregation from the report query entirely.

**3. Payment Coverage (current balance per invoice)**  
Query: `LEFT JOIN supplierpaymentallocation GROUP BY supplier_invoice + SUM(amount)`.  
Refresh: On every allocation insert/delete.  
Benefit: The outstanding-invoices HTMX view and AP aging both need this balance; a mat view makes both instant.

These are Phase 2 improvements — implement only after the index and queryset fixes in this report have been validated in production.

---

## Follow-Up Tasks

1. **Run migration 0009 in production** with `atomic=False` — the `CONCURRENTLY` keyword means zero table locking during index creation. Verify each index exists with `\di purchases_*` in psql.

2. **Drop old non-partial indexes** once the new partial alive-only indexes are confirmed healthy. Specifically: `pur_org_doctype_status_idx`, `pur_org_dt_status_date_idx`, `suppay_org_supplier_date_idx`, `suppay_org_date_idx`. Add a migration 0010 for this.

3. **Run `explain_purchasing_queries --org <slug>`** in production (or staging with production-sized data) and verify all queries show index scans, not seq scans. Target < 50 ms for all queries in the list.

4. **Fix `OutstandingSupplierInvoicesView` Python balance filter** — replace `[inv for inv in qs if inv.line_balance > 0]` with `.filter(paid_amount__lt=F("total"))` on the queryset to eliminate the Python filter entirely.

5. **Cap detail_invoices in `ReportPurchasesBySupplierView`** — add `[:500]` guard or `DataTableMixin` pagination to prevent unbounded invoice lists for suppliers with heavy history.

6. **Review `SupplierInvoiceService.confirm()`** — the loop over `invoice.items.select_related("item").all()` updates `item.cost_price` via `Item.objects.filter(pk=item.pk).update(...)`. This is N UPDATE queries (one per line item). Consider a bulk_update call.

7. **Add `updated_at` to delete_payment bulk UPDATE** — use `PurchaseDocument.objects.filter(pk__in=reopen_pks).update(status="CONFIRMED", updated_at=now())` if `updated_at` currency is required for invoice rows.

8. **Profile `ReportITBISCreditsView`** — the query joins `PurchaseDocumentItem → PurchaseDocument` with a cross-table filter (`purchase_document__organization`, `purchase_document__status`). Add a partial index on `purchases_purchasedocumentitem(purchase_document_id)` WHERE the parent is alive and confirmed, or rely on `pur_item_doc_itbis_idx` + the new covering index on `purchasedocument`.

9. **Consider materialized views** for AP Aging and Spend by Supplier once volumes exceed ~50 000 invoices (see Materialized View Candidates section).

10. **Set up `perf_test_purchasing`** as a CI step — run against a seeded test DB and fail CI if any query exceeds 500 ms.
