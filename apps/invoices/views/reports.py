import io
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, DecimalField, Sum
from django.db.models.functions import Coalesce, TruncDay, TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.views import ERPBaseViewMixin
from ..models import Customer, Invoice, InvoiceItem, NCFType, Payment
from ._helpers import _org

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
    template_name = "invoices/reports.html"
    required_module = "invoices"
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
    required_module = "invoices"
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
            return redirect("invoices:reports")

        month, year = int(month), int(year)
        invoices = (
            Invoice.invoices.filter(
                organization=_org(request),
                issue_date__month=month,
                issue_date__year=year,
            )
            .exclude(status=Invoice.Status.DRAFT)
            .exclude(status=Invoice.Status.CANCELLED)
            .select_related("customer")
            .order_by("issue_date", "encf")
        )

        buf = io.StringIO()
        for inv in invoices:
            c = inv.customer
            id_type_code = {"RNC": "1", "CED": "2", "PAS": "3", "EXT": "4"}.get(c.id_type, "")
            buyer_id = c.rnc_cedula or ""
            buyer_type = id_type_code if buyer_id else ""
            encf_mod = inv.encf_modified.encf if inv.encf_modified else ""

            last_alloc = inv.allocations.select_related("payment").order_by("-payment__date").first()
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

        filename = f"607_{year}{month:02d}_{_org(request).slug}.txt"
        response = HttpResponse(buf.getvalue(), content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class Report608View(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def get(self, request):
        month = request.GET.get("month")
        year = request.GET.get("year")
        if not (month and year):
            messages.error(request, _("Debe seleccionar mes y año."))
            return redirect("invoices:reports")

        month, year = int(month), int(year)
        cancelled = (
            Invoice.invoices.filter(
                organization=_org(request),
                status=Invoice.Status.CANCELLED,
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

        filename = f"608_{year}{month:02d}_{_org(request).slug}.txt"
        response = HttpResponse(buf.getvalue(), content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ReportAgingView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def get(self, request):
        _zero = Decimal("0.00")
        _dec = DecimalField(max_digits=14, decimal_places=2)

        customers = Customer.objects.filter(organization=_org(request)).order_by("name")
        customer_id = request.GET.get("customer", "").strip()

        selected_customer = None
        if customer_id:
            selected_customer = get_object_or_404(Customer, pk=customer_id, organization=_org(request))

        qs = Invoice.invoices.filter(
            organization=_org(request),
            status__in=[Invoice.Status.CONFIRMED, Invoice.Status.SENT, Invoice.Status.OVERDUE],
        )
        if selected_customer:
            qs = qs.filter(customer=selected_customer)

        invoices = list(
            qs.annotate(paid_amount=Coalesce(Sum("allocations__amount"), _zero, output_field=_dec))
            .select_related("customer")
        )
        for inv in invoices:
            inv.line_balance = inv.total - inv.paid_amount

        customers_map = {}
        for inv in invoices:
            if inv.line_balance <= _zero:
                continue
            cpk = inv.customer_id
            if cpk not in customers_map:
                customers_map[cpk] = {
                    "customer": inv.customer,
                    "buckets": {b: _zero for b in Invoice.AgingBucket.values},
                    "total": _zero,
                }
            customers_map[cpk]["buckets"][inv.aging_bucket] += inv.line_balance
            customers_map[cpk]["total"] += inv.line_balance

        col_totals = {b: _zero for b in Invoice.AgingBucket.values}
        grand_total = _zero
        rows = sorted(customers_map.values(), key=lambda r: r["customer"].name)
        for row in rows:
            row["bucket_cells"] = [
                {"amount": row["buckets"][b], "css": _AGING_CSS[b]}
                for b in Invoice.AgingBucket.values
            ]
            for b in Invoice.AgingBucket.values:
                col_totals[b] += row["buckets"][b]
            grand_total += row["total"]

        return render(
            request, "invoices/report_aging.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("invoices:reports")},
                        {"label": _("Antigüedad de Cuentas por Cobrar")},
                    ]
                ),
                "rows": rows,
                "bucket_headers": [
                    {"label": Invoice.AgingBucket(b).label, "css": _AGING_CSS[b]}
                    for b in Invoice.AgingBucket.values
                ],
                "col_total_cells": [
                    {"amount": col_totals[b], "css": _AGING_CSS[b]}
                    for b in Invoice.AgingBucket.values
                ],
                "grand_total": grand_total,
                "today": timezone.now().date(),
                "customers": customers,
                "customer_id": customer_id,
                "selected_customer": selected_customer,
            },
        )


class ReportStatementView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def get(self, request):
        from datetime import datetime as dt
        _zero = Decimal("0.00")
        _dec = DecimalField(max_digits=14, decimal_places=2)

        customers = Customer.objects.filter(organization=_org(request)).order_by("name")

        customer_id   = request.GET.get("customer",  "").strip()
        date_from_str = request.GET.get("date_from", "").strip()
        date_to_str   = request.GET.get("date_to",   "").strip()

        customer = None
        lines = []
        opening_balance = closing_balance = _zero
        period_invoiced = period_collected = _zero
        error = None

        if customer_id and date_from_str and date_to_str:
            try:
                customer = get_object_or_404(Customer, pk=customer_id, organization=_org(request))
                d_from = dt.strptime(date_from_str, "%Y-%m-%d").date()
                d_to   = dt.strptime(date_to_str,   "%Y-%m-%d").date()

                inv_before = (
                    Invoice.invoices.filter(
                        organization=_org(request), customer=customer, issue_date__lt=d_from,
                    )
                    .exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
                    .aggregate(t=Coalesce(Sum("total"), _zero, output_field=_dec))["t"]
                )
                pmt_before = Payment.objects.filter(
                    organization=_org(request), customer=customer, date__lt=d_from,
                ).aggregate(t=Coalesce(Sum("amount"), _zero, output_field=_dec))["t"]
                opening_balance = inv_before - pmt_before

                for inv in (
                    Invoice.invoices.filter(
                        organization=_org(request), customer=customer,
                        issue_date__gte=d_from, issue_date__lte=d_to,
                    )
                    .exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
                    .order_by("issue_date", "created_at")
                ):
                    lines.append({
                        "date": inv.issue_date, "type": "invoice",
                        "ref":  inv.display_number,
                        "url":  reverse("invoices:invoice_detail", args=[inv.pk]),
                        "debit": inv.total, "credit": _zero,
                    })
                    period_invoiced += inv.total

                for pmt in Payment.objects.filter(
                    organization=_org(request), customer=customer,
                    date__gte=d_from, date__lte=d_to,
                ).order_by("date", "created_at"):
                    lines.append({
                        "date": pmt.date, "type": "payment",
                        "ref":  f"PAG-{pmt.pk.hex[:8].upper()}",
                        "url":  reverse("invoices:payment_detail", args=[pmt.pk]),
                        "debit": _zero, "credit": pmt.amount,
                    })
                    period_collected += pmt.amount

                lines.sort(key=lambda x: (x["date"], x["type"]))
                balance = opening_balance
                for line in lines:
                    balance += line["debit"] - line["credit"]
                    line["balance"] = balance
                closing_balance = balance

            except (ValueError, TypeError):
                error = _("Fechas inválidas.")

        return render(
            request, "invoices/report_statement.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("invoices:reports")},
                        {"label": _("Estado de Cuenta")},
                    ]
                ),
                "customers": customers, "customer": customer, "customer_id": customer_id,
                "date_from": date_from_str, "date_to": date_to_str, "lines": lines,
                "opening_balance": opening_balance, "closing_balance": closing_balance,
                "period_invoiced": period_invoiced, "period_collected": period_collected,
                "error": error,
            },
        )


