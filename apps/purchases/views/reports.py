import csv
from datetime import date, datetime as dt, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDay, TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import RedirectView, TemplateView

from apps.accounts.views import ERPBaseViewMixin


def _report_gen(org):
    """Per-org generation value bumped by apps/purchases/signals.py on every
    PurchaseDocument / SupplierPayment / item mutation. Embedding it in cache
    keys makes stale report entries unreachable immediately."""
    return cache.get(f"purchases_report_gen:{org.pk}", 0)
from apps.core.daterange import (
    DATE_INVALID_MSG,
    DATE_RANGE_ERROR_MSG,
    DateRangeError,
    parse_date_range,
)
from ..models import PurchaseDocument, PurchaseDocumentItem, Supplier, SupplierPayment

_MONTHS_ES = [
    (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
    (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
    (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
]

_BUCKETS = ["current", "1_30", "31_60", "61_90", "90_plus"]
_BUCKET_LABELS = {
    "current": "Corriente",
    "1_30": "1-30 dias",
    "31_60": "31-60 dias",
    "61_90": "61-90 dias",
    "90_plus": "+90 dias",
}
_AGING_CSS = {
    "current": "text-success",
    "1_30": "text-warning",
    "31_60": "text-warning",
    "61_90": "text-danger",
    "90_plus": "text-danger",
}


def _bucket_for(days_overdue):
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "1_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    return "90_plus"


class ReportPurchasesIndexView(RedirectView):
    permanent = False
    pattern_name = "core:reports"


class Report606View(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def get(self, request):
        org = request.organization
        today = timezone.now().date()
        month_str = request.GET.get("month", "")
        year_str = request.GET.get("year", "")

        try:
            month_int = int(month_str) if month_str else today.month
            year_int = int(year_str) if year_str else today.year
        except ValueError:
            month_int = today.month
            year_int = today.year

        qs = PurchaseDocument.supplier_invoices.filter(
            organization=org,
            status__in=[PurchaseDocument.Status.CONFIRMED, PurchaseDocument.Status.PAID],
            issue_date__month=month_int,
            issue_date__year=year_int,
        ).select_related("supplier").order_by("issue_date", "supplier_ncf")

        if request.GET.get("format") == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = (
                f'attachment; filename="606-{year_int:04d}-{month_int:02d}.csv"'
            )
            writer = csv.writer(response)
            writer.writerow([
                "RNC Proveedor", "NCF", "Tipo NCF", "Fecha",
                "Subtotal", "ITBIS 18%", "ITBIS 16%", "Total",
            ])
            for inv in qs:
                writer.writerow([
                    inv.supplier_rnc, inv.supplier_ncf, inv.supplier_ncf_type,
                    inv.issue_date.strftime("%Y-%m-%d"),
                    inv.subtotal, inv.itbis_18, inv.itbis_16, inv.total,
                ])
            return response

        _cache_key = f"report_606:{org.pk}:{_report_gen(org)}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            next_month = today.month % 12 + 1
            next_year = today.year + (1 if today.month == 12 else 0)
            dgii_deadline = date(next_year, next_month, 15)

            _DEC = DecimalField(max_digits=14, decimal_places=2)
            _zero = Decimal("0.00")
            agg = qs.aggregate(
                total_subtotal=Coalesce(Sum("subtotal"), Value(0, output_field=_DEC), output_field=_DEC),
                total_itbis_18=Coalesce(Sum("itbis_18"), Value(0, output_field=_DEC), output_field=_DEC),
                total_itbis_16=Coalesce(Sum("itbis_16"), Value(0, output_field=_DEC), output_field=_DEC),
                total_total=Coalesce(Sum("total"), Value(0, output_field=_DEC), output_field=_DEC),
            )
            invoices = list(qs)

            computed = {
                "invoices": invoices,
                "month": month_int,
                "year": year_int,
                "months": _MONTHS_ES,
                "today": today,
                "dgii_deadline": dgii_deadline,
                "total_subtotal": agg["total_subtotal"],
                "total_itbis": agg["total_itbis_18"] + agg["total_itbis_16"],
                "total_total": agg["total_total"],
            }
            cache.set(_cache_key, computed, timeout=600)

        return render(
            request,
            "purchases/report_606.html",
            {
                **self.get_context(
                    module="supplier-invoice",
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("purchases:reports")},
                        {"label": _("Reporte 606")},
                    ],
                ),
                **computed,
            },
        )


class ReportAPAgingView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def get(self, request):
        org = request.organization
        _cache_key = f"report_ap_aging:{org.pk}:{_report_gen(org)}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            _DEC = DecimalField(max_digits=14, decimal_places=2)
            today = timezone.now().date()

            raw_rows = list(
                PurchaseDocument.supplier_invoices
                .filter(
                    organization=org,
                    status=PurchaseDocument.Status.CONFIRMED,
                    due_date__isnull=False,
                )
                .values("supplier_id", "supplier__name")
                .annotate(
                    bucket_current=Coalesce(
                        Sum("total", filter=Q(due_date__gte=today)),
                        Value(0, output_field=_DEC), output_field=_DEC,
                    ),
                    bucket_1_30=Coalesce(
                        Sum("total", filter=Q(
                            due_date__lt=today,
                            due_date__gte=today - timedelta(days=30),
                        )),
                        Value(0, output_field=_DEC), output_field=_DEC,
                    ),
                    bucket_31_60=Coalesce(
                        Sum("total", filter=Q(
                            due_date__lt=today - timedelta(days=30),
                            due_date__gte=today - timedelta(days=60),
                        )),
                        Value(0, output_field=_DEC), output_field=_DEC,
                    ),
                    bucket_61_90=Coalesce(
                        Sum("total", filter=Q(
                            due_date__lt=today - timedelta(days=60),
                            due_date__gte=today - timedelta(days=90),
                        )),
                        Value(0, output_field=_DEC), output_field=_DEC,
                    ),
                    bucket_90_plus=Coalesce(
                        Sum("total", filter=Q(due_date__lt=today - timedelta(days=90))),
                        Value(0, output_field=_DEC), output_field=_DEC,
                    ),
                    row_total=Coalesce(
                        Sum("total"), Value(0, output_field=_DEC), output_field=_DEC,
                    ),
                )
                .order_by("supplier__name")
            )

            _BUCKET_KEYS = ["current", "1_30", "31_60", "61_90", "90_plus"]
            _BUCKET_DB = [
                "bucket_current", "bucket_1_30", "bucket_31_60",
                "bucket_61_90", "bucket_90_plus",
            ]

            col_totals = {b: _zero for b in _BUCKET_KEYS}
            grand_total = _zero
            rows = []
            for r in raw_rows:
                bucket_cells = []
                for bkey, dbkey in zip(_BUCKET_KEYS, _BUCKET_DB):
                    amt = r[dbkey]
                    bucket_cells.append({"amount": amt, "css": _AGING_CSS[bkey]})
                    col_totals[bkey] += amt
                grand_total += r["row_total"]
                rows.append({
                    "supplier_name": r["supplier__name"],
                    "supplier_id":   r["supplier_id"],
                    "bucket_cells":  bucket_cells,
                    "total":         r["row_total"],
                })

            computed = {
                "rows": rows,
                "bucket_headers": [
                    {"label": _BUCKET_LABELS[b], "css": _AGING_CSS[b]}
                    for b in _BUCKET_KEYS
                ],
                "col_total_cells": [
                    {"amount": col_totals[b], "css": _AGING_CSS[b]}
                    for b in _BUCKET_KEYS
                ],
                "grand_total": grand_total,
                "today": today,
            }
            cache.set(_cache_key, computed, timeout=600)

        return render(
            request, "purchases/reports/report_aging.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("purchases:reports")},
                        {"label": _("Antiguedad de Cuentas por Pagar")},
                    ]
                ),
                **computed,
            },
        )


