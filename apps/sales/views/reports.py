import io
from decimal import Decimal

from django.contrib import messages
from django.core.cache import cache
from django.db.models import Case, Count, DecimalField, F, Sum, When
from django.db.models.functions import Coalesce, TruncDay, TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.daterange import (
    DATE_INVALID_MSG,
    DATE_RANGE_ERROR_MSG,
    DateRangeError,
    parse_date_range,
)
from ..models import Customer, SalesDocument, SalesDocumentItem, NCFType, Payment

_AGING_CSS = {
    "current": "text-success",
    "1_30":    "text-warning",
    "31_60":   "text-warning",
    "61_90":   "text-danger",
    "90_plus": "text-danger",
}


_MONTHS_ES = [
    (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
    (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
    (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
]


class ReportIndexView(ERPBaseViewMixin, TemplateView):
    template_name = "sales/reports.html"
    required_module = "sales"
    admin_required = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from datetime import date
        today = timezone.now().date()
        ctx["today"] = today
        ctx["months"] = _MONTHS_ES
        next_month = today.month % 12 + 1
        next_year = today.year + (1 if today.month == 12 else 0)
        ctx["dgii_deadline"] = date(next_year, next_month, 15)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Reportes de Facturación")},
        ]
        return ctx


class Report607View(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    PAYMENT_METHOD_CODE = {
        "CASH": "01",
        "CHECK": "02",
        "CARD": "03",
        "TRANSFER": "04",
        "SWAP": "05",
        "OTHER": "06",
        "CREDIT": "07",
    }

    def get(self, request):
        month = request.GET.get("month")
        year = request.GET.get("year")
        if not (month and year):
            messages.error(request, _("Debe seleccionar mes y año."))
            return redirect("sales:reports")

        try:
            month, year = int(month), int(year)
        except (ValueError, TypeError):
            messages.error(request, _("Mes y año inválidos."))
            return redirect("sales:reports")

        invoices = (
            SalesDocument.invoices.filter(
                organization=request.organization,
                issue_date__month=month,
                issue_date__year=year,
            )
            .exclude(status=SalesDocument.Status.DRAFT)
            .exclude(status=SalesDocument.Status.CANCELLED)
            .select_related("customer", "encf_modified")
            .prefetch_related("allocations__payment")
            .order_by("issue_date", "encf")
        )

        buf = io.StringIO()
        for inv in invoices:
            c = inv.customer
            id_type_code = {"RNC": "1", "CED": "2"}.get(c.id_type, "")
            buyer_id = c.rnc_cedula or ""
            buyer_type = id_type_code if buyer_id else ""
            encf_mod = inv.encf_modified.encf if inv.encf_modified else ""

            sorted_allocs = sorted(inv.allocations.all(), key=lambda a: a.payment.date, reverse=True)
            last_alloc = sorted_allocs[0] if sorted_allocs else None
            if last_alloc:
                pay_code = self.PAYMENT_METHOD_CODE.get(last_alloc.payment.method, "06")
            else:
                pay_code = "07" if inv.payment_condition == "CREDIT" else "01"

            row = "|".join([
                buyer_id, buyer_type, inv.encf, encf_mod,
                str(inv.ncf_type), inv.issue_date.strftime("%Y%m%d"),
                "", f"{inv.subtotal:.2f}", f"{inv.itbis_total:.2f}", "0.00", pay_code,
            ])
            buf.write(row + "\r\n")

        filename = f"607_{year}{month:02d}_{request.organization.slug}.txt"
        response = HttpResponse(buf.getvalue(), content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class Report608View(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def get(self, request):
        month = request.GET.get("month")
        year = request.GET.get("year")
        if not (month and year):
            messages.error(request, _("Debe seleccionar mes y año."))
            return redirect("sales:reports")

        try:
            month, year = int(month), int(year)
        except (ValueError, TypeError):
            messages.error(request, _("Mes y año inválidos."))
            return redirect("sales:reports")

        cancelled = (
            SalesDocument.invoices.filter(
                organization=request.organization,
                status=SalesDocument.Status.CANCELLED,
                updated_at__month=month,
                updated_at__year=year,
            )
            .exclude(encf="")
            .order_by("updated_at")
        )

        buf = io.StringIO()
        for inv in cancelled:
            row = "|".join([inv.encf, str(inv.ncf_type), inv.updated_at.strftime("%Y%m%d")])
            buf.write(row + "\r\n")

        filename = f"608_{year}{month:02d}_{request.organization.slug}.txt"
        response = HttpResponse(buf.getvalue(), content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ReportAgingView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def get(self, request):
        org = request.organization
        customers = Customer.objects.filter(organization=org).order_by("name")
        customer_id = request.GET.get("customer", "").strip()

        _aging_gen = cache.get(f"aging_gen:{org.pk}", 0)
        _cache_key = f"report_aging:{org.pk}:{_aging_gen}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)

            selected_customer = None
            if customer_id:
                selected_customer = get_object_or_404(Customer, pk=customer_id, organization=org)

            qs = SalesDocument.invoices.filter(
                organization=org,
                status__in=[SalesDocument.Status.CONFIRMED, SalesDocument.Status.SENT, SalesDocument.Status.OVERDUE],
            ).with_signed_totals().with_aging()
            if selected_customer:
                qs = qs.filter(customer=selected_customer)

            invoices = list(
                qs.annotate(paid_amount=Coalesce(Sum("allocations__amount"), _zero, output_field=_dec))
                .select_related("customer")
            )
            for inv in invoices:
                inv.line_balance = inv.signed_total - inv.paid_amount

            customers_map = {}
            for inv in invoices:
                if inv.line_balance <= _zero:
                    continue
                cpk = inv.customer_id
                if cpk not in customers_map:
                    customers_map[cpk] = {
                        "customer": inv.customer,
                        "buckets": {b: _zero for b in SalesDocument.AgingBucket.values},
                        "total": _zero,
                    }
                customers_map[cpk]["buckets"][inv.aging_bucket_db] += inv.line_balance
                customers_map[cpk]["total"] += inv.line_balance

            col_totals = {b: _zero for b in SalesDocument.AgingBucket.values}
            grand_total = _zero
            rows = sorted(customers_map.values(), key=lambda r: r["customer"].name)
            for row in rows:
                row["bucket_cells"] = [
                    {"amount": row["buckets"][b], "css": _AGING_CSS[b]}
                    for b in SalesDocument.AgingBucket.values
                ]
                for b in SalesDocument.AgingBucket.values:
                    col_totals[b] += row["buckets"][b]
                grand_total += row["total"]

            computed = {
                "rows": rows,
                "bucket_headers": [
                    {"label": SalesDocument.AgingBucket(b).label, "css": _AGING_CSS[b]}
                    for b in SalesDocument.AgingBucket.values
                ],
                "col_total_cells": [
                    {"amount": col_totals[b], "css": _AGING_CSS[b]}
                    for b in SalesDocument.AgingBucket.values
                ],
                "grand_total": grand_total,
                "today": timezone.now().date(),
                "selected_customer": selected_customer,
            }
            cache.set(_cache_key, computed, timeout=600)

        return render(
            request, "sales/report_aging.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("sales:reports")},
                        {"label": _("Antigüedad de Cuentas por Cobrar")},
                    ]
                ),
                "customers": customers,
                "customer_id": customer_id,
                **computed,
            },
        )


class ReportStatementView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def get(self, request):
        from datetime import datetime as dt
        org = request.organization
        customers = Customer.objects.filter(organization=org).order_by("name")
        customer_id   = request.GET.get("customer",  "").strip()
        date_from_str = request.GET.get("date_from", "").strip()
        date_to_str   = request.GET.get("date_to",   "").strip()

        _cache_key = f"report_statement:{org.pk}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            customer = None
            lines = []
            opening_balance = closing_balance = _zero
            period_invoiced = period_collected = _zero
            error = None

            if customer_id and date_from_str and date_to_str:
                try:
                    customer = get_object_or_404(Customer, pk=customer_id, organization=org)
                    d_from, d_to = parse_date_range(date_from_str, date_to_str)

                    inv_before = (
                        SalesDocument.invoices.filter(
                            organization=org, customer=customer, issue_date__lt=d_from,
                        )
                        .exclude(status__in=[SalesDocument.Status.DRAFT, SalesDocument.Status.CANCELLED])
                        .with_signed_totals()
                        .aggregate(t=Coalesce(Sum("signed_total"), _zero, output_field=_dec))["t"]
                    )
                    pmt_before = Payment.objects.filter(
                        organization=org, customer=customer, date__lt=d_from,
                    ).aggregate(t=Coalesce(Sum("amount"), _zero, output_field=_dec))["t"]
                    opening_balance = inv_before - pmt_before

                    for inv in (
                        SalesDocument.invoices.filter(
                            organization=org, customer=customer,
                            issue_date__gte=d_from, issue_date__lte=d_to,
                        )
                        .exclude(status__in=[SalesDocument.Status.DRAFT, SalesDocument.Status.CANCELLED])
                        .with_signed_totals()
                        .order_by("issue_date", "created_at")
                    ):
                        lines.append({
                            "date": inv.issue_date, "type": "invoice",
                            "ref":  inv.display_number,
                            "url":  reverse("sales:invoice_detail", args=[inv.pk]),
                            "debit": inv.signed_total, "credit": _zero,
                        })
                        period_invoiced += inv.signed_total

                    for pmt in Payment.objects.filter(
                        organization=org, customer=customer,
                        date__gte=d_from, date__lte=d_to,
                    ).order_by("date", "created_at"):
                        lines.append({
                            "date": pmt.date, "type": "payment",
                            "ref":  f"PAG-{pmt.pk.hex[:8].upper()}",
                            "url":  reverse("sales:payment_detail", args=[pmt.pk]),
                            "debit": _zero, "credit": pmt.amount,
                        })
                        period_collected += pmt.amount

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
                "customer": customer, "customer_id": customer_id,
                "date_from": date_from_str, "date_to": date_to_str, "lines": lines,
                "opening_balance": opening_balance, "closing_balance": closing_balance,
                "period_invoiced": period_invoiced, "period_collected": period_collected,
                "error": error,
            }
            if customer and not error:
                cache.set(_cache_key, computed, timeout=600)

        return render(
            request, "sales/report_statement.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("sales:reports")},
                        {"label": _("Estado de Cuenta")},
                    ]
                ),
                "customers": customers,
                **computed,
            },
        )


