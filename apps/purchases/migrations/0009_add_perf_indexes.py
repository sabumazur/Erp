"""
Performance index migration for apps/purchases.

Rules applied:
  - CONCURRENTLY so production deploys don't lock tables.
  - atomic = False required for CONCURRENTLY.
  - WHERE deleted_at IS NULL on every soft-delete table — shrinks indexes by
    however many rows are soft-deleted, and prevents stale index pages.
  - INCLUDE clauses for covering indexes that eliminate heap reads on hot paths.
  - Index names are ≤ 63 chars (PostgreSQL hard limit).

New indexes added:
  purchases_purchasedocument
    1. pur_org_si_status_duedt_idx  — (org, doc_type='SI', status, due_date)
       WHERE deleted_at IS NULL AND due_date IS NOT NULL
       Serves: AP Aging, overdue bills (Q5, Q6)

    2. pur_org_si_status_alloc_idx  — (org, doc_type='SI', status)
       INCLUDE (total, supplier_id) WHERE deleted_at IS NULL
       Covering index for payment-coverage annotation (Q4) — eliminates heap
       fetch for total and supplier_id once status+org filter hits the index.

    3. pur_doc_deleted_org_idx — (organization, deleted_at)
       WHERE deleted_at IS NULL
       Supports the soft-delete manager's alive() filter when no other column
       is in the predicate (e.g. admin list_display or migrations).

  purchases_supplier
    4. sup_org_active_name_idx — (organization, is_active, name)
       WHERE deleted_at IS NULL
       Serves: supplier list view, report supplier picker — always filters on
       (organization, is_active=True) and orders by name.

  purchases_supplierpaymentallocation
    5. spa_invoice_amount_idx — (supplier_invoice_id) INCLUDE (amount)
       Covering index for the allocations aggregate join.  Every query doing
       Sum("allocations__amount") filters on supplier_invoice_id and reads
       amount; this index serves both without touching the heap.

    6. spa_payment_invoice_idx — (payment_id, supplier_invoice_id) INCLUDE (amount)
       Covering index for payment detail + delete_payment service which fetches
       all allocations for a payment and reads amount.

Removed / replaced (RunSQL no-op drops so Django state stays clean):
  None — only additive changes.
"""
from django.db import migrations


class Migration(migrations.Migration):

    atomic = False  # required for CREATE INDEX CONCURRENTLY

    dependencies = [
        ("purchases", "0008_alter_historicalsupplierpayment_method_and_more"),
    ]

    operations = [
        # ── 1. AP Aging / Overdue bills ──────────────────────────────────────
        # Covers: filter(organization, doc_type=SI, status=CONFIRMED,
        #                due_date__isnull=False, due_date__lt=today)
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS pur_org_si_status_duedt_idx
                ON purchases_purchasedocument (organization_id, doc_type, status, due_date)
                WHERE deleted_at IS NULL
                  AND due_date IS NOT NULL
                  AND doc_type = 'SUPPLIER_INVOICE';
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS pur_org_si_status_duedt_idx;",
        ),

        # ── 2. Payment coverage covering index ───────────────────────────────
        # Covers: filter(organization, doc_type=SI, status IN [CONFIRMED,PAID])
        # INCLUDE total and supplier_id so Q4 and Q10 need no heap fetch.
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS pur_org_si_cov_idx
                ON purchases_purchasedocument (organization_id, status)
                INCLUDE (total, supplier_id, issue_date, due_date, supplier_ncf)
                WHERE deleted_at IS NULL
                  AND doc_type = 'SUPPLIER_INVOICE';
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS pur_org_si_cov_idx;",
        ),

        # ── 3. Soft-delete / org fallback index ─────────────────────────────
        # Helps the alive() filter when no other predicate narrows the scan.
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS pur_doc_org_alive_idx
                ON purchases_purchasedocument (organization_id)
                WHERE deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS pur_doc_org_alive_idx;",
        ),

        # ── 4. Supplier list / picker ─────────────────────────────────────────
        # Covers: filter(organization=org, is_active=True).order_by("name")
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS sup_org_active_name_idx
                ON purchases_supplier (organization_id, is_active, name)
                WHERE deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS sup_org_active_name_idx;",
        ),

        # ── 5. Allocation covering index (invoice lookup + amount) ────────────
        # Covers: Sum("allocations__amount") where supplier_invoice_id = ?
        # INCLUDE amount eliminates heap read.
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS spa_invoice_amount_cov_idx
                ON purchases_supplierpaymentallocation (supplier_invoice_id)
                INCLUDE (amount, payment_id);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS spa_invoice_amount_cov_idx;",
        ),

        # ── 6. Allocation covering index (payment lookup) ─────────────────────
        # Covers: payment.allocations.all() and delete_payment bulk-check.
        # The existing unique constraint is on (payment_id, supplier_invoice_id)
        # and already serves payment_id lookups, but doesn't INCLUDE amount.
        # This covering index means no heap fetch when reading allocations for
        # a payment (detail view, delete_payment service).
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS spa_pmt_invoice_cov_idx
                ON purchases_supplierpaymentallocation (payment_id, supplier_invoice_id)
                INCLUDE (amount);
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS spa_pmt_invoice_cov_idx;",
        ),

        # ── 7. Partial replacement for pur_org_doctype_status_idx ────────────
        # The existing index is a full-table (no WHERE clause).  This partial
        # version is ~30–60 % smaller depending on soft-delete volume, and lets
        # Postgres use an index-only scan on the alive rows.
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS pur_org_dt_status_alive_idx
                ON purchases_purchasedocument (organization_id, doc_type, status)
                WHERE deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS pur_org_dt_status_alive_idx;",
        ),

        # ── 8. Partial replacement for pur_org_dt_status_date_idx ────────────
        # Same rationale — adds WHERE deleted_at IS NULL.
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS pur_org_dt_st_dt_alive_idx
                ON purchases_purchasedocument
                    (organization_id, doc_type, status, issue_date)
                WHERE deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS pur_org_dt_st_dt_alive_idx;",
        ),

        # ── 9. SupplierPayment soft-delete alive partial index ────────────────
        # suppay_org_supplier_date_idx and suppay_org_date_idx are full indexes.
        # These partial replacements exclude deleted payments (SupplierPayment
        # inherits ERPBaseModel which has deleted_at).
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS suppay_org_sup_dt_alive_idx
                ON purchases_supplierpayment (organization_id, supplier_id, date)
                WHERE deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS suppay_org_sup_dt_alive_idx;",
        ),

        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS suppay_org_dt_alive_idx
                ON purchases_supplierpayment (organization_id, date)
                WHERE deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS suppay_org_dt_alive_idx;",
        ),

        # ── 10. Supplier org+deleted_at alive partial index ───────────────────
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS sup_org_alive_idx
                ON purchases_supplier (organization_id)
                WHERE deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS sup_org_alive_idx;",
        ),
    ]