class ReportSupplierStatementView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def get(self, request):
        org = request.organization
        suppliers = Supplier.objects.filter(organization=org, is_active=True).order_by("name")
        supplier_id   = request.GET.get("supplier",  "").strip()
        date_from_str = request.GET.get("date_from", "").strip()
        date_to_str   = request.GET.get("date_to",   "").strip()

        _cache_key = f"report_supplier_statement:{org.pk}:{_report_gen(org)}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            supplier = None
            lines = []
            opening_balance = closing_balance = _zero
            period_invoiced = period_paid = _zero
            error = None

            if supplier_id and date_from_str and date_to_str:
                try:
                    supplier = get_object_or_404(Supplier, pk=supplier_id, organization=org)
                    d_from, d_to = parse_date_range(date_from_str, date_to_str)

                    inv_before = (
                        PurchaseDocument.supplier_invoices.filter(
                            organization=org, supplier=supplier, issue_date__lt=d_from,
                        )
                        .exclude(status__in=[PurchaseDocument.Status.DRAFT, PurchaseDocument.Status.CANCELLED])
                        .aggregate(t=Coalesce(Sum("total"), _zero, output_field=_dec))["t"]
                    )
                    pmt_before = SupplierPayment.objects.filter(
                        organization=org, supplier=supplier, date__lt=d_from,
                    ).aggregate(t=Coalesce(Sum("amount"), _zero, output_field=_dec))["t"]
                    opening_balance = inv_before - pmt_before

                    for inv in (
                        PurchaseDocument.supplier_invoices.filter(
                            organization=org, supplier=supplier,
                            issue_date__gte=d_from, issue_date__lte=d_to,
                        )
                        .exclude(status__in=[PurchaseDocument.Status.DRAFT, PurchaseDocument.Status.CANCELLED])
                        .order_by("issue_date", "created_at")
                    ):
                        lines.append({
                            "date": inv.issue_date, "type": "invoice",
                            "ref": inv.display_number,
                            "url": reverse("purchases:supplier_invoice_detail", args=[inv.pk]),
                            "debit": inv.total, "credit": _zero,
                        })
                        period_invoiced += inv.total

                    for pmt in SupplierPayment.objects.filter(
                        organization=org, supplier=supplier,
                        date__gte=d_from, date__lte=d_to,
                    ).order_by("date", "created_at"):
                        lines.append({
                            "date": pmt.date, "type": "payment",
                            "ref": f"PAG-{pmt.pk.hex[:8].upper()}",
                            "url": reverse("purchases:supplier_payment_detail", args=[pmt.pk]),
                            "debit": _zero, "credit": pmt.amount,
                        })
                        period_paid += pmt.amount

                    lines.sort(key=lambda x: (x["date"], x["type"]))
                    balance = opening_balance
                    for line in lines:
                        balance += line["debit"] - line["credit"]
                        line["balance"] = balance
                    closing_balance = balance

                except DateRangeError:
                    error = DATE_RANGE_ERROR_MSG
                except (ValueError, TypeError):
                    error = DATE_INVALID_MSG

            computed = {
                "supplier": supplier, "supplier_id": supplier_id,
                "date_from": date_from_str, "date_to": date_to_str, "lines": lines,
                "opening_balance": opening_balance, "closing_balance": closing_balance,
                "period_invoiced": period_invoiced, "period_paid": period_paid,
                "error": error,
            }
            if supplier and not error:
                cache.set(_cache_key, computed, timeout=600)

        return render(
            request, "purchases/reports/report_statement.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("purchases:reports")},
                        {"label": _("Estado de Cuenta de Proveedor")},
                    ]
                ),
                "suppliers": suppliers,
                **computed,
            },
        )