class ReportSalesByPeriodView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def get(self, request):
        _zero = Decimal("0.00")
        _dec = DecimalField(max_digits=14, decimal_places=2)

        year_str  = request.GET.get("year",  "").strip()
        month_str = request.GET.get("month", "").strip()
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
                        Invoice.invoices.filter(
                            organization=_org(request),
                            issue_date__year=year, issue_date__month=month,
                        )
                        .exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
                        .annotate(period=TruncDay("issue_date"))
                        .values("period")
                        .annotate(total=Coalesce(Sum("total"), _zero, output_field=_dec))
                    )
                    pmt_qs = (
                        Payment.objects.filter(
                            organization=_org(request),
                            date__year=year, date__month=month,
                        )
                        .annotate(period=TruncDay("date"))
                        .values("period")
                        .annotate(total=Coalesce(Sum("amount"), _zero, output_field=_dec))
                    )
                else:
                    inv_qs = (
                        Invoice.invoices.filter(
                            organization=_org(request), issue_date__year=year,
                        )
                        .exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
                        .annotate(period=TruncMonth("issue_date"))
                        .values("period")
                        .annotate(total=Coalesce(Sum("total"), _zero, output_field=_dec))
                    )
                    pmt_qs = (
                        Payment.objects.filter(
                            organization=_org(request), date__year=year,
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

        return render(
            request, "invoices/report_sales_period.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("invoices:reports")},
                        {"label": _("Ventas por Período")},
                    ]
                ),
                "year": year, "month": month,
                "year_input": year_str, "month_input": month_str,
                "rows": rows, "totals": totals,
                "by_day": by_day, "today": timezone.now().date(),
            },
        )


