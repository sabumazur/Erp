"""
Management command: refresh_revenue_mv
========================================
Refreshes the sales_customer_revenue_mv materialized view concurrently.

Usage:
    python manage.py refresh_revenue_mv

The CONCURRENTLY keyword allows reads to continue during the refresh.
It requires that the unique index (sales_customer_revenue_mv_uniq_idx)
exists on the view, which is created by migration 0032.

Typical call sites:
  - Celery beat / cron (scheduled nightly or hourly refresh)
  - Post-deploy scripts after bulk data imports
  - Manually by a developer after direct DB edits

The view is also refreshed automatically on each confirmed invoice via the
post_save signal in apps/sales/signals.py (using transaction.on_commit).
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Refresh the sales_customer_revenue_mv materialized view concurrently."

    def handle(self, *args, **options):
        self.stdout.write("Refreshing sales_customer_revenue_mv …")
        with connection.cursor() as cursor:
            cursor.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY sales_customer_revenue_mv;"
            )
        self.stdout.write(self.style.SUCCESS("Done — sales_customer_revenue_mv refreshed."))
