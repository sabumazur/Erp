from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.datatable import DTColumn, DataTableMixin
from apps.core.search import fts_search
from ..forms import SupplierPaymentHeaderForm
from ..models import PurchaseDocument, SupplierPayment
from ..services import SupplierPaymentService


class SupplierPaymentListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "purchases/supplier_payment_list.html"
    required_module = "purchasing"

    dt_columns = [
        DTColumn("date",           _("Fecha"),     sortable=True),
        DTColumn("supplier__name", _("Proveedor"), sortable=True),
        DTColumn("method",         _("Método"),    sortable=False),
        DTColumn("amount",         _("Monto"),     sortable=True, numeric=True),
        DTColumn("reference",      _("Referencia"),sortable=False, visible=False),
        DTColumn("allocations",    _("Facturas"),  sortable=False),
    ]
    dt_default_sort = "-date"
    dt_url = "purchases:supplier_payment_list"
    dt_row_template = "purchases/partials/supplier_payment_row.html"
    dt_ribbon_template = "purchases/partials/supplier_payment_ribbon.html"
    dt_filter_template = "purchases/partials/supplier_payment_filters.html"
    dt_search_placeholder = _("Proveedor o referencia…")
    dt_id = "supplier_payments"

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.request.organization
        qs = (
            SupplierPayment.objects.filter(organization=org)
            .select_related("supplier")
            .prefetch_related("allocations__supplier_invoice")
        )
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["supplier__name"], trgm_fields=["reference"])
        ctx.update(self.apply_datatable(qs))
        ctx["module"] = "supplier-payment"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Pagos a Proveedores")},
        ]
        return ctx


class SupplierPaymentCreateView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def _ctx(self, request, form):
        return self.get_context(
            module="supplier-payment",
            form=form,
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Pagos a Proveedores"), "url": reverse("purchases:supplier_payment_list")},
                {"label": _("Nuevo pago")},
            ],
        )

    def get(self, request):
        form = SupplierPaymentHeaderForm(organization=request.organization, initial={"date": date.today()})
        return render(request, "purchases/supplier_payment_form.html", self._ctx(request, form))

    def post(self, request):
        form = SupplierPaymentHeaderForm(organization=request.organization, data=request.POST)
        if not form.is_valid():
            return render(request, "purchases/supplier_payment_form.html", self._ctx(request, form))

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
                inv = PurchaseDocument.supplier_invoices.get(pk=pk_str, organization=request.organization)
            except PurchaseDocument.DoesNotExist:
                continue
            allocations.append({"invoice": inv, "amount": amt})

        if not allocations:
            form.add_error(None, _("Seleccione al menos una factura y un monto mayor a cero."))
            return render(request, "purchases/supplier_payment_form.html", self._ctx(request, form))

        try:
            payment = SupplierPaymentService.create_payment(
                supplier=form.cleaned_data["supplier"],
                org=request.organization,
                payment_date=form.cleaned_data["date"],
                method=form.cleaned_data["method"],
                reference=form.cleaned_data.get("reference", ""),
                notes=form.cleaned_data.get("notes", ""),
                allocations=allocations,
            )
            messages.success(request, _("Pago registrado exitosamente."))
            return redirect("purchases:supplier_payment_detail", pk=payment.pk)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return render(request, "purchases/supplier_payment_form.html", self._ctx(request, form))


class SupplierPaymentDetailView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def get(self, request, pk):
        payment = get_object_or_404(
            SupplierPayment.objects.select_related("supplier", "organization")
            .prefetch_related("allocations__supplier_invoice"),
            pk=pk,
            organization=request.organization,
        )
        return render(
            request,
            "purchases/supplier_payment_detail.html",
            self.get_context(
                module="supplier-payment",
                payment=payment,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Pagos a Proveedores"), "url": reverse("purchases:supplier_payment_list")},
                    {"label": str(payment)},
                ],
            ),
        )


class SupplierPaymentDeleteView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def post(self, request, pk):
        payment = get_object_or_404(SupplierPayment, pk=pk, organization=request.organization)
        try:
            SupplierPaymentService.delete_payment(payment)
            messages.success(request, _("Pago eliminado y facturas reabiertas."))
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("purchases:supplier_payment_list")


class OutstandingSupplierInvoicesView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def get(self, request):
        supplier_id = request.GET.get("supplier", "").strip()
        invoices = []
        if supplier_id:
            _zero = Decimal("0.00")
            _dec = DecimalField(max_digits=14, decimal_places=2)
            qs = (
                PurchaseDocument.supplier_invoices.filter(
                    organization=request.organization,
                    supplier_id=supplier_id,
                    status__in=[
                        PurchaseDocument.Status.CONFIRMED,
                        PurchaseDocument.Status.PAID,
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
            request,
            "purchases/partials/supplier_payment_allocation_rows.html",
            {"invoices": invoices},
        )