class ReportInvoicesByCustomerView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def get(self, request):
        from datetime import datetime as dt
        _zero = Decimal("0.00")
        _dec = DecimalField(max_digits=14, decimal_places=2)

        customers = Customer.objects.filter(organization=_org(request)).order_by("name")
        customer_id   = request.GET.get("customer",  "").strip()
        date_from_str = request.GET.get("date_from", "").strip()
        date_to_str   = request.GET.get("date_to",   "").strip()

        customer = None
        invoices = []
        totals = {"subtotal": _zero, "itbis_18": _zero, "total": _zero}
        error = None

        if customer_id and date_from_str and date_to_str:
            try:
                customer = get_object_or_404(Customer, pk=customer_id, organization=_org(request))
                d_from = dt.strptime(date_from_str, "%Y-%m-%d").date()
                d_to   = dt.strptime(date_to_str,   "%Y-%m-%d").date()

                invoices = list(
                    Invoice.invoices.filter(
                        organization=_org(request),
                        customer=customer,
                        issue_date__gte=d_from,
                        issue_date__lte=d_to,
                    )
                    .exclude(status=Invoice.Status.DRAFT)
                    .order_by("issue_date", "created_at")
                )

                for inv in invoices:
                    totals["subtotal"] += inv.subtotal
                    totals["itbis_18"] += inv.itbis_18
                    totals["total"]    += inv.total

            except (ValueError, TypeError):
                error = _("Fechas inválidas.")

        return render(
            request, "invoices/report_invoices_by_customer.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("invoices:reports")},
                        {"label": _("Facturas por Cliente")},
                    ]
                ),
                "customers": customers, "customer": customer, "customer_id": customer_id,
                "date_from": date_from_str, "date_to": date_to_str,
                "invoices": invoices, "totals": totals, "error": error,
                "today": timezone.now().date(),
            },
        )


