from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from apps.accounts.views import ERPBaseViewMixin
from ..filters import PaymentFilter
from ..forms import PaymentHeaderForm, PaymentForm
from ..models import Invoice, Payment, PaymentAllocation
from ..services import PaymentService
from ._helpers import _org, _active_filter_count


class PaymentListView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request):
        from django.db.models import Q
        qs = (
            Payment.objects.filter(organization=_org(request))
            .select_related("customer")
            .prefetch_related("allocations__invoice")
            .order_by("-date", "-created_at")
        )
        q = request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(reference__icontains=q) | Q(customer__name__icontains=q))
        f = PaymentFilter(request.GET, queryset=qs, organization=_org(request))
        total = sum(p.amount for p in f.qs)
        ctx = {
            **self.get_context(
                filter=f,
                payments=f.qs,
                total=total,
                active_filter_count=_active_filter_count(request),
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Pagos")},
                ],
            ),
        }
        if request.htmx:
            return render(request, "invoices/partials/payment_table.html", ctx)
        return render(request, "invoices/payment_list.html", ctx)


class PaymentCreateView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def _ctx(self, request, form):
        return {
            **self.get_context(
                form=form,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Pagos"), "url": reverse("invoices:payment_list")},
                    {"label": _("Nuevo pago")},
                ],
            ),
        }

    def get(self, request):
        form = PaymentHeaderForm(organization=_org(request), initial={"date": date.today()})
        return render(request, "invoices/payment_form.html", self._ctx(request, form))

    def post(self, request):
        form = PaymentHeaderForm(organization=_org(request), data=request.POST)

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
                inv = Invoice.invoices.get(pk=pk_str, organization=_org(request))
            except Invoice.DoesNotExist:
                continue
            allocations.append({"invoice": inv, "amount": amt})

        if not allocations:
            form.add_error(None, _("Seleccione al menos una factura y un monto mayor a cero."))
            return render(request, "invoices/payment_form.html", self._ctx(request, form))

        try:
            payment = PaymentService.register(
                organization=_org(request),
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


class PaymentDetailView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("customer", "organization").prefetch_related("allocations__invoice"),
            pk=pk, organization=_org(request),
        )
        return render(
            request, "invoices/payment_detail.html",
            {
                **self.get_context(
                    payment=payment,
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Pagos"), "url": reverse("invoices:payment_list")},
                        {"label": str(payment)},
                    ],
                ),
            },
        )


class PaymentDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk, organization=_org(request))
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
                    organization=_org(request),
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
