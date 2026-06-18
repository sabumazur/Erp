"""
Management command: perf_test_purchasing
=========================================
Runs 5 timed database queries against purchasing data for a given organization
and prints a results table. Warns when any query exceeds 200 ms.

Usage:
    python manage.py perf_test_purchasing --org <slug>
    python manage.py perf_test_purchasing --org <slug> --runs 3

Queries tested:
  1. Supplier invoice list — all CONFIRMED/PAID bills with totals
  2. Purchase orders by date range — last 90 days
  3. Spend by supplier — top 20 by total billed (SQL ORDER BY + LIMIT)
  4. Payment coverage — invoices annotated with paid/partial/unpaid status
  5. Overdue bills — confirmed invoices past due date, not fully paid
"""
import time
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce

from apps.accounts.models import Organization
from apps.purchases.models import PurchaseDocument, SupplierPaymentAllocation

WARN_MS = 200          # emit a warning if a query exceeds this threshold
COL_NAME_W = 52        # column widths for the results table
COL_ROWS_W = 8
COL_MS_W   = 10

_ZERO = Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
_DEC  = DecimalField(max_digits=14, decimal_places=2)


class Command(BaseCommand):
    help = "Run 5 timed purchasing queries and print a performance results table."

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
            ("1. Supplier invoice list with totals",        self._q1_invoice_totals),
            ("2. Purchase orders — last 90 days",            self._q2_po_date_range),
            ("3. Spend by supplier (top 20)",                self._q3_spend_by_supplier),
            ("4. Payment coverage annotation",               self._q4_payment_coverage),
            ("5. Overdue bills (past due, not fully paid)",  self._q5_overdue_bills),
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
        Fetch all CONFIRMED/PAID supplier invoices for the org.
        Tests pur_org_doctype_status_idx and pur_org_dt_status_date_idx.
        """
        statuses = [PurchaseDocument.Status.CONFIRMED, PurchaseDocument.Status.PAID]
        qs = (
            PurchaseDocument.supplier_invoices
            .filter(organization=org, status__in=statuses)
            .select_related("supplier")
            .values(
                "id", "supplier_ncf", "status", "issue_date", "due_date",
                "supplier_id", "supplier__name",
                "subtotal", "itbis_18", "itbis_16", "total",
            )
            .order_by("-issue_date")
        )
        rows = list(qs)
        return len(rows)

    def _q2_po_date_range(self, org):
        """
        Filter purchase orders issued in the last 90 days.
        Tests pur_org_dt_status_date_idx (organization, doc_type, status, issue_date).
        """
        cutoff = date.today() - timedelta(days=90)
        qs = (
            PurchaseDocument.purchase_orders
            .filter(organization=org, issue_date__gte=cutoff)
            .select_related("supplier")
            .values(
                "id", "number", "status", "issue_date", "expected_date",
                "supplier__name", "total",
            )
            .order_by("-issue_date")
        )
        rows = list(qs)
        return len(rows)

    def _q3_spend_by_supplier(self, org):
        """
        Aggregate confirmed/paid invoice totals grouped by supplier.
        Returns top-20 suppliers by total billed — SQL-level ORDER BY + LIMIT 20.
        Tests pur_org_supplier_idx and pur_org_doctype_status_idx.
        """
        statuses = [PurchaseDocument.Status.CONFIRMED, PurchaseDocument.Status.PAID]
        qs = (
            PurchaseDocument.supplier_invoices
            .filter(organization=org, status__in=statuses)
            .values("supplier_id", "supplier__name")
            .annotate(
                invoice_count=Count("id"),
                total_spend=Coalesce(Sum("total"), _ZERO, output_field=_DEC),
                total_itbis=Coalesce(
                    Sum(F("itbis_18") + F("itbis_16")), _ZERO, output_field=_DEC
                ),
            )
            .order_by("-total_spend")[:20]
        )
        rows = list(qs)
        return len(rows)

    def _q4_payment_coverage(self, org):
        """
        Annotate supplier invoices with their paid amount and a payment status
        (PAID / PARTIAL / UNPAID) derived entirely in SQL.
        Tests pur_org_doctype_status_idx and suppay_org_supplier_date_idx.
        """
        statuses = [PurchaseDocument.Status.CONFIRMED, PurchaseDocument.Status.PAID]
        qs = (
            PurchaseDocument.supplier_invoices
            .filter(organization=org, status__in=statuses)
            .annotate(
                paid_amount=Coalesce(
                    Sum("allocations__amount"), _ZERO, output_field=_DEC
                )
            )
            .annotate(
                payment_status=Case(
                    When(paid_amount=F("total"), then=Value("PAID")),
                    When(paid_amount=Value(0, output_field=_DEC), then=Value("UNPAID")),
                    default=Value("PARTIAL"),
                )
            )
            .values(
                "id", "supplier_ncf", "issue_date", "due_date", "total",
                "paid_amount", "payment_status", "supplier__name",
            )
            .order_by("-issue_date")
        )
        rows = list(qs)
        return len(rows)

    def _q5_overdue_bills(self, org):
        """
        Find CONFIRMED invoices whose due_date is in the past and that are not
        fully paid (outstanding balance > 0).
        Tests pur_org_dt_status_date_idx + allocation join.
        """
        today = date.today()
        qs = (
            PurchaseDocument.supplier_invoices
            .filter(
                organization=org,
                status=PurchaseDocument.Status.CONFIRMED,
                due_date__isnull=False,
                due_date__lt=today,
            )
            .annotate(
                paid_amount=Coalesce(
                    Sum("allocations__amount"), _ZERO, output_field=_DEC
                )
            )
            .filter(paid_amount__lt=F("total"))
            .select_related("supplier")
            .values(
                "id", "supplier_ncf", "due_date", "total",
                "paid_amount", "supplier__name",
            )
            .order_by("due_date")
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
