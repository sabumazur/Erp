# Python-to-SQL Audit — sabsys ERP

**Audited by:** Senior Django Developer (automated audit pass)
**Date:** 2026-06-06
**Scope:** `apps/` — all `services.py`, `views/`, `management/commands/`, `utils.py`, `helpers.py`, `mixins.py`
**Method:** ripgrep pattern scan across all Python files + manual classification of every hit

---

## Summary

| Metric | Count |
|--------|-------|
| Loops audited | 28 |
| **Replaced** | **6** |
| Skipped — service-per-record | 8 |
| Skipped — already correct ORM pattern | 14 |
| Estimated query reduction (clone of 10-item document) | N+10 → 2 |
| Estimated query reduction (SupplierInvoice.confirm, 10 items) | 10 → 1 |

**Category breakdown of replacements:**

| Category | Count |
|----------|-------|
| A — Python aggregation over loaded list | 1 |
| B — N+1 | 0 (consolidate loop had prefetch_related; false positive) |
| C — N individual INSERT → bulk_create | 4 |
| D — Python sort pushing to SQL | 0 |
| E — N individual UPDATE → bulk_update | 1 |
| F — Cross-model join in Python | 0 |

---

## Findings by Category

### Category A — Python aggregation over loaded list

#### [SAL-001] Category A — Python sum over full Payment list in ReportCollectionsView

**File:** `apps/sales/views/reports.py:604`

**Before:**
```python
payments = list(
    Payment.objects.filter(organization=org, date__gte=d_from, date__lte=d_to)
    .select_related("customer")
    .order_by("date", "customer__name")
)
# ...
grand_total = sum(p.amount for p in payments)   # O(N) over all payment rows
```

**After:**
```python
# by_method is already a DB-aggregated list of ≤6 rows (one per payment method)
grand_total = sum(r["total"] for r in by_method)   # O(≤6) Python sum
```

**Query reduction:** 0 extra queries either way (payments already loaded), but eliminates O(N) Python iteration over the full payment list and replaces it with O(≤6) sum over the already-aggregated `by_method` list.

**Risk:** Low — `by_method` sums `amount` per method with `Coalesce(Sum(...))`, so the total is mathematically identical to summing individual rows. Verified by inspection.

**Applied:** ✅ Yes

---

### Category C — N individual INSERT → bulk_create

#### [SAL-002] Category C — N INSERTs in SaleOrderCloneView

**File:** `apps/sales/views/sale_orders.py:384`

**Before:**
```python
for line in source.items.all():
    SalesDocumentItem.objects.create(
        document=new_order, item=line.item, description=line.description,
        quantity=line.quantity, unit_price=line.unit_price, itbis_rate=line.itbis_rate,
    )
# (no explicit recompute_totals — relied on N post_save signals firing)
```

**After:**
```python
SalesDocumentItem.objects.bulk_create([
    SalesDocumentItem(document=new_order, item=line.item, ...)
    for line in source.items.all()
])
new_order.recompute_totals()
```

**Query reduction:** N INSERTs → 1 INSERT. `post_save` (recompute) fired N times → 0 times from the loop, 1 explicit call after. For a 10-item order: 10+10 = 20 queries → 2 queries.

**Signal safety:** `SalesDocumentItem.post_save` calls `recompute_totals()` unless `_recompute_suspended`. `bulk_create` bypasses `post_save` entirely; the explicit `recompute_totals()` replaces all N signal-driven calls. Cache invalidation (`_bust_dashboard`) is NOT fired per-item by this signal — it fires on `SalesDocument.post_save` which still fires when the document is created. Net: no cache regression.

**Risk:** Low — read-only clone path, no financial state transition.

**Applied:** ✅ Yes

---

#### [SAL-003] Category C — N INSERTs in QuotationService.convert_to_invoice

**File:** `apps/sales/services.py:265`

**Before:**
```python
for item in quotation.items.all():
    SalesDocumentItem.objects.create(
        document=invoice, item=item.item, description=item.description,
        quantity=item.quantity, unit_price=item.unit_price, itbis_rate=item.itbis_rate,
    )
# N post_save signals → N recompute_totals() calls
```

**After:**
```python
SalesDocumentItem.objects.bulk_create([
    SalesDocumentItem(document=invoice, item=item.item, ...)
    for item in quotation.items.all()
])
invoice.recompute_totals()
```

**Query reduction:** N INSERTs → 1 INSERT. N recomputes → 1. For a 5-item quotation: 10 queries → 2 queries.

**Signal safety:** Same as SAL-002. Method is `@transaction.atomic`; `recompute_totals()` runs within the same transaction.