class ReportSalesByPeriodView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def get(self, request):
        org = request.organization
        year_str  = request.GET.get("year",  "").strip()
        month_str = request.GET.get("month", "").strip()

        _cache_key = f"report_sales_period:{org.pk}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            year = month = None
            rows = []
            totals = {"invoiced": _zero, "collected": _zero, "net": _zero}
            by_day = False

            if year_str:
                try:
                    year = int(year_str)
                    if month_str:
                        month = int(month_str)

                    if month:
                        by_day = True
                        inv_qs = (
                            SalesDocument.invoices.filter(
                                organization=org,
                                issue_date__year=year, issue_date__month=month,
                            )
                            .exclude(status__in=[SalesDocument.Status.DRAFT, SalesDocument.Status.CANCELLED])
                            .with_signed_totals()
                            .annotate(period=TruncDay("issue_date"))
                            .values("period")
                            .annotate(total=Coalesce(Sum("signed_total"), _zero, output_field=_dec))
                        )
                        pmt_qs = (
                            Payment.objects.filter(
                                organization=org,
                                date__year=year, date__month=month,
                            )
                            .annotate(period=TruncDay("date"))
                            .values("period")
                            .annotate(total=Coalesce(Sum("amount"), _zero, output_field=_dec))
                        )
                    else:
                        inv_qs = (
                            SalesDocument.invoices.filter(
                                organization=org, issue_date__year=year,
                            )
                            .exclude(status__in=[SalesDocument.Status.DRAFT, SalesDocument.Status.CANCELLED])
                            .with_signed_totals()
                            .annotate(period=TruncMonth("issue_date"))
                            .values("period")
                            .annotate(total=Coalesce(Sum("signed_total"), _zero, output_field=_dec))
                        )
                        pmt_qs = (
                            Payment.objects.filter(
                                organization=org, date__year=year,
                            )
                            .annotate(period=TruncMonth("date"))
                            .values("period")
                            .annotate(total=Coalesce(Sum("amount"), _zero, output_field=_dec))
                        )

                    inv_by_period = {r["period"]: r["total"] for r in inv_qs}
                    pmt_by_period = {r["period"]: r["total"] for r in pmt_qs}

                    for period_dt in sorted(set(inv_by_period) | set(pmt_by_period)):
                        invoiced  = inv_by_period.get(period_dt, _zero)
                        collected = pmt_by_period.get(period_dt, _zero)
                        net       = invoiced - collected
                        rows.append({"period": period_dt, "invoiced": invoiced, "collected": collected, "net": net})
                        totals["invoiced"]  += invoiced
                        totals["collected"] += collected
                        totals["net"]       += net

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
            request, "sales/report_sales_period.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("sales:reports")},
                        {"label": _("Ventas por Período")},
                    ]
                ),
                **computed,
            },
        )