class ReportSpendByPeriodView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def get(self, request):
        org = request.organization
        year_str  = request.GET.get("year",  "").strip()
        month_str = request.GET.get("month", "").strip()

        _cache_key = f"report_spend_period:{org.pk}:{_report_gen(org)}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            year = month = None
            rows = []
            totals = {"invoiced": _zero, "paid": _zero, "net": _zero}
            by_day = False

            if year_str:
                try:
                    year = int(year_str)
                    if month_str:
                        month = int(month_str)

                    if month:
                        by_day = True
                        inv_qs = (
                            PurchaseDocument.supplier_invoices.filter(
                                organization=org,
                                issue_date__year=year, issue_date__month=month,
                            )
                            .exclude(status__in=[PurchaseDocument.Status.DRAFT, PurchaseDocument.Status.CANCELLED])
                            .annotate(period=TruncDay("issue_date"))
                            .values("period")
                            .annotate(total=Coalesce(Sum("total"), _zero, output_field=_dec))
                        )
                        pmt_qs = (
                            SupplierPayment.objects.filter(
                                organization=org,
                                date__year=year, date__month=month,
                            )
                            .annotate(period=TruncDay("date"))
                            .values("period")
                            .annotate(total=Coalesce(Sum("amount"), _zero, output_field=_dec))
                        )
                    else:
                        inv_qs = (
                            PurchaseDocument.supplier_invoices.filter(
                                organization=org, issue_date__year=year,
                            )
                            .exclude(status__in=[PurchaseDocument.Status.DRAFT, PurchaseDocument.Status.CANCELLED])
                            .annotate(period=TruncMonth("issue_date"))
                            .values("period")
                            .annotate(total=Coalesce(Sum("total"), _zero, output_field=_dec))
                        )
                        pmt_qs = (
                            SupplierPayment.objects.filter(
                                organization=org, date__year=year,
                            )
                            .annotate(period=TruncMonth("date"))
                            .values("period")
                            .annotate(total=Coalesce(Sum("amount"), _zero, output_field=_dec))
                        )

                    inv_by_period = {r["period"]: r["total"] for r in inv_qs}
                    pmt_by_period = {r["period"]: r["total"] for r in pmt_qs}

                    for period_dt in sorted(set(inv_by_period) | set(pmt_by_period)):
                        invoiced = inv_by_period.get(period_dt, _zero)
                        paid     = pmt_by_period.get(period_dt, _zero)
                        net      = invoiced - paid
                        rows.append({"period": period_dt, "invoiced": invoiced, "paid": paid, "net": net})
                        totals["invoiced"] += invoiced
                        totals["paid"]     += paid
                        totals["net"]      += net

                except (ValueError, TypeError):
                    year = month = None

            computed = {
                "year": year, "month": month,
                "year_input": year_str, "month_input": month_str,
                "rows": rows, "totals": totals,
                "by_day": by_day, "today": timezone.now().date(),
            }
            if year:
                cache.set(_cache_key, computed, timeout=600)

        return render(
            request, "purchases/reports/report_spend_period.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("purchases:reports")},
                        {"label": _("Compras por Periodo")},
                    ]
                ),
                **computed,
            },
        )