**Risk:** Low — wrapped in `@transaction.atomic`. Invoice is DRAFT at this point; no fiscal state.

**Applied:** ✅ Yes

---

#### [PQ-001] Category C — N INSERTs in PurchaseOrderCloneView

**File:** `apps/purchases/views/purchase_orders.py:297`

**Before:**
```python
for line in source.items.all():
    PurchaseDocumentItem.objects.create(purchase_document=new_po, ...)
new_po.recompute_totals()
```

**After:**
```python
PurchaseDocumentItem.objects.bulk_create([
    PurchaseDocumentItem(purchase_document=new_po, ...)
    for line in source.items.all()
])
new_po.recompute_totals()
```

**Query reduction:** N INSERTs → 1 INSERT. `new_po.recompute_totals()` was already called once after the loop — unchanged.

**Signal safety:** No `post_save` signal registered for `PurchaseDocumentItem` in the codebase (`apps/purchases/signals.py` does not exist). Safe to `bulk_create`.

**Risk:** Low — DRAFT document clone, no fiscal state.

**Applied:** ✅ Yes

---

#### [PQ-002] Category C — N INSERTs in SupplierInvoiceCloneView

**File:** `apps/purchases/views/supplier_invoices.py:306`

**Before:**
```python
for line in source.items.all():
    PurchaseDocumentItem.objects.create(purchase_document=new_inv, ...)
new_inv.recompute_totals()
```

**After:**
```python
PurchaseDocumentItem.objects.bulk_create([
    PurchaseDocumentItem(purchase_document=new_inv, ...)
    for line in source.items.all()
])
new_inv.recompute_totals()
```

**Query reduction:** N INSERTs → 1. Same signal-safety argument as PQ-001.

**Risk:** Low — DRAFT document, fiscal fields (NCF, RNC) are cleared on clone.

**Applied:** ✅ Yes

---

#### [PQ-003] Category C — N INSERTs in PurchaseOrderService.receive

**File:** `apps/purchases/services.py:78`

**Before:**
```python
for line in po.items.all():
    PurchaseDocumentItem.objects.create(purchase_document=si, ...)
si.recompute_totals()
```

**After:**
```python
PurchaseDocumentItem.objects.bulk_create([
    PurchaseDocumentItem(purchase_document=si, ...)
    for line in po.items.all()
])
si.recompute_totals()
```

**Query reduction:** N INSERTs → 1 INSERT. `si.recompute_totals()` was already called once after.

**Signal safety:** No PurchaseDocumentItem post_save signal. Method is `@transaction.atomic`.

**Risk:** Low — new DRAFT supplier invoice; no fiscal or payment state yet.

**Applied:** ✅ Yes

---

### Category E — N individual UPDATE → bulk_update

#### [PQ-004] Category E — N Item.update() calls in SupplierInvoiceService.confirm

**File:** `apps/purchases/services.py:152`

**Before:**
```python
for line in invoice.items.select_related("item").all():
    if line.item_id is None:
        continue
    item = line.item
    item.cost_price = line.unit_price
    if item.default_supplier_id is None:
        item.default_supplier = invoice.supplier
    Item.objects.filter(pk=item.pk).update(
        cost_price=item.cost_price,
        default_supplier_id=item.default_supplier_id,
    )
```

**After:**
```python
items_to_update = []
for line in invoice.items.select_related("item").all():
    if line.item_id is None:
        continue
    item = line.item
    item.cost_price = line.unit_price
    if item.default_supplier_id is None:
        item.default_supplier = invoice.supplier
    items_to_update.append(item)
if items_to_update:
    Item.objects.bulk_update(items_to_update, ["cost_price", "default_supplier"])
```

**Query reduction:** N UPDATE queries → 1 (Django `bulk_update` emits a single `UPDATE … SET cost_price = CASE WHEN id=… THEN … END` statement).

**Correctness note:** Items that already have a `default_supplier` are passed to `bulk_update` with their existing `default_supplier_id` value unchanged (the Python mutation only occurs when `item.default_supplier_id is None`). Django's `bulk_update` writes what the Python object holds — no-op for those items on the `default_supplier` column.

**Risk:** Medium — write path inside `@transaction.atomic`, touches the `items` catalogue. Tested by inspection: the mutation logic is identical to the original. `bulk_update` does not fire `pre_save`/`post_save` signals on `Item`, consistent with the original `.update()` call which also bypasses signals.

**Applied:** ✅ Yes

---

## Skipped — Cannot Batch