class ReportInvoicesByCustomerView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def get(self, request):
        from datetime import datetime as dt
        org = request.organization
        customers = Customer.objects.filter(organization=org).order_by("name")
        customer_ids  = [c.strip() for c in request.GET.getlist("customer") if c.strip()]
        doc_type_ids  = [d.strip() for d in request.GET.getlist("doc_type") if d.strip()]
        date_from_str = request.GET.get("date_from", "").strip()
        date_to_str   = request.GET.get("date_to",   "").strip()

        valid_doc_types = {c[0] for c in SalesDocument.DocType.choices}
        doc_type_ids = [d for d in doc_type_ids if d in valid_doc_types]

        _cache_key = f"report_inv_by_customer:{org.pk}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            selected_customers = []
            invoices = []
            totals = {"subtotal": _zero, "itbis_18": _zero, "total": _zero}
            error = None
            ran = False

            if date_from_str and date_to_str:
                ran = True
                try:
                    d_from, d_to = parse_date_range(date_from_str, date_to_str)

                    if customer_ids:
                        selected_customers = list(
                            Customer.objects.filter(pk__in=customer_ids, organization=org).order_by("name")
                        )

                    docs_qs = SalesDocument.objects.filter(
                        organization=org,
                        issue_date__gte=d_from,
                        issue_date__lte=d_to,
                    )
                    if customer_ids:
                        docs_qs = docs_qs.filter(customer__in=selected_customers)
                    if doc_type_ids:
                        docs_qs = docs_qs.filter(doc_type__in=doc_type_ids)
                    invoices = list(
                        docs_qs
                        .exclude(status__in=[SalesDocument.Status.DRAFT, SalesDocument.Status.CANCELLED])
                        .select_related("customer")
                        .with_signed_totals()
                        .order_by("customer__name", "issue_date", "created_at")
                    )

                    for inv in invoices:
                        totals["subtotal"] += inv.signed_subtotal
                        totals["itbis_18"] += inv.signed_itbis_18
                        totals["total"]    += inv.signed_total

                except DateRangeError:
                    error = DATE_RANGE_ERROR_MSG
                except (ValueError, TypeError):
                    error = DATE_INVALID_MSG

            customer = selected_customers[0] if len(selected_customers) == 1 else None
            computed = {
                "selected_customers": selected_customers,
                "customer": customer,
                "multi_customer": customer is None,
                "ran": ran,
                "customer_ids": customer_ids,
                "doc_type_ids": doc_type_ids,
                "date_from": date_from_str, "date_to": date_to_str,
                "invoices": invoices, "totals": totals, "error": error,
                "today": timezone.now().date(),
            }
            if ran and not error:
                cache.set(_cache_key, computed, timeout=600)

        return render(
            request, "sales/report_salesdoc_by_customer.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("sales:reports")},
                        {"label": _("Facturas por Cliente")},
                    ]
                ),
                "customers": customers,
                "doc_types": SalesDocument.DocType.choices,
                **computed,
            },
        )


