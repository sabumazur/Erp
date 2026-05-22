from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.mixins import HistoryMixin
from apps.core.datatable import DTColumn, DataTableMixin
from apps.core.search import fts_search
from ..filters import PaymentFilter
from ..forms import PaymentHeaderForm, PaymentForm
from ..models import Invoice, Payment, PaymentAllocation
from ..services import PaymentService


class PaymentListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "invoices/payment_list.html"
    required_module = "invoices"

    dt_columns = [
        DTColumn("date",           _("Fecha"),    sortable=True),
        DTColumn("customer__name", _("Cliente"),  sortable=True),
        DTColumn("method",         _("Método"),   sortable=False),
        DTColumn("amount",         _("Monto"),    sortable=True, numeric=True),
        DTColumn("reference",      _("Referencia"),sortable=False, visible=False),
        DTColumn("allocations",    _("Facturas"), sortable=False),
    ]
    dt_default_sort = "-date"
    dt_url = "invoices:payment_list"
    dt_row_template = "invoices/partials/payment_row.html"
    dt_filter_template = "invoices/partials/payment_filters.html"
    dt_search_placeholder = _("Cliente o referencia…")
    dt_id = "payments"

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.request.organization
        qs = (
            Payment.objects.filter(organization=org)
            .select_related("customer")
            .prefetch_related("allocations__invoice")
        )
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["customer__name"], trgm_fields=["reference"])
        f = PaymentFilter(self.request.GET, queryset=qs, organization=org)
        ctx["filter"] = f
        ctx.update(self.apply_datatable(f.qs))

        if not self.request.htmx:
            today = date.today()
            agg = Payment.objects.filter(organization=org).aggregate(
                total_count=Count("id"),
                total_amount=Sum("amount"),
                month_count=Count("id", filter=Q(
                    date__month=today.month, date__year=today.year,
                )),
                month_amount=Sum("amount", filter=Q(
                    date__month=today.month, date__year=today.year,
                )),
            )
            total_amount = agg["total_amount"] or Decimal("0.00")
            month_amount = agg["month_amount"] or Decimal("0.00")
            ctx["stats"] = [
                {"label": _("Total pagos"),       "value": agg["total_count"],
                 "icon": "bi-cash-stack",         "color": "primary"},
                {"label": _("Monto total"),        "value": f"RD$ {total_amount:,.2f}",
                 "icon": "bi-wallet2",             "color": "success"},
                {"label": _("Pagos este mes"),     "value": agg["month_count"],
                 "icon": "bi-calendar-check",      "color": "info"},
                {"label": _("Cobrado este mes"),   "value": f"RD$ {month_amount:,.2f}",
                 "icon": "bi-graph-up-arrow",      "color": "warning"},
            ]
        ctx["module"] = "payment"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Pagos")},
        ]
        return ctx


class PaymentCreateView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def _ctx(self, request, form):
        return {
            **self.get_context(
                module="payment",
                form=form,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Pagos"), "url": reverse("invoices:payment_list")},
                    {"label": _("Nuevo pago")},
                ],
            ),
        }

    def get(self, request):
        form = PaymentHeaderForm(organization=request.organization, initial={"date": date.today()})
        return render(request, "invoices/payment_form.html", self._ctx(request, form))

    def post(self, request):
        form = PaymentHeaderForm(organization=request.organization, data=request.POST)

        if not form.is_valid():
            return render(request, "invoices/payment_form.html", self._ctx(request, form))

        invoice_pks = request.POST.getlist("alloc_invoices")
        amounts_raw = request.POST.getlist("alloc_amounts")

        allocations = []
        for pk_str, amt_str in zip(invoice_pks, amounts_raw):
            try:
                amt = Decimal(amt_str.replace(",", "."))
            except Exception:
                continue
            if amt <= Decimal("0"):
                continue
            try:
                inv = Invoice.invoices.get(pk=pk_str, organization=request.organization)
            except Invoice.DoesNotExist:
                continue
            allocations.append({"invoice": inv, "amount": amt})

        if not allocations:
            form.add_error(None, _("Seleccione al menos una factura y un monto mayor a cero."))
            return render(request, "invoices/payment_form.html", self._ctx(request, form))

        try:
            payment = PaymentService.register(
                organization=request.organization,
                customer=form.cleaned_data["customer"],
                payment_date=form.cleaned_data["date"],
                method=form.cleaned_data["method"],
                reference=form.cleaned_data.get("reference", ""),
                notes=form.cleaned_data.get("notes", ""),
                allocations=allocations,
            )
            messages.success(request, _("Pago registrado exitosamente."))
            return redirect("invoices:payment_detail", pk=payment.pk)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return render(request, "invoices/payment_form.html", self._ctx(request, form))


class PaymentDetailView(HistoryMixin, ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("customer", "organization").prefetch_related("allocations__invoice"),
            pk=pk, organization=request.organization,
        )
        return render(
            request, "invoices/payment_detail.html",
            {
                **self.get_context(
                    module="payment",
                    payment=payment,
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Pagos"), "url": reverse("invoices:payment_list")},
                        {"label": str(payment)},
                    ],
                ),
                "history_records": self.get_history(payment),
            },
        )


class PaymentDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk, organization=request.organization)
        try:
            PaymentService.delete(payment)
            messages.success(request, _("Pago eliminado y facturas reabiertas."))
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("invoices:payment_list")


class OutstandingInvoicesView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request):
        customer_id = request.GET.get("customer", "").strip()
        invoices = []
        if customer_id:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            qs = (
                Invoice.invoices.filter(
                    organization=request.organization,
                    customer_id=customer_id,
                    status__in=[
                        Invoice.Status.CONFIRMED,
                        Invoice.Status.SENT,
                        Invoice.Status.OVERDUE,
                    ],
                )
                .annotate(
                    paid_amount=Coalesce(Sum("allocations__amount"), _zero, output_field=_dec)
                )
                .order_by("due_date", "issue_date")
            )
            for inv in qs:
                inv.line_balance = inv.total - inv.paid_amount
            invoices = [inv for inv in qs if inv.line_balance > Decimal("0")]

        return render(
            request, "invoices/partials/payment_allocation_rows.html",
            {"invoices": invoices},
        )
