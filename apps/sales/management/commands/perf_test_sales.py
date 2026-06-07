"""
Management command: perf_test_sales
=====================================
Runs 5 timed database queries against the sales data for a given organization
and prints a results table. Warns when any query exceeds 200 ms.

Usage:
    python manage.py perf_test_sales --org <slug>
    python manage.py perf_test_sales --org <slug> --runs 3

Queries tested:
  1. List all invoices for the org with totals  (SELECT + annotate)
  2. Filter sale orders by date range  (last 90 days)
  3. Aggregate revenue by customer  (top 20, GROUP BY)
  4. Consolidated invoice lookup  (join sale orders → invoices)
  5. Full-text / trigram search on quotation reference and customer name
"""
import random
import time
from datetime import date, timedelta

from django.contrib.postgres.search import TrigramSimilarity
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce

from apps.accounts.models import Organization
from apps.sales.models import SalesDocument, SalesDocumentItem

WARN_MS = 200          # emit a warning if a query exceeds this threshold
COL_NAME_W = 52        # column widths for the results table
COL_ROWS_W = 8
COL_MS_W   = 10


class Command(BaseCommand):
    help = "Run 5 timed sales queries and print a performance results table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--org",
            required=True,
            help="Organization slug to query against.",
        )
        parser.add_argument(
            "--runs",
            type=int,
            default=1,
            help="Number of repetitions per query (best time is reported). Default: 1.",
        )

    def handle(self, *args, **options):
        slug = options["org"]
        runs = max(1, options["runs"])

        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization '{slug}' not found.")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\nPerformance test — org: {org.name}  (best of {runs} run(s))\n"
            )
        )

        queries = [
            ("1. Invoice list with totals",         self._q1_invoice_totals),
            ("2. Sale orders — last 90 days",        self._q2_orders_date_range),
            ("3. Revenue by customer (top 20)",      self._q3_revenue_by_customer),
            ("4. Consolidated invoice lookup",       self._q4_consolidated_lookup),
            ("5. Quotation FTS / trigram search",    self._q5_fts_search),
        ]

        results = []
        for label, func in queries:
            best_ms    = float("inf")
            best_count = 0
            for _ in range(runs):
                count, ms = self._time(func, org)
                if ms < best_ms:
                    best_ms    = ms
                    best_count = count
            results.append((label, best_count, best_ms))

        self._print_table(results)

    # ── Query implementations ─────────────────────────────────────────────────

    def _q1_invoice_totals(self, org):
        """
        Fetch all invoices for the org with annotated signed_totals.
        Tests the invoice_org_doctype_status_idx index and with_signed_totals()
        QuerySet method.
        """
        qs = (
            SalesDocument.invoices
            .filter(organization=org)
            .with_signed_totals()
            .values(
                "id", "encf", "doc_type", "status",
                "issue_date", "due_date", "customer_id",
                "signed_subtotal", "signed_itbis_18", "signed_total",
            )
            .order_by("-issue_date")
        )
        rows = list(qs)
        return len(rows)

    def _q2_orders_date_range(self, org):
        """
        Filter sale orders issued in the last 90 days.
        Tests inv_org_dt_status_date_idx (organization, doc_type, issue_date).
        """
        cutoff = date.today() - timedelta(days=90)
        qs = (
            SalesDocument.sale_orders
            .filter(
                organization=org,
                issue_date__gte=cutoff,
            )
            .select_related("customer")
            .values(
                "id", "doc_number", "status", "issue_date",
                "customer__name", "total",
            )
            .order_by("-issue_date")
        )
        rows = list(qs)
        return len(rows)

    def _q3_revenue_by_customer(self, org):
        """
        Aggregate confirmed/sent/paid invoice totals grouped by customer.
        Returns top-20 customers by revenue — tests inv_org_customer_status_idx.
        """
        payable_statuses = [
            SalesDocument.Status.CONFIRMED,
            SalesDocument.Status.SENT,
            SalesDocument.Status.PAID,
            SalesDocument.Status.OVERDUE,
        ]
        qs = (
            SalesDocument.invoices
            .filter(organization=org, status__in=payable_statuses)
            .values("customer_id", "customer__name")
            .annotate(
                invoice_count=Count("id"),
                total_revenue=Coalesce(
                    Sum("total"),
                    0,
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                ),
                total_itbis=Coalesce(
                    Sum(F("itbis_18") + F("itbis_16")),
                    0,
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                ),
            )
            .order_by("-total_revenue")[:20]
        )
        rows = list(qs)
        return len(rows)

    def _q4_consolidated_lookup(self, org):
        """
        For every consolidated invoice, fetch the invoice header plus a count
        and subtotal sum of its constituent sale orders.

        Fix Q4: replaced correlated Subquery/OuterRef with a single annotated
        queryset using Count + Sum — eliminates the N+1 correlated subquery.
        Uses so_consolidated_into_idx for the reverse FK scan.
        """
        qs = (
            SalesDocument.invoices
            .filter(
                organization=org,
                consolidated_orders__isnull=False,
            )
            .annotate(
                order_count=Count("consolidated_orders", distinct=True),
                orders_subtotal=Coalesce(
                    Sum("consolidated_orders__subtotal"),
                    0,
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                ),
            )
            .select_related("customer")
            .values(
                "id", "encf", "status", "issue_date",
                "customer_id", "total", "order_count", "orders_subtotal",
            )
            .order_by("-issue_date")
        )
        rows = list(qs)
        return len(rows)

    def _q5_fts_search(self, org):
        """
        Trigram search across quotation doc_number and customer name.

        Fix Q5: replaced icontains with TrigramSimilarity on doc_number
        (exercises the invoice_doc_number_trgm_idx GIN index).
        customer__name falls back to icontains since FK traversal is not
        supported by TrigramSimilarity annotations.
        """
        search_terms = ["COT", "Distribuidora", "S.R.L.", "Servicios", "Caribe"]
        term = random.choice(search_terms)

        qs = (
            SalesDocument.quotations
            .filter(organization=org)
            .annotate(sim_doc=TrigramSimilarity("doc_number", term))
            .filter(
                Q(sim_doc__gte=0.1)
                | Q(customer__name__icontains=term)
            )
            .select_related("customer")
            .values(
                "id", "doc_number", "status", "issue_date",
                "customer__name", "total", "sim_doc",
            )
            .order_by("-sim_doc", "-issue_date")
        )
        rows = list(qs)
        return len(rows)

    # ── Timing helper ─────────────────────────────────────────────────────────

    def _time(self, func, org):
        """Execute `func(org)`, return (row_count, elapsed_ms)."""
        t0    = time.perf_counter()
        count = func(org)
        ms    = (time.perf_counter() - t0) * 1_000
        return count, ms

    # ── Output ────────────────────────────────────────────────────────────────

    def _print_table(self, results) -> None:
        divider = (
            f"  {'─' * COL_NAME_W}  {'─' * COL_ROWS_W}  {'─' * COL_MS_W}"
        )
        header = (
            f"  {'Query':<{COL_NAME_W}}  "
            f"{'Rows':>{COL_ROWS_W}}  "
            f"{'Time (ms)':>{COL_MS_W}}"
        )

        self.stdout.write(divider)
        self.stdout.write(header)
        self.stdout.write(divider)

        any_slow = False
        for label, count, ms in results:
            slow = ms > WARN_MS
            if slow:
                any_slow = True

            ms_str = f"{ms:>8.1f} ms"
            row = (
                f"  {label:<{COL_NAME_W}}  "
                f"{count:>{COL_ROWS_W},}  "
                f"{ms_str:>{COL_MS_W + 3}}"
            )

            if slow:
                self.stdout.write(self.style.WARNING(row + "  ⚠ SLOW"))
            else:
                self.stdout.write(row)

        self.stdout.write(divider)

        if any_slow:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  ⚠  One or more queries exceeded {WARN_MS} ms threshold.\n"
                    "     Consider adding a database index, reviewing query structure,\n"
                    "     or running EXPLAIN ANALYZE in psql for diagnosis.\n"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n  All queries completed under {WARN_MS} ms.\n")
            )