class ReportCollectionsView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def get(self, request):
        from datetime import datetime as dt
        _zero = Decimal("0.00")
        _dec = DecimalField(max_digits=14, decimal_places=2)

        date_from_str = request.GET.get("date_from", "").strip()
        date_to_str   = request.GET.get("date_to",   "").strip()

        payments    = []
        by_method   = []
        grand_total = _zero
        error       = None

        if date_from_str and date_to_str:
            try:
                d_from = dt.strptime(date_from_str, "%Y-%m-%d").date()
                d_to   = dt.strptime(date_to_str,   "%Y-%m-%d").date()

                payments = list(
                    Payment.objects.filter(
                        organization=_org(request), date__gte=d_from, date__lte=d_to,
                    )
                    .select_related("customer")
                    .order_by("date", "customer__name")
                )

                method_labels = dict(Payment.Method.choices)
                by_method = [
                    {**r, "method_display": method_labels.get(r["method"], r["method"])}
                    for r in Payment.objects.filter(
                        organization=_org(request), date__gte=d_from, date__lte=d_to,
                    )
                    .values("method")
                    .annotate(count=Count("id"), total=Coalesce(Sum("amount"), _zero, output_field=_dec))
                    .order_by("method")
                ]

                grand_total = sum(p.amount for p in payments)

            except (ValueError, TypeError):
                error = _("Fechas inválidas.")

        return render(
            request, "invoices/report_collections.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("invoices:reports")},
                        {"label": _("Cobros del Período")},
                    ]
                ),
                "date_from": date_from_str, "date_to": date_to_str,
                "payments": payments, "by_method": by_method,
                "grand_total": grand_total, "error": error,
            },
        )


class ReportITBISView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def get(self, request):
        _zero = Decimal("0.00")
        _dec = DecimalField(max_digits=14, decimal_places=2)

        year_str  = request.GET.get("year",  "").strip()
        month_str = request.GET.get("month", "").strip()
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
                    InvoiceItem.objects.filter(
                        invoice__organization=_org(request),
                        invoice__doc_type=Invoice.DocType.INVOICE,
                        invoice__deleted_at__isnull=True,
                        invoice__issue_date__year=year,
                    )
                    .exclude(invoice__status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
                )
                if month:
                    qs = qs.filter(invoice__issue_date__month=month)

                trunc = TruncDay("invoice__issue_date") if by_day else TruncMonth("invoice__issue_date")

                raw = (
                    qs.annotate(period=trunc)
                    .values("period", "itbis_rate")
                    .annotate(
                        base=Coalesce(Sum("line_total"),    _zero, output_field=_dec),
                        tax= Coalesce(Sum("itbis_amount"),  _zero, output_field=_dec),
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
                    if rate in (InvoiceItem.ITBISRate.EXEMPT, InvoiceItem.ITBISRate.RATE_0):
                        period_map[p]["exempt"] += r["base"]
                    elif rate == InvoiceItem.ITBISRate.RATE_16:
                        period_map[p]["base_16"]  += r["base"]
                        period_map[p]["itbis_16"] += r["tax"]
                    elif rate == InvoiceItem.ITBISRate.RATE_18:
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

        return render(
            request, "invoices/report_itbis.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("invoices:reports")},
                        {"label": _("Resumen de ITBIS")},
                    ]
                ),
                "year": year, "month": month,
                "year_input": year_str, "month_input": month_str,
                "rows": rows, "totals": totals,
                "by_day": by_day, "today": timezone.now().date(),
            },
        )


class ReportSalesByNCFTypeView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def get(self, request):
        _zero = Decimal("0.00")
        _dec = DecimalField(max_digits=14, decimal_places=2)

        month_str = request.GET.get("month", "").strip()
        year_str  = request.GET.get("year",  "").strip()
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
                    Invoice.invoices.filter(
                        organization=_org(request),
                        issue_date__year=year,
                        issue_date__month=month,
                    )
                    .exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
                    .values("ncf_type")
                    .annotate(
                        count=Count("id"),
                        subtotal=Coalesce(Sum("subtotal"),  _zero, output_field=_dec),
                        itbis_18=Coalesce(Sum("itbis_18"), _zero, output_field=_dec),
                        itbis_16=Coalesce(Sum("itbis_16"), _zero, output_field=_dec),
                        total=Coalesce(Sum("total"),        _zero, output_field=_dec),
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

        return render(
            request, "invoices/report_ncf_type.html",
            {
                **self.get_context(
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Reportes"), "url": reverse("invoices:reports")},
                        {"label": _("Ventas por Tipo de Comprobante")},
                    ]
                ),
                "month": month, "year": year,
                "month_input": month_str, "year_input": year_str,
                "rows": rows, "totals": totals, "total_count": total_count,
                "today": timezone.now().date(),
            },
        )
