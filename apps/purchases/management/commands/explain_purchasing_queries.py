"""
Management command: explain_purchasing_queries
==============================================
Runs EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) against every hot purchasing query
and prints a human-readable summary: execution time, node type, row count, and
the single worst plan node (highest Actual Total Time).

Usage:
    python manage.py explain_purchasing_queries --org <slug>
    python manage.py explain_purchasing_queries --org <slug> --raw   # dump full JSON

Queries covered:
  Q1  Supplier invoice list (CONFIRMED/PAID) with totals        [from perf_test]
  Q2  Purchase orders — last 90 days                             [from perf_test]
  Q3  Spend by supplier — top 20 by total billed                [from perf_test]
  Q4  Payment coverage annotation (paid/partial/unpaid)          [from perf_test]
  Q5  Overdue bills (past due_date, not fully paid)              [from perf_test]
  Q6  AP Aging — confirmed invoices bucketed by days overdue
  Q7  Supplier statement — opening balance + period lines
  Q8  Spend by period — monthly roll-up for a year
  Q9  ITBIS credit report — line-item aggregation by period
  Q10 Supplier list — active suppliers for an org
"""
import json
import textwrap
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import (
    Case, Count, DecimalField, F, Q, Sum, Value, When,
)
from django.db.models.functions import Coalesce, TruncMonth

from apps.accounts.models import Organization
from apps.purchases.models import (
    PurchaseDocument, PurchaseDocumentItem, Supplier, SupplierPayment,
)

_ZERO = Value(0, output_field=DecimalField(max_digits=14, decimal_places=2))
_DEC  = DecimalField(max_digits=14, decimal_places=2)


def _explain(qs, raw: bool = False):
    """
    Run EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) against *qs* and return a
    dict with keys: execution_ms, node_type, actual_rows, plan (full JSON),
    worst_node (dict with node_type, actual_total_time, relation_name).
    """
    sql, params = qs.query.sql_with_params()
    explain_sql = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql
    with connection.cursor() as cur:
        cur.execute(explain_sql, params)
        plan_json = cur.fetchone()[0]  # list[dict] from psycopg

    plan = plan_json[0] if isinstance(plan_json, list) else plan_json
    root = plan["Plan"]
    execution_ms = plan.get("Execution Time", plan.get("Total Runtime", 0.0))

    worst = _find_worst_node(root, None)

    return {
        "execution_ms": execution_ms,
        "node_type": root.get("Node Type", "?"),
        "actual_rows": root.get("Actual Rows", 0),
        "plan": plan,
        "worst_node": worst,
    }


def _find_worst_node(node: dict, current_worst: dict | None) -> dict | None:
    """Recursively find the plan node with the highest Actual Total Time."""
    node_time = node.get("Actual Total Time", 0.0)
    if current_worst is None or node_time > current_worst.get("Actual Total Time", 0.0):
        current_worst = {
            "Node Type": node.get("Node Type", "?"),
            "Actual Total Time": node_time,
            "Relation Name": node.get("Relation Name", ""),
            "Index Name": node.get("Index Name", ""),
        }
    for child in node.get("Plans", []):
        current_worst = _find_worst_node(child, current_worst)
    return current_worst


