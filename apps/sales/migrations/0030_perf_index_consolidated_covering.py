"""
Migration 0030 — Performance: consolidated_into index + revenue covering index

Fix 1 / Q4: index on consolidated_into_id FK so the reverse relation scan
  (consolidated_orders) used by the consolidated-invoice lookup is fast.

Fix 3 / Q3: covering index on (organization_id, status, customer_id) INCLUDE (total)
  so the revenue-by-customer GROUP BY aggregate can be satisfied from the index
  alone without hitting the heap.  Uses WHERE deleted_at IS NULL to keep the
  index small (soft-deleted rows are excluded from all revenue queries).

atomic = False is required because CREATE INDEX CONCURRENTLY cannot run inside
a transaction, and INCLUDE … CONCURRENTLY requires the same.
"""
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # CONCURRENTLY + INCLUDE cannot run in a transaction

    dependencies = [
        ("sales", "0029_alter_historicalpayment_method_and_more"),
    ]

    operations = [
        # Fix 1 / Q4: FK index — speeds up consolidated_orders reverse relation
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS so_consolidated_into_idx
                ON sales_salesdocument (consolidated_into_id)
                WHERE consolidated_into_id IS NOT NULL;
            """,
            reverse_sql="DROP INDEX IF EXISTS so_consolidated_into_idx;",
        ),

        # Fix 3 / Q3: covering index for revenue aggregate query
        # INCLUDE pushes `total` into the index leaf so the GROUP BY SUM(total)
        # never needs a heap fetch for active (non-deleted) rows.
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS inv_revenue_covering_idx
                ON sales_salesdocument (organization_id, status, customer_id)
                INCLUDE (total)
                WHERE deleted_at IS NULL;
            """,
            reverse_sql="DROP INDEX IF EXISTS inv_revenue_covering_idx;",
        ),
    ]
