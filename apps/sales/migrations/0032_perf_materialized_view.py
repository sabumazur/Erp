"""
Migration 0032 — Performance: materialized view for customer revenue (Fix 7)

Creates sales_customer_revenue_mv — a pre-aggregated view of confirmed invoice
totals per (organization, customer).  The unique index allows REFRESH
CONCURRENTLY so refreshes don't block readers.

The view is kept fresh by:
  - A post_save signal in apps/sales/signals.py (via transaction.on_commit)
  - A management command `refresh_revenue_mv` for manual / scheduled refresh

Scoped to INVOICE doc_type only (quotations and sale orders are excluded from
revenue figures).

atomic = False: CREATE MATERIALIZED VIEW and its CONCURRENTLY index cannot
run inside a transaction in PostgreSQL.
"""
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # DDL cannot run inside a transaction for MV + CONCURRENTLY

    dependencies = [
        ("sales", "0031_perf_partial_indexes"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE MATERIALIZED VIEW IF NOT EXISTS sales_customer_revenue_mv AS
                SELECT
                    organization_id,
                    customer_id,
                    SUM(total) AS revenue
                FROM sales_salesdocument
                WHERE status = 'CONFIRMED'
                  AND deleted_at IS NULL
                  AND doc_type = 'INVOICE'
                GROUP BY organization_id, customer_id;

                CREATE UNIQUE INDEX IF NOT EXISTS sales_customer_revenue_mv_uniq_idx
                ON sales_customer_revenue_mv (organization_id, customer_id);
            """,
            reverse_sql="""
                DROP MATERIALIZED VIEW IF EXISTS sales_customer_revenue_mv;
            """,
        ),
    ]