class Command(BaseCommand):
    help = "Run EXPLAIN ANALYZE on all hot purchasing queries and summarise results."

    def add_arguments(self, parser):
        parser.add_argument("--org", required=True, help="Organization slug.")
        parser.add_argument(
            "--raw", action="store_true",
            help="Also dump the full EXPLAIN JSON for each query.",
        )
        parser.add_argument(
            "--year", type=int, default=None,
            help="Year for period-based reports (defaults to current year).",
        )

    def handle(self, *args, **options):
        slug  = options["org"]
        raw   = options["raw"]
        year  = options["year"] or date.today().year

        try:
            org = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization '{slug}' not found.")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\nEXPLAIN ANALYZE — org: {org.name}  (year={year})\n"
                "  Each entry shows: execution time · root node type · "
                "row estimate · worst node\n"
            )
        )

        queries = [
            ("Q1  Invoice list (CONFIRMED/PAID)",    lambda: self._q1(org)),
            ("Q2  Purchase orders — last 90 days",   lambda: self._q2(org)),
            ("Q3  Spend by supplier (top 20)",        lambda: self._q3(org)),
            ("Q4  Payment coverage annotation",       lambda: self._q4(org)),
            ("Q5  Overdue bills (past due, unpaid)",  lambda: self._q5(org)),
            ("Q6  AP Aging (grouped by supplier)",    lambda: self._q6(org)),
            ("Q7  Spend by period (monthly, year)",   lambda: self._q7(org, year)),
            ("Q8  ITBIS credits by period (monthly)", lambda: self._q8(org, year)),
            ("Q9  Supplier list (active)",            lambda: self._q9(org)),
            ("Q10 Outstanding invoices for payment",  lambda: self._q10(org)),
        ]

        divider = "  " + "─" * 100
        self.stdout.write(divider)

        for label, fn in queries:
            qs = fn()
            try:
                result = _explain(qs, raw)
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(f"  {label:<45}  ERROR: {exc}")
                )
                continue

            ms     = result["execution_ms"]
            ntype  = result["node_type"]
            rows   = result["actual_rows"]
            worst  = result["worst_node"] or {}

            worst_str = (
                f"{worst.get('Node Type','?')} "
                f"({worst.get('Actual Total Time', 0):.2f} ms"
                + (f" on {worst.get('Relation Name','')}" if worst.get("Relation Name") else "")
                + (f" idx={worst.get('Index Name','')}" if worst.get("Index Name") else "")
                + ")"
            )

            color = self.style.SUCCESS if ms < 50 else (
                self.style.WARNING if ms < 200 else self.style.ERROR
            )
            line = (
                f"  {label:<45}"
                f"  {ms:>8.2f} ms"
                f"  root={ntype:<25}"
                f"  rows={rows:<8}"
                f"  worst={worst_str}"
            )
            self.stdout.write(color(line))

            if raw:
                self.stdout.write(
                    textwrap.indent(
                        json.dumps(result["plan"], indent=2, ensure_ascii=False),
                        "      ",
                    )
                )

        self.stdout.write(divider)
        self.stdout.write(
            "\n  ✓ Tip: times < 50 ms are green · 50–200 ms yellow · > 200 ms red.\n"
            "  Run with --raw to dump full EXPLAIN JSON for any suspect query.\n"
        )

    # ── Query builders ────────────────────────────────────────────────────────

    def _q1(self, org):
        """Supplier invoice list — all CONFIRMED/PAID with totals."""
        statuses = [PurchaseDocument.Status.CONFIRMED, PurchaseDocument.Status.PAID]
        return (
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

    def _q2(self, org):
        """Purchase orders issued in the last 90 days."""
        cutoff = date.today() - timedelta(days=90)
        return (
            PurchaseDocument.purchase_orders
            .filter(organization=org, issue_date__gte=cutoff)
            .select_related("supplier")
            .values(
                "id", "number", "status", "issue_date", "expected_date",
                "supplier__name", "total",
            )
            .order_by("-issue_date")
        )

    def _q3(self, org):
        """Top-20 suppliers by spend (SQL GROUP BY + ORDER BY + LIMIT)."""
        statuses = [PurchaseDocument.Status.CONFIRMED, PurchaseDocument.Status.PAID]
        return (
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

    def _q4(self, org):
        """Payment coverage — annotate invoices with paid_amount + status label."""
        statuses = [PurchaseDocument.Status.CONFIRMED, PurchaseDocument.Status.PAID]
        return (
            PurchaseDocument.supplier_invoices
            .filter(organization=org, status__in=statuses)
            .annotate(
                paid_amount=Coalesce(Sum("allocations__amount"), _ZERO, output_field=_DEC)
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

    def _q5(self, org):
        """Overdue bills — confirmed, past due_date, not fully paid."""
        today = date.today()
        return (
            PurchaseDocument.supplier_invoices
            .filter(
                organization=org,
                status=PurchaseDocument.Status.CONFIRMED,
                due_date__isnull=False,
                due_date__lt=today,
            )
            .annotate(
                paid_amount=Coalesce(Sum("allocations__amount"), _ZERO, output_field=_DEC)
            )
            .filter(paid_amount__lt=F("total"))
            .select_related("supplier")
            .values(
                "id", "supplier_ncf", "due_date", "total",
                "paid_amount", "supplier__name",
            )
            .order_by("due_date")
        )

    def _q6(self, org):
        """
        AP Aging SQL version — group by supplier, annotate bucket totals using
        CASE WHEN on days overdue.  This is the *correct* version that avoids
        loading all rows into Python.
        """
        today = date.today()
        return (
            PurchaseDocument.supplier_invoices
            .filter(
                organization=org,
                status=PurchaseDocument.Status.CONFIRMED,
                due_date__isnull=False,
            )
            .values("supplier_id", "supplier__name")
            .annotate(
                current=Coalesce(
                    Sum("total", filter=Q(due_date__gte=today)), _ZERO, output_field=_DEC
                ),
                bucket_1_30=Coalesce(
                    Sum("total", filter=Q(
                        due_date__lt=today,
                        due_date__gte=today - timedelta(days=30),
                    )), _ZERO, output_field=_DEC
                ),
                bucket_31_60=Coalesce(
                    Sum("total", filter=Q(
                        due_date__lt=today - timedelta(days=30),
                        due_date__gte=today - timedelta(days=60),
                    )), _ZERO, output_field=_DEC
                ),
                bucket_61_90=Coalesce(
                    Sum("total", filter=Q(
                        due_date__lt=today - timedelta(days=60),
                        due_date__gte=today - timedelta(days=90),
                    )), _ZERO, output_field=_DEC
                ),
                bucket_90_plus=Coalesce(
                    Sum("total", filter=Q(due_date__lt=today - timedelta(days=90))),
                    _ZERO, output_field=_DEC
                ),
                grand_total=Coalesce(Sum("total"), _ZERO, output_field=_DEC),
            )
            .order_by("supplier__name")
        )

    def _q7(self, org, year: int):
        """Spend by period — monthly roll-up for a calendar year."""
        return (
            PurchaseDocument.supplier_invoices
            .filter(organization=org, issue_date__year=year)
            .exclude(status__in=[
                PurchaseDocument.Status.DRAFT, PurchaseDocument.Status.CANCELLED
            ])
            .annotate(period=TruncMonth("issue_date"))
            .values("period")
            .annotate(total=Coalesce(Sum("total"), _ZERO, output_field=_DEC))
            .order_by("period")
        )

    def _q8(self, org, year: int):
        """ITBIS credits — line-item aggregation by period and rate."""
        return (
            PurchaseDocumentItem.objects
            .filter(
                purchase_document__organization=org,
                purchase_document__doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
                purchase_document__deleted_at__isnull=True,
                purchase_document__issue_date__year=year,
                purchase_document__status__in=[
                    PurchaseDocument.Status.CONFIRMED,
                    PurchaseDocument.Status.PAID,
                ],
            )
            .annotate(period=TruncMonth("purchase_document__issue_date"))
            .values("period", "itbis_rate")
            .annotate(
                base=Coalesce(Sum("line_total"), _ZERO, output_field=_DEC),
                tax=Coalesce(Sum("itbis_amount"), _ZERO, output_field=_DEC),
            )
            .order_by("period", "itbis_rate")
        )

    def _q9(self, org):
        """Active supplier list for an org."""
        return (
            Supplier.objects
            .filter(organization=org, is_active=True)
            .values("id", "name", "rnc_cedula", "email", "phone")
            .order_by("name")
        )

    def _q10(self, org):
        """Outstanding invoices — annotated with paid_amount for payment form."""
        return (
            PurchaseDocument.supplier_invoices
            .filter(
                organization=org,
                status__in=[
                    PurchaseDocument.Status.CONFIRMED,
                    PurchaseDocument.Status.PAID,
                ],
            )
            .annotate(
                paid_amount=Coalesce(Sum("allocations__amount"), _ZERO, output_field=_DEC)
            )
            .order_by("due_date", "issue_date")
            .values("id", "supplier_ncf", "issue_date", "due_date", "total", "paid_amount")
        )
