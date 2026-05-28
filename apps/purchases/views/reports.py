import csv
from datetime import date

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View

from apps.accounts.views import ERPBaseViewMixin
from ..models import PurchaseDocument

_MONTHS_ES = [
    (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
    (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
    (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
]


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
                "RNC Proveedor",
                "NCF",
                "Tipo NCF",
                "Fecha",
                "Subtotal",
                "ITBIS 18%",
                "ITBIS 16%",
                "Total",
            ])
            for inv in qs:
                writer.writerow([
                    inv.supplier_rnc,
                    inv.supplier_ncf,
                    inv.supplier_ncf_type,
                    inv.issue_date.strftime("%Y-%m-%d"),
                    inv.subtotal,
                    inv.itbis_18,
                    inv.itbis_16,
                    inv.total,
                ])
            return response

        next_month = today.month % 12 + 1
        next_year = today.year + (1 if today.month == 12 else 0)
        dgii_deadline = date(next_year, next_month, 15)

        invoices = list(qs)
        total_subtotal = sum(i.subtotal for i in invoices)
        total_itbis = sum(i.itbis_18 + i.itbis_16 for i in invoices)
        total_total = sum(i.total for i in invoices)

        return render(
            request,
            "purchases/report_606.html",
            self.get_context(
                module="supplier-invoice",
                invoices=invoices,
                month=month_int,
                year=year_int,
                months=_MONTHS_ES,
                today=today,
                dgii_deadline=dgii_deadline,
                total_subtotal=total_subtotal,
                total_itbis=total_itbis,
                total_total=total_total,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Reporte 606")},
                ],
            ),
        )