class ReportPurchasesBySupplierView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def get(self, request):
        org = request.organization
        suppliers = Supplier.objects.filter(organization=org, is_active=True).order_by("name")
        supplier_id   = request.GET.get("supplier",  "").strip()
        date_from_str = request.GET.get("date_from", "").strip()
        date_to_str   = request.GET.get("date_to",   "").strip()

        _cache_key = f"report_purchases_by_supplier:{org.pk}:{_report_gen(org)}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            supplier = None
            rows = []
            detail_invoices = []
            totals = {"count": 0, "subtotal": _zero, "itbis": _zero, "total": _zero}
            error = None

            if date_from_str and date_to_str:
                try:
                    d_from, d_to = parse_date_range(date_from_str, date_to_str)

                    base_qs = (
                        PurchaseDocument.supplier_invoices.filter(
                            organization=org,
                            issue_date__gte=d_from, issue_date__lte=d_to,
                        )
                        .exclude(status__in=[PurchaseDocument.Status.DRAFT, PurchaseDocument.Status.CANCELLED])
                    )

                    if supplier_id:
                        supplier = get_object_or_404(Supplier, pk=supplier_id, organization=org)
                        supplier_qs = base_qs.filter(supplier=supplier)
                        agg = supplier_qs.aggregate(
                            count=Count("id"),
                            subtotal=Coalesce(Sum("subtotal"), _zero, output_field=_dec),
                            itbis_18=Coalesce(Sum("itbis_18"), _zero, output_field=_dec),
                            itbis_16=Coalesce(Sum("itbis_16"), _zero, output_field=_dec),
                            total=Coalesce(Sum("total"), _zero, output_field=_dec),
                        )
                        totals["count"]    = agg["count"]
                        totals["subtotal"] = agg["subtotal"]
                        totals["itbis"]    = agg["itbis_18"] + agg["itbis_16"]
                        totals["total"]    = agg["total"]
                        detail_invoices = list(
                            supplier_qs
                            .select_related("supplier")
                            .order_by("issue_date", "created_at")
                        )
                    else:
                        raw = (
                            base_qs.values("supplier__id", "supplier__name")
                            .annotate(
                                count=Count("id"),
                                subtotal=Coalesce(Sum("subtotal"), _zero, output_field=_dec),
                                itbis_18=Coalesce(Sum("itbis_18"), _zero, output_field=_dec),
                                itbis_16=Coalesce(Sum("itbis_16"), _zero, output_field=_dec),
                                total=Coalesce(Sum("total"), _zero, output_field=_dec),
                            )
                            .order_by("supplier__name")
                        )
                        for r in raw:
                            itbis = r["itbis_18"] + r["itbis_16"]
                            rows.append({
                                "supplier_id":   r["supplier__id"],
                                "supplier_name": r["supplier__name"],
                                "count":    r["count"],
                                "subtotal": r["subtotal"],
                                "itbis":    itbis,
                                "total":    r["total"],
                            })
                            totals["count"]    += r["count"]
                            totals["subtotal"] += r["subtotal"]
                            totals["itbis"]    += itbis
                            totals["total"]    += r["total"]

                except DateRangeError:
                    error = DATE_RANGE_ERROR_MSG
                except (ValueError, TypeError):
                    error = DATE_INVALID_MSG

            computed = {
                "supplier": supplier, "supplier_id": supplier_id,
                "date_from": date_from_str, "date_to": date_to_str,
                "rows": rows, "detail_invoices": detail_invoices,
                "totals": totals, "error": error,
                "today": timezone.now().date(),
            }
            if date_from_str and date_to_str and not error:
                cache.set(_cache_key, computed, timeout=600)

        return render(
            request, "purchases/reports/report_by_supplier.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("purchases:reports")},
                        {"label": _("Compras por Proveedor")},
                    ]
                ),
                "suppliers": suppliers,
                **computed,
            },
        )