class ReportCollectionsView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def get(self, request):
        from datetime import datetime as dt
        org = request.organization
        date_from_str = request.GET.get("date_from", "").strip()
        date_to_str   = request.GET.get("date_to",   "").strip()

        _cache_key = f"report_collections:{org.pk}:{request.GET.urlencode()}"
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

                    payments = list(
                        Payment.objects.filter(
                            organization=org, date__gte=d_from, date__lte=d_to,
                        )
                        .select_related("customer")
                        .order_by("date", "customer__name")
                    )

                    method_labels = dict(Payment.Method.choices)
                    by_method = [
                        {**r, "method_display": method_labels.get(r["method"], r["method"])}
                        for r in Payment.objects.filter(
                            organization=org, date__gte=d_from, date__lte=d_to,
                        )
                        .values("method")
                        .annotate(count=Count("id"), total=Coalesce(Sum("amount"), _zero, output_field=_dec))
                        .order_by("method")
                    ]

                    grand_total = sum(p.amount for p in payments)

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
            request, "sales/report_collections.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("sales:reports")},
                        {"label": _("Cobros del Período")},
                    ]
                ),
                **computed,
            },
        )


class ReportITBISView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def get(self, request):
        org = request.organization
        year_str  = request.GET.get("year",  "").strip()
        month_str = request.GET.get("month", "").strip()

        _cache_key = f"report_itbis:{org.pk}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            year = month = None
            rows = []
            totals = {k: _zero for k in ("exempt", "base_16", "itbis_16", "base_18", "itbis_18", "total_base", "total_itbis", "grand_total")}
            by_day = False

            if year_str:
                try:
                    year = int(year_str)
                    if month_str:
                        month = int(month_str)
                        by_day = True

                    qs = (
                        SalesDocumentItem.objects.filter(
                            document__organization=org,
                            document__doc_type=SalesDocument.DocType.INVOICE,
                            document__deleted_at__isnull=True,
                            document__issue_date__year=year,
                        )
                        .exclude(document__status__in=[SalesDocument.Status.DRAFT, SalesDocument.Status.CANCELLED])
                    )
                    if month:
                        qs = qs.filter(document__issue_date__month=month)

                    trunc = TruncDay("document__issue_date") if by_day else TruncMonth("document__issue_date")

                    raw = (
                        qs.annotate(
                            period=trunc,
                            signed_line_total=Case(
                                When(document__ncf_type__in=SalesDocument.CREDIT_NOTE_TYPES, then=-F("line_total")),
                                default=F("line_total"),
                                output_field=_dec,
                            ),
                            signed_tax=Case(
                                When(document__ncf_type__in=SalesDocument.CREDIT_NOTE_TYPES, then=-F("itbis_amount")),
                                default=F("itbis_amount"),
                                output_field=_dec,
                            ),
                        )
                        .values("period", "itbis_rate")
                        .annotate(
                            base=Coalesce(Sum("signed_line_total"), _zero, output_field=_dec),
                            tax= Coalesce(Sum("signed_tax"), _zero, output_field=_dec),
                        )
                        .order_by("period", "itbis_rate")
                    )

                    period_map = {}
                    for r in raw:
                        p = r["period"]
                        if p not in period_map:
                            period_map[p] = {"period": p, "exempt": _zero,
                                             "base_16": _zero, "itbis_16": _zero,
                                             "base_18": _zero, "itbis_18": _zero}
                        rate = r["itbis_rate"]
                        if rate == SalesDocumentItem.ITBISRate.EXEMPT:
                            period_map[p]["exempt"] += r["base"]
                        elif rate == SalesDocumentItem.ITBISRate.RATE_16:
                            period_map[p]["base_16"]  += r["base"]
                            period_map[p]["itbis_16"] += r["tax"]
                        elif rate == SalesDocumentItem.ITBISRate.RATE_18:
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
            request, "sales/report_itbis.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("sales:reports")},
                        {"label": _("Resumen de ITBIS")},
                    ]
                ),
                **computed,
            },
        )