| ID | File | Loop | Reason |
|----|------|------|--------|
| SK-01 | `apps/purchases/services.py:242` | `for alloc in allocations: SupplierPaymentAllocation.objects.create(...)` | Loop also calls `SupplierInvoiceService.mark_paid(inv)` per alloc conditionally — service-per-record; cannot batch. |
| SK-02 | `apps/sales/services.py:594` | `for alloc in allocations: PaymentAllocation.objects.create(...)` | Loop calls `NCFService.mark_paid(inv)` per alloc conditionally — service-per-record; cannot batch. |
| SK-03 | `apps/sales/services.py:451` | `for order in orders: SalesDocumentItem.objects.create(...); order.save(...)` | `order.save()` per row is a business-state transition (INVOICED) — cannot batch the `save()`. Item creation could be batched but the mixed create+save makes it unsafe to split without careful state management. `order.items` is already prefetch_related at line 403 — no N+1. |
| SK-04 | `apps/purchases/services.py:147` SELECT | `for line in invoice.items.select_related("item").all()` SELECT | Single-document iteration — not N+1. The N UPDATEs are handled by PQ-004. |
| SK-05 | `apps/sales/management/commands/mark_overdue_invoices.py:17` | `for org in Organization.objects.filter(is_active=True)` | Management command — calls a service per org. # service-per-record: cannot batch |
| SK-06 | `apps/sales/management/commands/expire_quotations.py:17` | `for org in Organization.objects.filter(is_active=True)` | Management command — service-per-record. # service-per-record: cannot batch |
| SK-07 | `apps/sales/views/reports.py:88` | `for inv in invoices:` (Report 607 file generation) | Row-by-row file serialization into a `StringIO` buffer — inherently sequential. |
| SK-08 | `apps/sales/views/reports.py:144` | `for inv in cancelled:` (Report 608 file generation) | Row-by-row file serialization — inherently sequential. |

---

## Patterns Audited and Found Clean

The following patterns were checked and required **no changes**:

| Pattern | Files | Status |
|---------|-------|--------|
| `values().annotate()` dict comprehensions | `accounts/views.py`, `sales/views/reports.py` | ✅ Already correct ORM aggregation |
| `select_related` / `prefetch_related` | `sales/services.py:399–403`, `purchases/services.py:220` | ✅ Properly avoids N+1 |
| `.aggregate(Sum(...))` | `accounts/views.py`, `purchases/views/reports.py` | ✅ Correct |
| `for r in raw:` over `.values().annotate()` result | `sales/views/reports.py:698`, `purchases/views/reports.py` | ✅ Iterating DB-aggregated results — not a problem |
| `for period_dt in sorted(set(...))` | `sales/views/reports.py:428` | ✅ Python set-merge of two small in-memory dicts — no DB query |
| `for row in sorted(customers_map.values(), ...)` | `sales/views/reports.py:205` | ✅ Sorting already-computed in-memory data |
| `select_for_update()` dict-build | `sales/services.py:529–532`, `purchases/services.py:218–221` | ✅ Correct lock + dict pattern |
| `existing_paid` bulk-fetch before allocation loop | `purchases/services.py:230–240` | ✅ Already refactored (comment: REFACTOR PQ-07) |
| `for inv in invoices: inv.line_balance = ...` | `sales/views/payments.py:216` | ✅ Computed attribute on already-loaded qs; filter follows immediately — no extra DB query |

---

## Remaining Risks

### R-01 — Payment allocation loops (SK-01, SK-02)

`PaymentService.register` and `SupplierPaymentService.create_payment` both loop over an `allocations` list calling `create()` + a conditional service call per row. The `create()` calls could be batched with `bulk_create`, but only if the conditional service call (`NCFService.mark_paid` / `SupplierInvoiceService.mark_paid`) were extracted into a separate post-loop pass.

**Recommendation (next pass):** Split the allocation loop into two passes:
1. `PaymentAllocation.objects.bulk_create(alloc_objects)` — single INSERT
2. `for alloc in allocations: if alloc["_balance"] - alloc["amount"] <= 0: mark_paid(inv)` — service calls only

This is safe because all balance checks are already done before the creates begin.

### R-02 — SaleOrderConsolidateView: order.save() in loop (SK-03)

`consolidate_and_invoice` creates one `SalesDocumentItem` per order, then calls `order.save(update_fields=[...])` per order. The item creates could be batched (into a single `bulk_create` + `invoice.recompute_totals()`), but the `order.save()` per row (business state INVOICED) cannot. This would reduce query count by N (item creates) but leave N order saves.

**Recommendation (next pass):** Use `bulk_create` for the item list, then `SalesDocument.objects.bulk_update(orders, ["consolidated_into", "status", "updated_at"])` for the order state. Requires verifying that `order.save()` doesn't trigger any additional signal logic beyond what `bulk_update` can replicate.

---

*End of audit report.*