class ReportSupplierPaymentsView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def get(self, request):
        org = request.organization
        date_from_str = request.GET.get("date_from", "").strip()
        date_to_str   = request.GET.get("date_to",   "").strip()

        _cache_key = f"report_supplier_payments:{org.pk}:{_report_gen(org)}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            payments    = []
            by_method   = []
            grand_total = _zero
            error       = None

            if date_from_str and date_to_str:
                try:
                    d_from, d_to = parse_date_range(date_from_str, date_to_str)

                    pmt_qs = SupplierPayment.objects.filter(
                        organization=org, date__gte=d_from, date__lte=d_to,
                    )
                    payments = list(
                        pmt_qs.select_related("supplier")
                        .order_by("date", "supplier__name")
                    )

                    method_labels = dict(SupplierPayment.Method.choices)
                    by_method = [
                        {**r, "method_display": method_labels.get(r["method"], r["method"])}
                        for r in pmt_qs
                        .values("method")
                        .annotate(
                            count=Count("id"),
                            total=Coalesce(Sum("amount"), _zero, output_field=_dec),
                        )
                        .order_by("method")
                    ]

                    grand_total = pmt_qs.aggregate(
                        t=Coalesce(Sum("amount"), _zero, output_field=_dec)
                    )["t"]

                except DateRangeError:
                    error = DATE_RANGE_ERROR_MSG
                except (ValueError, TypeError):
                    error = DATE_INVALID_MSG

            computed = {
                "date_from": date_from_str, "date_to": date_to_str,
                "payments": payments, "by_method": by_method,
                "grand_total": grand_total, "error": error,
            }
            if date_from_str and date_to_str and not error:
                cache.set(_cache_key, computed, timeout=600)

        return render(
            request, "purchases/reports/report_payments.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("purchases:reports")},
                        {"label": _("Pagos a Proveedores")},
                    ]
                ),
                **computed,
            },
        )


