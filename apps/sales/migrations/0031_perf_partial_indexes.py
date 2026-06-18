"""
Migration 0031 — Performance: partial indexes with WHERE deleted_at IS NULL

Fix 5 / Q2: partial index for confirmed sale orders — the most common list
  filter for active orders awaiting delivery. Scoped to doc_type = 'SALE_ORDER'
  so the planner selects it only for order queries.

Fix 6: partial variants of the major composite indexes on SalesDocument.
  Soft-delete awareness means every real query adds `deleted_at IS NULL`.
  Adding that predicate here shrinks the index by excluding deleted rows,
  reducing I/O on large orgs.

  We ADD new partial indexes instead of dropping the existing full indexes
  because:
  a) The existing indexes are declared in model Meta.indexes — removing them
     from the DB without removing from the model state would cause drift.
  b) PostgreSQL will prefer the more selective partial index automatically.

  Table: sales_salesdocument  (confirmed by 0023_rename_db_tables)
  Note: issue_date column is named `issue_date` (not `issued_at`).

atomic = False: CONCURRENTLY indexes cannot run inside a transaction.
"""
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # CONCURRENTLY cannot run in a transaction

    dependencies = [
        ("sales", "0030_perf_index_consolidated_covering"),
    ]

    operations = [
        # Fix 5 / Q2: partial index for confirmed sale orders ordered by issue_date
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS so_org_confirmed_date_idx
                ON sales_salesdocument (organization_id, issue_date DESC)
                WHERE status = 'CONFIRMED'
                  AND doc_type = 'SALE_ORDER'
                  AND deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX IF EXISTS so_org_confirmed_date_idx;",
        ),

        # Fix 6: (org, doc_type, status) — primary list/count filter
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS inv_org_doctype_status_partial_idx
                ON sales_salesdocument (organization_id, doc_type, status)
                WHERE deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX IF EXISTS inv_org_doctype_status_partial_idx;",
        ),

        # Fix 6: (org, customer, status) — used by aging report and revenue aggregate
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS inv_org_cust_status_partial_idx
                ON sales_salesdocument (organization_id, customer_id, status)
                WHERE deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX IF EXISTS inv_org_cust_status_partial_idx;",
        ),

        # Fix 6: (org, doc_type, status, issue_date) — list ordering with filter
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS inv_org_dt_status_date_partial_idx
                ON sales_salesdocument (organization_id, doc_type, status, issue_date DESC)
                WHERE deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX IF EXISTS inv_org_dt_status_date_partial_idx;",
        ),
    ]
