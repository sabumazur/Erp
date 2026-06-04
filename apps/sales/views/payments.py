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
from ..models import SalesDocument, Payment, PaymentAllocation
from ..services import PaymentService


class PaymentListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "sales/payment_list.html"
    required_module = "sales"

    dt_columns = [
        DTColumn("date",           _("Fecha"),    sortable=True),
        DTColumn("customer__name", _("Cliente"),  sortable=True),
        DTColumn("method",         _("Método"),   sortable=False),
        DTColumn("amount",         _("Monto"),    sortable=True, numeric=True),
        DTColumn("reference",      _("Referencia"),sortable=False, visible=False),
        DTColumn("allocations",    _("Facturas"), sortable=False),
    ]
    dt_default_sort = "-date"
    dt_url = "sales:payment_list"
    dt_row_template = "sales/partials/payment_row.html"
    dt_filter_template = "sales/partials/payment_filters.html"
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
            .prefetch_related("allocations__invoice__customer")
        )
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["customer__name"], trgm_fields=["reference"])
        f = PaymentFilter(self.request.GET, queryset=qs, organization=org)
        ctx["filter"] = f
        ctx.update(self.apply_datatable(f.qs))

        if not self.request.htmx:
            today = date.today()
            base = Payment.objects.filter(organization=org)
            month_qs = base.filter(date__year=today.year, date__month=today.month)
            ctx["stats"] = [
                {"label": _("Total pagos"), "value": base.count(),
                 "icon": "bi-cash-coin", "color": "primary"},
                {"label": _("Cobrado este mes"),
                 "value": "{:,.2f}".format(month_qs.aggregate(t=Sum("amount"))["t"] or 0),
                 "icon": "bi-cash-stack", "color": "success", "currency": "RD$"},
                {"label": _("Total cobrado"),
                 "value": "{:,.2f}".format(base.aggregate(t=Sum("amount"))["t"] or 0),
                 "icon": "bi-wallet2", "color": "info", "currency": "RD$"},
                {"label": _("Pagos este mes"), "value": month_qs.count(),
                 "icon": "bi-calendar-check", "color": "secondary"},
            ]

        ctx["module"] = "payment"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Pagos")},
        ]
        return ctx


class PaymentCreateView(ERPBaseViewMixin, View):
    required_module = "sales"

    def _ctx(self, request, form):
        return {
            **self.get_context(
                module="payment",
                form=form,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Pagos"), "url": reverse("sales:payment_list")},
                    {"label": _("Nuevo pago")},
                ],
            ),
        }

    def get(self, request):
        form = PaymentHeaderForm(organization=request.organization, initial={"date": date.today()})
        return render(request, "sales/payment_form.html", self._ctx(request, form))

    def post(self, request):
        form = PaymentHeaderForm(organization=request.organization, data=request.POST)

        if not form.is_valid():
            return render(request, "sales/payment_form.html", self._ctx(request, form))

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
                inv = SalesDocument.invoices.get(pk=pk_str, organization=request.organization)
            except SalesDocument.DoesNotExist:
                continue
            allocations.append({"invoice": inv, "amount": amt})

        if not allocations:
            form.add_error(None, _("Seleccione al menos una factura y un monto mayor a cero."))
            return render(request, "sales/payment_form.html", self._ctx(request, form))

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
            return redirect("sales:payment_detail", pk=payment.pk)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return render(request, "sales/payment_form.html", self._ctx(request, form))


class PaymentDetailView(HistoryMixin, ERPBaseViewMixin, View):
    required_module = "sales"

    def get(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("customer", "organization").prefetch_related("allocations__invoice__customer"),
            pk=pk, organization=request.organization,
        )
        return render(
            request, "sales/payment_detail.html",
            {
                **self.get_context(
                    module="payment",
                    payment=payment,
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Pagos"), "url": reverse("sales:payment_list")},
                        {"label": str(payment)},
                    ],
                ),
                "history_records": self.get_history(payment),
            },
        )


class PaymentDeleteView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk, organization=request.organization)
        try:
            PaymentService.delete(payment)
            messages.success(request, _("Pago eliminado y facturas reabiertas."))
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("sales:payment_list")


class OutstandingInvoicesView(ERPBaseViewMixin, View):
    required_module = "sales"

    def get(self, request):
        customer_id = request.GET.get("customer", "").strip()
        invoices = []
        if customer_id:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            qs = (
                SalesDocument.invoices.filter(
                    organization=request.organization,
                    customer_id=customer_id,
                    status__in=[
                        SalesDocument.Status.CONFIRMED,
                        SalesDocument.Status.SENT,
                        SalesDocument.Status.OVERDUE,
                    ],
                )
                .exclude(ncf_type__in=SalesDocument.NOTE_TYPES)
                .annotate(
                    paid_amount=Coalesce(Sum("allocations__amount"), _zero, output_field=_dec)
                )
                .order_by("due_date", "issue_date")
            )
            for inv in qs:
                inv.line_balance = inv.total - inv.paid_amount
            invoices = [inv for inv in qs if inv.line_balance > Decimal("0")]

        return render(
            request, "sales/partials/payment_allocation_rows.html",
            {"invoices": invoices},
        )