class ReportITBISCreditsView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def get(self, request):
        org = request.organization
        year_str  = request.GET.get("year",  "").strip()
        month_str = request.GET.get("month", "").strip()

        _cache_key = f"report_itbis_credits:{org.pk}:{_report_gen(org)}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            year = month = None
            rows = []
            totals = {k: _zero for k in (
                "exempt", "base_16", "itbis_16", "base_18", "itbis_18",
                "total_base", "total_itbis", "grand_total",
            )}
            by_day = False

            if year_str:
                try:
                    year = int(year_str)
                    if month_str:
                        month = int(month_str)
                        by_day = True

                    qs = PurchaseDocumentItem.objects.filter(
                        purchase_document__organization=org,
                        purchase_document__doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
                        purchase_document__deleted_at__isnull=True,
                        purchase_document__issue_date__year=year,
                        purchase_document__status__in=[
                            PurchaseDocument.Status.CONFIRMED,
                            PurchaseDocument.Status.PAID,
                        ],
                    )
                    if month:
                        qs = qs.filter(purchase_document__issue_date__month=month)

                    trunc = (
                        TruncDay("purchase_document__issue_date") if by_day
                        else TruncMonth("purchase_document__issue_date")
                    )

                    raw = (
                        qs.annotate(period=trunc)
                        .values("period", "itbis_rate")
                        .annotate(
                            base=Coalesce(Sum("line_total"), _zero, output_field=_dec),
                            tax=Coalesce(Sum("itbis_amount"), _zero, output_field=_dec),
                        )
                        .order_by("period", "itbis_rate")
                    )

                    period_map = {}
                    for r in raw:
                        p = r["period"]
                        if p not in period_map:
                            period_map[p] = {
                                "period": p, "exempt": _zero,
                                "base_16": _zero, "itbis_16": _zero,
                                "base_18": _zero, "itbis_18": _zero,
                            }
                        rate = r["itbis_rate"]
                        if rate == PurchaseDocumentItem.ITBISRate.EXEMPT:
                            period_map[p]["exempt"] += r["base"]
                        elif rate == PurchaseDocumentItem.ITBISRate.RATE_16:
                            period_map[p]["base_16"]  += r["base"]
                            period_map[p]["itbis_16"] += r["tax"]
                        elif rate == PurchaseDocumentItem.ITBISRate.RATE_18:
                            period_map[p]["base_18"]  += r["base"]
                            period_map[p]["itbis_18"] += r["tax"]

                    for row in sorted(period_map.values(), key=lambda r: r["period"]):
                        row["total_base"]  = row["exempt"] + row["base_16"] + row["base_18"]
                        row["total_itbis"] = row["itbis_16"] + row["itbis_18"]
                        row["grand_total"] = row["total_base"] + row["total_itbis"]
                        rows.append(row)

                    for row in rows:
                        for k in ("exempt", "base_16", "itbis_16", "base_18", "itbis_18",
                                  "total_base", "total_itbis", "grand_total"):
                            totals[k] += row[k]

                except (ValueError, TypeError):
                    year = month = None

            computed = {
                "year": year, "month": month,
                "year_input": year_str, "month_input": month_str,
                "rows": rows, "totals": totals,
                "by_day": by_day, "today": timezone.now().date(),
            }
            if year:
                cache.set(_cache_key, computed, timeout=600)

        return render(
            request, "purchases/reports/report_itbis.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("purchases:reports")},
                        {"label": _("Credito ITBIS en Compras")},
                    ]
                ),
                **computed,
            },
        )