class ReportSalesByNCFTypeView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def get(self, request):
        org = request.organization
        month_str = request.GET.get("month", "").strip()
        year_str  = request.GET.get("year",  "").strip()

        _cache_key = f"report_ncf_type:{org.pk}:{request.GET.urlencode()}"
        computed = cache.get(_cache_key)

        if computed is None:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            month = year = None
            rows = []
            totals = {k: _zero for k in ("subtotal", "itbis", "total")}
            total_count = 0

            if month_str and year_str:
                try:
                    month = int(month_str)
                    year  = int(year_str)

                    ncf_labels = dict(NCFType.choices)
                    raw = (
                        SalesDocument.invoices.filter(
                            organization=org,
                            issue_date__year=year,
                            issue_date__month=month,
                        )
                        .exclude(status__in=[SalesDocument.Status.DRAFT, SalesDocument.Status.CANCELLED])
                        .with_signed_totals()
                        .values("ncf_type")
                        .annotate(
                            count=Count("id"),
                            subtotal=Coalesce(Sum("signed_subtotal"), _zero, output_field=_dec),
                            itbis_18=Coalesce(Sum("signed_itbis_18"), _zero, output_field=_dec),
                            itbis_16=Coalesce(Sum("signed_itbis_16"), _zero, output_field=_dec),
                            total=Coalesce(Sum("signed_total"), _zero, output_field=_dec),
                        )
                        .order_by("ncf_type")
                    )

                    for r in raw:
                        itbis = r["itbis_18"] + r["itbis_16"]
                        rows.append({
                            "ncf_type":    r["ncf_type"],
                            "ncf_label":   ncf_labels.get(r["ncf_type"], str(r["ncf_type"])),
                            "count":       r["count"],
                            "subtotal":    r["subtotal"],
                            "itbis":       itbis,
                            "total":       r["total"],
                        })
                        totals["subtotal"] += r["subtotal"]
                        totals["itbis"]    += itbis
                        totals["total"]    += r["total"]
                        total_count        += r["count"]

                except (ValueError, TypeError):
                    month = year = None

            computed = {
                "month": month, "year": year,
                "month_input": month_str, "year_input": year_str,
                "rows": rows, "totals": totals, "total_count": total_count,
                "today": timezone.now().date(),
            }
            if month and year:
                cache.set(_cache_key, computed, timeout=600)

        return render(
            request, "sales/report_ncf_type.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("sales:reports")},
                        {"label": _("Ventas por Tipo de Comprobante")},
                    ]
                ),
                **computed,
            },
        )
