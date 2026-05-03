import csv
import importlib
import io
import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, UpdateView, DetailView

from apps.accounts.views import ERPBaseViewMixin
from .filters import InvoiceFilter, QuotationFilter, SaleOrderFilter, PaymentFilter

from .forms import (
    CustomerForm,
    CustomerDepartmentForm,
    InvoiceForm,
    InvoiceItemForm,
    InvoiceItemFormSet,
    PaymentForm,
    PaymentHeaderForm,
    CreditNoteForm,
    NCFSequenceForm,
    QuotationForm,
    SaleOrderForm,
    SaleOrderDeliverForm,
    ConsolidateForm,
)
from .models import (
    Customer,
    CustomerDepartment,
    Invoice,
    InvoiceItem,
    NCFSequence,
    Payment,
    PaymentAllocation,
)
from .services import NCFService, QuotationService, SaleOrderService, PaymentService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _org(request):
    return request.organization


def _customer_defaults_json(request) -> str:
    """
    Serialize each active customer's billing defaults for the current org.
    Injected as window.CUSTOMER_DEFAULTS so the form can update ncf_type and
    payment_condition automatically when the user changes the customer select.

    payment_condition derivation:
      CREDIT → customer has a payment_term with days_due > 0
      CASH   → no term, or days_due == 0
    """
    qs = Customer.objects.filter(
        organization=_org(request),
    ).select_related("payment_term")
    return json.dumps(
        {
            str(c.pk): {
                "ncf_type": c.default_ncf_type,
                "payment_condition": (
                    "CREDIT"
                    if c.payment_term and c.payment_term.days_due > 0
                    else "CASH"
                ),
            }
            for c in qs
        },
        ensure_ascii=False,
    )


def _sale_items_json(request) -> str:
    """
    Active SALE/BOTH items for the current org serialized as JSON.
    Injected into form pages as window.ITEM_CATALOG so Alpine can
    populate per-row <select> pickers without any per-row HTMX calls.
    """
    from apps.items.models import Item

    qs = Item.objects.filter(
        organization=_org(request),
        is_active=True,
        item_type__in=[Item.ItemType.SALE, Item.ItemType.BOTH],
    ).order_by("name")
    return json.dumps(
        [
            {
                "pk": str(item.pk),
                "code": item.code,
                "name": item.name,
                "unit_price": str(item.unit_price),
                "itbis_rate": item.itbis_rate,
            }
            for item in qs
        ],
        ensure_ascii=False,
    )


# ═════════════════════════════════════════════════════════════════════════════
#  CUSTOMER VIEWS
# ═════════════════════════════════════════════════════════════════════════════


class CustomerListView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/customer_list.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["customers"] = (
            Customer.objects.filter(organization=_org(self.request))
            .annotate(
                dept_count=Count(
                    "departments", filter=Q(departments__deleted_at__isnull=True)
                )
            )
            .order_by("name")
        )
        ctx["form"] = CustomerForm()
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Clientes")},
        ]
        return ctx

    def post(self, request):
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.organization = _org(request)
            customer.save()
            if request.htmx:
                customers = Customer.objects.filter(
                    organization=_org(request)
                ).order_by("name")
                resp = render(
                    request,
                    "invoices/partials/customer_table.html",
                    {"customers": customers},
                )
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showToast": {
                            "message": str(_("Cliente creado correctamente.")),
                            "type": "success",
                        }
                    }
                )
                return resp
            messages.success(request, _("Cliente creado correctamente."))
            return redirect("invoices:customer_list")

        if request.htmx:
            resp = render(
                request,
                "invoices/partials/customer_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("invoices:customer_list"),
                    "submit_label": _("Crear"),
                },
            )
            resp["HX-Retarget"] = "#customer-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class CustomerUpdateView(ERPBaseViewMixin, UpdateView):
    form_class = CustomerForm
    template_name = "invoices/customer_form.html"
    required_module = "invoices"
    success_url = reverse_lazy("invoices:customer_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Clientes"), "url": reverse("invoices:customer_list")},
            {"label": self.object.name},
        ]
        return ctx

    def get_object(self):
        return get_object_or_404(
            Customer, pk=self.kwargs["pk"], organization=_org(self.request)
        )

    def get(self, request, *args, **kwargs):
        if request.htmx:
            customer = self.get_object()
            form = CustomerForm(instance=customer)
            return render(
                request,
                "invoices/partials/customer_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("invoices:customer_edit", args=[customer.pk]),
                    "submit_label": _("Guardar"),
                    "hx_target": request.GET.get("hx_target", "#customer-table"),
                },
            )
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.htmx:
            hx_target = self.request.POST.get("_hx_target", "#customer-table")
            if hx_target != "#customer-table":
                messages.success(self.request, _("Cliente actualizado."))
                resp = HttpResponse()
                resp["HX-Refresh"] = "true"
                return resp
            customers = Customer.objects.filter(
                organization=_org(self.request)
            ).order_by("name")
            resp = render(
                self.request,
                "invoices/partials/customer_table.html",
                {"customers": customers},
            )
            resp["HX-Trigger"] = json.dumps(
                {
                    "showToast": {
                        "message": str(_("Cliente actualizado.")),
                        "type": "success",
                    }
                }
            )
            return resp
        messages.success(self.request, _("Cliente actualizado."))
        return response

    def form_invalid(self, form):
        if self.request.htmx:
            customer = self.get_object()
            hx_target = self.request.POST.get("_hx_target", "#customer-table")
            resp = render(
                self.request,
                "invoices/partials/customer_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("invoices:customer_edit", args=[customer.pk]),
                    "submit_label": _("Guardar"),
                    "hx_target": hx_target,
                },
            )
            resp["HX-Retarget"] = "#customer-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        return super().form_invalid(form)


class CustomerDetailView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk, organization=_org(request))
        departments = customer.departments.filter(deleted_at__isnull=True).order_by(
            "name"
        )

        # ── Account / payment summary ─────────────────────────────────────────
        _zero = Decimal("0.00")
        _dec_field = DecimalField(max_digits=14, decimal_places=2)

        invoices = list(
            Invoice.invoices.filter(organization=_org(request), customer=customer)
            .exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
            .annotate(
                paid_amount=Coalesce(
                    Sum("allocations__amount"), _zero, output_field=_dec_field
                )
            )
            .select_related("customer")
            .order_by("-issue_date")
        )

        # Attach per-invoice balance as a Python attribute
        for inv in invoices:
            inv.line_balance = inv.total - inv.paid_amount

        total_invoiced = sum((inv.total for inv in invoices), _zero)
        total_paid = sum((inv.paid_amount for inv in invoices), _zero)
        balance = total_invoiced - total_paid
        overdue = sum(
            inv.line_balance for inv in invoices if inv.status == Invoice.Status.OVERDUE
        )

        recent_payments = list(
            Payment.objects.filter(customer=customer, organization=_org(request))
            .prefetch_related("allocations__invoice")
            .order_by("-date", "-created_at")[:30]
        )

        return render(
            request,
            "invoices/customer_detail.html",
            {
                **self.get_context(
                    customer=customer,
                    departments=departments,
                    dept_form=CustomerDepartmentForm(),
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {
                            "label": _("Clientes"),
                            "url": reverse("invoices:customer_list"),
                        },
                        {"label": customer.name},
                    ],
                ),
                "invoices": invoices,
                "total_invoiced": total_invoiced,
                "total_paid": total_paid,
                "balance": balance,
                "overdue": overdue,
                "recent_payments": recent_payments,
            },
        )


class CustomerDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk, organization=_org(request))
        if customer.invoices.exists():
            messages.error(
                request,
                _("No se puede eliminar un cliente con documentos asociados."),
            )
            return redirect("invoices:customer_list")
        name = customer.name
        customer.delete()
        messages.success(request, _(f"Cliente «{name}» eliminado."))
        return redirect("invoices:customer_list")


# ── Customer Department CRUD ──────────────────────────────────────────────────


class CustomerDepartmentCreateView(ERPBaseViewMixin, View):
    """GET → blank form for HTMX modal.  POST → save and refresh table."""

    required_module = "invoices"

    def _customer(self, request, customer_pk):
        return get_object_or_404(Customer, pk=customer_pk, organization=_org(request))

    def _departments(self, customer):
        return customer.departments.filter(deleted_at__isnull=True).order_by("name")

    def get(self, request, customer_pk):
        customer = self._customer(request, customer_pk)
        form = CustomerDepartmentForm()
        return render(
            request,
            "invoices/partials/department_modal_form.html",
            {
                "form": form,
                "customer": customer,
                "action_url": reverse("invoices:department_create", args=[customer_pk]),
                "submit_label": _("Crear"),
            },
        )

    def post(self, request, customer_pk):
        customer = self._customer(request, customer_pk)
        form = CustomerDepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save(commit=False)
            dept.organization = _org(request)
            dept.customer = customer
            dept.save()
            if request.htmx:
                resp = render(
                    request,
                    "invoices/partials/department_table.html",
                    {"departments": self._departments(customer), "customer": customer},
                )
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showToast": {
                            "message": str(_("Departamento creado.")),
                            "type": "success",
                        },
                        "closeDeptModal": True,
                    }
                )
                return resp
            messages.success(request, _("Departamento creado."))
            return redirect("invoices:customer_detail", pk=customer_pk)

        if request.htmx:
            resp = render(
                request,
                "invoices/partials/department_modal_form.html",
                {
                    "form": form,
                    "customer": customer,
                    "action_url": reverse(
                        "invoices:department_create", args=[customer_pk]
                    ),
                    "submit_label": _("Crear"),
                },
            )
            resp["HX-Retarget"] = "#dept-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        messages.error(request, _("Por favor corrija los errores."))
        return redirect("invoices:customer_detail", pk=customer_pk)


class CustomerDepartmentUpdateView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def _get_objects(self, request, customer_pk, pk):
        customer = get_object_or_404(
            Customer, pk=customer_pk, organization=_org(request)
        )
        dept = get_object_or_404(CustomerDepartment, pk=pk, customer=customer)
        return customer, dept

    def _departments(self, customer):
        return customer.departments.filter(deleted_at__isnull=True).order_by("name")

    def get(self, request, customer_pk, pk):
        customer, dept = self._get_objects(request, customer_pk, pk)
        form = CustomerDepartmentForm(instance=dept)
        return render(
            request,
            "invoices/partials/department_modal_form.html",
            {
                "form": form,
                "customer": customer,
                "action_url": reverse(
                    "invoices:department_edit", args=[customer_pk, pk]
                ),
                "submit_label": _("Guardar"),
            },
        )

    def post(self, request, customer_pk, pk):
        customer, dept = self._get_objects(request, customer_pk, pk)
        form = CustomerDepartmentForm(request.POST, instance=dept)
        if form.is_valid():
            form.save()
            if request.htmx:
                resp = render(
                    request,
                    "invoices/partials/department_table.html",
                    {"departments": self._departments(customer), "customer": customer},
                )
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showToast": {
                            "message": str(_("Departamento actualizado.")),
                            "type": "success",
                        },
                        "closeDeptModal": True,
                    }
                )
                return resp
            messages.success(request, _("Departamento actualizado."))
            return redirect("invoices:customer_detail", pk=customer_pk)

        if request.htmx:
            resp = render(
                request,
                "invoices/partials/department_modal_form.html",
                {
                    "form": form,
                    "customer": customer,
                    "action_url": reverse(
                        "invoices:department_edit", args=[customer_pk, pk]
                    ),
                    "submit_label": _("Guardar"),
                },
            )
            resp["HX-Retarget"] = "#dept-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        messages.error(request, _("Por favor corrija los errores."))
        return redirect("invoices:customer_detail", pk=customer_pk)


class CustomerDepartmentToggleView(ERPBaseViewMixin, View):
    """Toggle is_active; returns refreshed table partial for HTMX."""

    required_module = "invoices"

    def post(self, request, customer_pk, pk):
        customer = get_object_or_404(
            Customer, pk=customer_pk, organization=_org(request)
        )
        dept = get_object_or_404(CustomerDepartment, pk=pk, customer=customer)
        dept.is_active = not dept.is_active
        dept.save(update_fields=["is_active", "updated_at"])
        if request.htmx:
            departments = customer.departments.filter(deleted_at__isnull=True).order_by(
                "name"
            )
            return render(
                request,
                "invoices/partials/department_table.html",
                {"departments": departments, "customer": customer},
            )
        return redirect("invoices:customer_detail", pk=customer_pk)


# ═════════════════════════════════════════════════════════════════════════════
#  INVOICE VIEWS
# ═════════════════════════════════════════════════════════════════════════════


class InvoiceListView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/invoice_list.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = (
            Invoice.invoices.filter(  # doc_type=INVOICE only
                organization=_org(self.request)
            )
            .select_related("customer")
            .order_by("-issue_date", "-created_at")
        )
        f = InvoiceFilter(
            self.request.GET, queryset=qs, organization=_org(self.request)
        )
        ctx["filter"] = f
        ctx["invoices"] = f.qs
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Facturas")},
        ]
        return ctx


class InvoiceDetailView(ERPBaseViewMixin, DetailView):
    template_name = "invoices/invoice_detail.html"
    required_module = "invoices"
    context_object_name = "invoice"

    def get_object(self):
        return get_object_or_404(
            Invoice.objects.select_related("customer", "organization", "encf_modified"),
            pk=self.kwargs["pk"],
            organization=_org(self.request),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all()
        ctx["allocations"] = self.object.allocations.select_related("payment").order_by(
            "payment__date"
        )
        ctx["payment_form"] = PaymentForm(
            initial={"amount": self.object.total, "date": date.today()}
        )
        # For consolidated invoices, show the source sale orders
        ctx["consolidated_orders"] = (
            self.object.consolidated_orders.select_related("customer").order_by(
                "delivery_date"
            )
            if self.object.is_invoice
            else None
        )
        invoice = self.object
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Facturas"), "url": reverse("invoices:invoice_list")},
            {"label": invoice.doc_number or invoice.encf or str(_("Borrador"))},
        ]
        return ctx


class InvoiceCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/invoice_form.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", InvoiceForm(organization=_org(self.request)))
        ctx.setdefault("formset", InvoiceItemFormSet())
        ctx["sale_items_json"] = _sale_items_json(self.request)
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Facturas"), "url": reverse("invoices:invoice_list")},
            {"label": _("Nueva factura")},
        ]
        return ctx

    def post(self, request):
        form = InvoiceForm(organization=_org(request), data=request.POST)
        formset = InvoiceItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.organization = _org(request)
            invoice.doc_type = Invoice.DocType.INVOICE
            invoice.save()
            formset.instance = invoice
            formset.save()
            messages.success(request, _("Factura creada como borrador."))
            return redirect("invoices:invoice_detail", pk=invoice.pk)

        ctx = self.get_context_data()
        ctx["form"] = form
        ctx["formset"] = formset
        return self.render_to_response(ctx)


class InvoiceUpdateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/invoice_form.html"
    required_module = "invoices"

    def get_invoice(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, organization=_org(request))
        if not invoice.is_editable:
            messages.error(
                request,
                _(
                    "Esta factura ya fue confirmada y no puede editarse. "
                    "Emita una Nota de Crédito para corregirla."
                ),
            )
            return None, redirect("invoices:invoice_detail", pk=invoice.pk)
        return invoice, None

    def get(self, request, pk):
        invoice, redir = self.get_invoice(request, pk)
        if redir:
            return redir
        ctx = self.get_context_data(
            form=InvoiceForm(organization=_org(request), instance=invoice),
            formset=InvoiceItemFormSet(instance=invoice),
            invoice=invoice,
        )
        return self.render_to_response(ctx)

    def post(self, request, pk):
        invoice, redir = self.get_invoice(request, pk)
        if redir:
            return redir
        form = InvoiceForm(
            organization=_org(request), data=request.POST, instance=invoice
        )
        formset = InvoiceItemFormSet(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Factura actualizada."))
            return redirect("invoices:invoice_detail", pk=invoice.pk)
        ctx = self.get_context_data(form=form, formset=formset, invoice=invoice)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", InvoiceForm(organization=_org(self.request)))
        ctx.setdefault("formset", InvoiceItemFormSet())
        ctx["sale_items_json"] = _sale_items_json(self.request)
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        invoice = kwargs.get("invoice")
        if invoice:
            ctx["breadcrumbs"] = [
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Facturas"), "url": reverse("invoices:invoice_list")},
                {
                    "label": invoice.doc_number or str(_("Borrador")),
                    "url": reverse("invoices:invoice_detail", args=[invoice.pk]),
                },
                {"label": _("Editar")},
            ]
        return ctx


# ── Invoice status transitions ────────────────────────────────────────────────


class InvoiceConfirmView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, organization=_org(request))
        try:
            NCFService.confirm(invoice)
            messages.success(
                request, _(f"Factura confirmada. e-NCF asignado: {invoice.encf}")
            )
        except (ValueError, Exception) as exc:
            messages.error(request, str(exc))
        return redirect("invoices:invoice_detail", pk=invoice.pk)


class InvoiceSendView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, organization=_org(request))
        try:
            NCFService.mark_sent(invoice)
            messages.success(request, _("Factura marcada como enviada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:invoice_detail", pk=invoice.pk)


class InvoicePayView(ERPBaseViewMixin, View):
    """Quick single-invoice payment from the invoice detail page."""

    required_module = "invoices"

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, organization=_org(request))
        form = PaymentForm(request.POST)
        if not form.is_valid():
            messages.error(
                request, _("Por favor corrija los errores en el formulario de pago.")
            )
            return redirect("invoices:invoice_detail", pk=invoice.pk)

        payment = form.save(commit=False)
        payment.customer = invoice.customer
        payment.organization = _org(request)
        payment.save()

        # Allocate the full payment amount to this invoice
        PaymentAllocation.objects.create(
            payment=payment,
            invoice=invoice,
            amount=payment.amount,
        )

        try:
            NCFService.mark_paid(invoice)
            messages.success(
                request, _("Pago registrado. Factura marcada como pagada.")
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:invoice_detail", pk=invoice.pk)


class InvoiceCancelView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, organization=_org(request))
        try:
            NCFService.cancel(invoice)
            messages.success(
                request,
                _(
                    f"Factura {invoice.encf or invoice.pk} anulada. "
                    "Recuerde incluirla en el formato 608 de este período."
                ),
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:invoice_detail", pk=invoice.pk)


class InvoiceDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, organization=_org(request))
        if invoice.status != Invoice.Status.DRAFT:
            messages.error(
                request, _("Solo se pueden eliminar documentos en estado Borrador.")
            )
            return redirect("invoices:invoice_detail", pk=invoice.pk)
        invoice.hard_delete()
        messages.success(request, _("Borrador eliminado."))
        return redirect("invoices:invoice_list")


# ── Credit / Debit Note ───────────────────────────────────────────────────────


class CreditNoteCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/credit_note_form.html"
    required_module = "invoices"

    def get_original(self, request, pk):
        return get_object_or_404(Invoice, pk=pk, organization=_org(request))

    def get(self, request, pk):
        original = self.get_original(request, pk)
        form = CreditNoteForm(initial={"issue_date": date.today(), "ncf_type": 34})
        formset = InvoiceItemFormSet()
        ctx = self.get_context_data(form=form, formset=formset, original=original)
        return self.render_to_response(ctx)

    def post(self, request, pk):
        original = self.get_original(request, pk)
        form = CreditNoteForm(request.POST)
        formset = InvoiceItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            note = form.save(commit=False)
            note.organization = _org(request)
            note.customer = original.customer
            note.encf_modified = original
            note.doc_type = Invoice.DocType.INVOICE
            note.payment_condition = original.payment_condition
            note.save()
            formset.instance = note
            formset.save()
            messages.success(request, _("Nota de Crédito/Débito creada como borrador."))
            return redirect("invoices:invoice_detail", pk=note.pk)

        ctx = self.get_context_data(form=form, formset=formset, original=original)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", CreditNoteForm())
        ctx.setdefault("formset", InvoiceItemFormSet())
        original = kwargs.get("original")
        if original:
            ctx["breadcrumbs"] = [
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Facturas"), "url": reverse("invoices:invoice_list")},
                {
                    "label": original.doc_number or str(_("Borrador")),
                    "url": reverse("invoices:invoice_detail", args=[original.pk]),
                },
                {"label": _("Nota de crédito/débito")},
            ]
        return ctx


# ═════════════════════════════════════════════════════════════════════════════
#  QUOTATION VIEWS
# ═════════════════════════════════════════════════════════════════════════════


class QuotationListView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/quotation_list.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = (
            Invoice.quotations.filter(organization=_org(self.request))
            .select_related("customer")
            .order_by("-issue_date", "-created_at")
        )
        f = QuotationFilter(
            self.request.GET, queryset=qs, organization=_org(self.request)
        )
        ctx["filter"] = f
        ctx["quotations"] = f.qs
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Cotizaciones")},
        ]
        return ctx


class QuotationCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/quotation_form.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", QuotationForm(organization=_org(self.request)))
        ctx.setdefault("formset", InvoiceItemFormSet())
        ctx["sale_items_json"] = _sale_items_json(self.request)
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Cotizaciones"), "url": reverse("invoices:quotation_list")},
            {"label": _("Nueva cotización")},
        ]
        return ctx

    def post(self, request):
        form = QuotationForm(organization=_org(request), data=request.POST)
        formset = InvoiceItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            quotation = form.save(commit=False)
            quotation.organization = _org(request)
            quotation.doc_type = Invoice.DocType.QUOTATION
            quotation.save()
            formset.instance = quotation
            formset.save()
            messages.success(request, _("Cotización creada como borrador."))
            return redirect("invoices:quotation_detail", pk=quotation.pk)

        ctx = self.get_context_data()
        ctx["form"] = form
        ctx["formset"] = formset
        return self.render_to_response(ctx)


class QuotationDetailView(ERPBaseViewMixin, DetailView):
    template_name = "invoices/quotation_detail.html"
    required_module = "invoices"
    context_object_name = "quotation"

    def get_object(self):
        return get_object_or_404(
            Invoice.quotations.select_related("customer", "organization"),
            pk=self.kwargs["pk"],
            organization=_org(self.request),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all()
        from .models import NCFType

        ctx["ncf_type_choices"] = NCFType.choices
        q = self.object
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Cotizaciones"), "url": reverse("invoices:quotation_list")},
            {"label": q.doc_number or str(_("Borrador"))},
        ]
        return ctx


class QuotationUpdateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/quotation_form.html"
    required_module = "invoices"

    def get_quotation(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=_org(request))
        if not q.is_editable:
            messages.error(
                request, _("Solo se pueden editar cotizaciones en Borrador.")
            )
            return None, redirect("invoices:quotation_detail", pk=q.pk)
        return q, None

    def get(self, request, pk):
        q, redir = self.get_quotation(request, pk)
        if redir:
            return redir
        ctx = self.get_context_data(
            form=QuotationForm(organization=_org(request), instance=q),
            formset=InvoiceItemFormSet(instance=q),
            quotation=q,
        )
        return self.render_to_response(ctx)

    def post(self, request, pk):
        q, redir = self.get_quotation(request, pk)
        if redir:
            return redir
        form = QuotationForm(organization=_org(request), data=request.POST, instance=q)
        formset = InvoiceItemFormSet(request.POST, instance=q)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Cotización actualizada."))
            return redirect("invoices:quotation_detail", pk=q.pk)
        ctx = self.get_context_data(form=form, formset=formset, quotation=q)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", QuotationForm(organization=_org(self.request)))
        ctx.setdefault("formset", InvoiceItemFormSet())
        ctx["sale_items_json"] = _sale_items_json(self.request)
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        q = kwargs.get("quotation")
        if q:
            ctx["breadcrumbs"] = [
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Cotizaciones"), "url": reverse("invoices:quotation_list")},
                {
                    "label": q.doc_number or str(_("Borrador")),
                    "url": reverse("invoices:quotation_detail", args=[q.pk]),
                },
                {"label": _("Editar")},
            ]
        return ctx


# ── Quotation transitions ─────────────────────────────────────────────────────


class QuotationConfirmView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=_org(request))
        try:
            QuotationService.confirm(q)
            messages.success(request, _(f"Cotización confirmada: {q.doc_number}"))
        except (ValueError, Exception) as exc:
            messages.error(request, str(exc))
        return redirect("invoices:quotation_detail", pk=q.pk)


class QuotationSendView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=_org(request))
        try:
            QuotationService.send(q)
            messages.success(request, _("Cotización marcada como enviada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:quotation_detail", pk=q.pk)


class QuotationAcceptView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=_org(request))
        try:
            QuotationService.accept(q)
            messages.success(request, _("Cotización marcada como aceptada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:quotation_detail", pk=q.pk)


class QuotationRejectView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=_org(request))
        try:
            QuotationService.reject(q)
            messages.success(request, _("Cotización marcada como rechazada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:quotation_detail", pk=q.pk)


class QuotationConvertView(ERPBaseViewMixin, View):
    """Convert an ACCEPTED quotation to a DRAFT Invoice."""

    required_module = "invoices"

    def post(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=_org(request))
        ncf_type = request.POST.get("ncf_type")
        if not ncf_type:
            messages.error(
                request, _("Debe seleccionar el tipo de comprobante fiscal.")
            )
            return redirect("invoices:quotation_detail", pk=q.pk)
        try:
            invoice = QuotationService.convert_to_invoice(q, int(ncf_type))
            messages.success(
                request,
                _("Cotización convertida. Factura borrador creada."),
            )
            return redirect("invoices:invoice_detail", pk=invoice.pk)
        except (ValueError, Exception) as exc:
            messages.error(request, str(exc))
            return redirect("invoices:quotation_detail", pk=q.pk)


class QuotationDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=_org(request))
        if q.status != Invoice.Status.DRAFT:
            messages.error(
                request, _("Solo se pueden eliminar cotizaciones en Borrador.")
            )
            return redirect("invoices:quotation_detail", pk=q.pk)
        q.hard_delete()
        messages.success(request, _("Cotización eliminada."))
        return redirect("invoices:quotation_list")


# ═════════════════════════════════════════════════════════════════════════════
#  SALE ORDER VIEWS
# ═════════════════════════════════════════════════════════════════════════════


class SaleOrderListView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/sale_order_list.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = (
            Invoice.sale_orders.filter(organization=_org(self.request))
            .select_related("customer", "department")
            .order_by("-delivery_date", "-created_at")
        )
        f = SaleOrderFilter(
            self.request.GET, queryset=qs, organization=_org(self.request)
        )
        ctx["filter"] = f
        ctx["orders"] = f.qs
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de venta")},
        ]
        return ctx


class SaleOrderCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/sale_order_form.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", SaleOrderForm(organization=_org(self.request)))
        ctx.setdefault("formset", InvoiceItemFormSet())
        ctx["sale_items_json"] = _sale_items_json(self.request)
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {
                "label": _("Órdenes de venta"),
                "url": reverse("invoices:sale_order_list"),
            },
            {"label": _("Nueva orden")},
        ]
        return ctx

    def post(self, request):
        form = SaleOrderForm(organization=_org(request), data=request.POST)
        formset = InvoiceItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            order = form.save(commit=False)
            order.organization = _org(request)
            order.doc_type = Invoice.DocType.SALE_ORDER
            order.save()
            formset.instance = order
            formset.save()
            messages.success(request, _("Orden de venta creada como borrador."))
            return redirect("invoices:sale_order_detail", pk=order.pk)

        ctx = self.get_context_data()
        ctx["form"] = form
        ctx["formset"] = formset
        return self.render_to_response(ctx)


class SaleOrderDetailView(ERPBaseViewMixin, DetailView):
    template_name = "invoices/sale_order_detail.html"
    required_module = "invoices"
    context_object_name = "order"

    def get_object(self):
        return get_object_or_404(
            Invoice.sale_orders.select_related(
                "customer", "organization", "consolidated_into", "department"
            ),
            pk=self.kwargs["pk"],
            organization=_org(self.request),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all()
        ctx["deliver_form"] = SaleOrderDeliverForm()
        o = self.object
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {
                "label": _("Órdenes de venta"),
                "url": reverse("invoices:sale_order_list"),
            },
            {"label": o.doc_number or str(_("Borrador"))},
        ]
        return ctx


class SaleOrderUpdateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/sale_order_form.html"
    required_module = "invoices"

    def get_order(self, request, pk):
        o = get_object_or_404(Invoice.sale_orders, pk=pk, organization=_org(request))
        if not o.is_editable:
            messages.error(request, _("Solo se pueden editar órdenes en Borrador."))
            return None, redirect("invoices:sale_order_detail", pk=o.pk)
        return o, None

    def get(self, request, pk):
        o, redir = self.get_order(request, pk)
        if redir:
            return redir
        ctx = self.get_context_data(
            form=SaleOrderForm(organization=_org(request), instance=o),
            formset=InvoiceItemFormSet(instance=o),
            order=o,
        )
        return self.render_to_response(ctx)

    def post(self, request, pk):
        o, redir = self.get_order(request, pk)
        if redir:
            return redir
        form = SaleOrderForm(organization=_org(request), data=request.POST, instance=o)
        formset = InvoiceItemFormSet(request.POST, instance=o)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Orden de venta actualizada."))
            return redirect("invoices:sale_order_detail", pk=o.pk)
        ctx = self.get_context_data(form=form, formset=formset, order=o)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", SaleOrderForm(organization=_org(self.request)))
        ctx.setdefault("formset", InvoiceItemFormSet())
        ctx["sale_items_json"] = _sale_items_json(self.request)
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        o = kwargs.get("order")
        if o:
            ctx["breadcrumbs"] = [
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {
                    "label": _("Órdenes de venta"),
                    "url": reverse("invoices:sale_order_list"),
                },
                {
                    "label": o.doc_number or str(_("Borrador")),
                    "url": reverse("invoices:sale_order_detail", args=[o.pk]),
                },
                {"label": _("Editar")},
            ]
        return ctx


# ── Sale Order transitions ────────────────────────────────────────────────────


class SaleOrderConfirmView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        o = get_object_or_404(Invoice.sale_orders, pk=pk, organization=_org(request))
        try:
            SaleOrderService.confirm(o)
            messages.success(request, _(f"Orden confirmada: {o.doc_number}"))
        except (ValueError, Exception) as exc:
            messages.error(request, str(exc))
        return redirect("invoices:sale_order_detail", pk=o.pk)


class SaleOrderDeliverView(ERPBaseViewMixin, View):
    """Mark a confirmed order as DELIVERED and record who signed."""

    required_module = "invoices"

    def post(self, request, pk):
        o = get_object_or_404(Invoice.sale_orders, pk=pk, organization=_org(request))
        form = SaleOrderDeliverForm(request.POST)
        if not form.is_valid():
            messages.error(
                request, _("Debe indicar el nombre de quien recibe la entrega.")
            )
            return redirect("invoices:sale_order_detail", pk=o.pk)
        try:
            SaleOrderService.mark_delivered(o, form.cleaned_data["signed_by"])
            messages.success(
                request,
                _(f"Orden marcada como entregada. Recibido por: {o.signed_by}"),
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:sale_order_detail", pk=o.pk)


class SaleOrderCancelView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        o = get_object_or_404(Invoice.sale_orders, pk=pk, organization=_org(request))
        try:
            SaleOrderService.cancel(o)
            messages.success(request, _("Orden de venta anulada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:sale_order_detail", pk=o.pk)


class SaleOrderDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        o = get_object_or_404(Invoice.sale_orders, pk=pk, organization=_org(request))
        if o.status != Invoice.Status.DRAFT:
            messages.error(request, _("Solo se pueden eliminar órdenes en Borrador."))
            return redirect("invoices:sale_order_detail", pk=o.pk)
        o.hard_delete()
        messages.success(request, _("Orden eliminada."))
        return redirect("invoices:sale_order_list")


# ── Consolidation ─────────────────────────────────────────────────────────────


class SaleOrderConsolidateView(ERPBaseViewMixin, TemplateView):
    """
    Two-step consolidation:
      GET  → show the ConsolidateForm
      POST → call SaleOrderService.consolidate_and_invoice(), redirect to new invoice
    HTMX GET with ?preview=1 → return the preview partial only
    """

    template_name = "invoices/sale_order_consolidate.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", ConsolidateForm(organization=_org(self.request)))
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {
                "label": _("Órdenes de venta"),
                "url": reverse("invoices:sale_order_list"),
            },
            {"label": _("Consolidar en factura")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        # HTMX preview request
        if request.htmx and request.GET.get("preview"):
            return self._render_preview(request)
        return self.render_to_response(self.get_context_data())

    def _render_preview(self, request):
        """Return the pending-orders preview table for the HTMX target."""
        customer_id = request.GET.get("customer", "").strip()
        department_id = request.GET.get("department", "").strip()
        start = request.GET.get("period_start")
        end = request.GET.get("period_end")

        orders = []
        grand_total = 0
        if customer_id and start and end:
            try:
                from datetime import datetime

                p_start = datetime.strptime(start, "%Y-%m-%d").date()
                p_end = datetime.strptime(end, "%Y-%m-%d").date()
                qs = (
                    Invoice.sale_orders.filter(
                        organization=_org(request),
                        customer_id=customer_id,
                        status=Invoice.Status.DELIVERED,
                        consolidated_into__isnull=True,
                        delivery_date__gte=p_start,
                        delivery_date__lte=p_end,
                    )
                    .select_related("customer", "department")
                    .order_by("delivery_date")
                )
                if department_id:
                    qs = qs.filter(department_id=department_id)
                orders = list(qs)
                grand_total = sum(o.total for o in orders)
            except (ValueError, TypeError):
                pass

        return render(
            request,
            "invoices/partials/consolidate_preview.html",
            {
                "orders": orders,
                "grand_total": grand_total,
            },
        )

    def post(self, request):
        form = ConsolidateForm(organization=_org(request), data=request.POST)
        if not form.is_valid():
            ctx = self.get_context_data()
            ctx["form"] = form
            return self.render_to_response(ctx)

        cd = form.cleaned_data
        try:
            invoice = SaleOrderService.consolidate_and_invoice(
                organization=_org(request),
                customer=cd["customer"],
                period_start=cd["period_start"],
                period_end=cd["period_end"],
                ncf_type=int(cd["ncf_type"]),
                department=cd.get("department"),
            )
            messages.success(
                request,
                _(f"Se generó la factura consolidada. Revise y confirme el e-NCF."),
            )
            return redirect("invoices:invoice_detail", pk=invoice.pk)
        except ValueError as exc:
            messages.error(request, str(exc))
            ctx = self.get_context_data()
            ctx["form"] = form
            return self.render_to_response(ctx)


# ── HTMX: department options for a customer ──────────────────────────────────


class CustomerDepartmentsView(ERPBaseViewMixin, View):
    """
    HTMX GET: return <option> tags for the selected customer's active departments.
    Used by SaleOrderForm's customer select to dynamically reload the department
    select when the customer changes.
    """

    required_module = "invoices"

    def get(self, request):
        customer_id = request.GET.get("customer", "").strip()
        departments = []
        if customer_id:
            departments = list(
                CustomerDepartment.objects.filter(
                    customer_id=customer_id,
                    organization=_org(request),
                    is_active=True,
                    deleted_at__isnull=True,
                ).order_by("name")
            )
        return render(
            request,
            "invoices/partials/department_options.html",
            {
                "departments": departments,
            },
        )


# ── HTMX: RNC / Cédula lookup ────────────────────────────────────────────────


class RNCLookupView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request):
        from .validators import lookup_name, _digits_only

        value = (request.GET.get("rnc_cedula") or "").strip()
        id_type = (request.GET.get("id_type") or "").strip()

        if not value:
            return HttpResponse("")

        digits = _digits_only(value)
        if id_type not in ("RNC", "CED") and len(digits) not in (9, 11):
            return HttpResponse("")

        name, source = lookup_name(value, id_type)

        resp = HttpResponse("")
        if name:
            resp["HX-Trigger"] = json.dumps(
                {"rncFound": {"name": name, "value": value}}
            )
        else:
            resp["HX-Trigger"] = json.dumps({"rncNotFound": {"value": value}})
        return resp


# ── HTMX: empty item row ──────────────────────────────────────────────────────


class InvoiceItemRowView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request):
        index = int(request.GET.get("form_index", 0))
        form = InvoiceItemForm(prefix=f"items-{index}")
        return render(
            request, "invoices/partials/item_row.html", {"form": form, "index": index}
        )


# ═════════════════════════════════════════════════════════════════════════════
#  NCF SEQUENCE MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════


class NCFSequenceListView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/ncf_sequence_list.html"
    required_module = "invoices"
    admin_required = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sequences"] = NCFSequence.objects.filter(
            organization=_org(self.request)
        ).order_by("ncf_type")
        ctx["form"] = NCFSequenceForm()
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Secuencias NCF")},
        ]
        return ctx

    def post(self, request):
        form = NCFSequenceForm(request.POST)
        if form.is_valid():
            seq = form.save(commit=False)
            seq.organization = _org(request)
            seq.save()
            messages.success(request, _("Secuencia NCF registrada."))
            return redirect("invoices:ncf_sequences")
        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class NCFSequenceUpdateView(ERPBaseViewMixin, UpdateView):
    form_class = NCFSequenceForm
    template_name = "invoices/ncf_sequence_form.html"
    required_module = "invoices"
    admin_required = True
    success_url = reverse_lazy("invoices:ncf_sequences")

    def get_object(self):
        return get_object_or_404(
            NCFSequence, pk=self.kwargs["pk"], organization=_org(self.request)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Secuencias NCF"), "url": reverse("invoices:ncf_sequences")},
            {"label": self.object.get_ncf_type_display()},
        ]
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _("Secuencia NCF actualizada."))
        return super().form_valid(form)


# ═════════════════════════════════════════════════════════════════════════════
#  DGII REPORTS  (Formatos 607 / 608)
# ═════════════════════════════════════════════════════════════════════════════


class ReportIndexView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/reports.html"
    required_module = "invoices"
    admin_required = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["today"] = timezone.now().date()
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Reportes DGII")},
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
            Invoice.invoices.filter(  # fiscal invoices only
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
            id_type_code = {"RNC": "1", "CED": "2", "PAS": "3", "EXT": "4"}.get(
                c.id_type, ""
            )
            buyer_id = c.rnc_cedula or ""
            buyer_type = id_type_code if buyer_id else ""
            encf_mod = inv.encf_modified.encf if inv.encf_modified else ""

            last_payment = inv.payments.order_by("-date").first()
            if last_payment:
                pay_code = self.PAYMENT_METHOD_CODE.get(last_payment.method, "06")
            else:
                pay_code = "07" if inv.payment_condition == "CREDIT" else "01"

            row = "|".join(
                [
                    buyer_id,
                    buyer_type,
                    inv.encf,
                    encf_mod,
                    str(inv.ncf_type),
                    inv.issue_date.strftime("%Y%m%d"),
                    "",
                    f"{inv.subtotal:.2f}",
                    f"{inv.itbis_total:.2f}",
                    "0.00",
                    pay_code,
                ]
            )
            buf.write(row + "\r\n")

        filename = f"607_{year}{month:02d}_{_org(request).slug}.txt"
        response = HttpResponse(
            buf.getvalue(), content_type="text/plain; charset=utf-8"
        )
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
            Invoice.invoices.filter(  # fiscal invoices only
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
            row = "|".join(
                [inv.encf, str(inv.ncf_type), inv.updated_at.strftime("%Y%m%d")]
            )
            buf.write(row + "\r\n")

        filename = f"608_{year}{month:02d}_{_org(request).slug}.txt"
        response = HttpResponse(
            buf.getvalue(), content_type="text/plain; charset=utf-8"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


# ── PDF ───────────────────────────────────────────────────────────────────────


class InvoicePDFView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer", "organization"),
            pk=pk,
            organization=_org(request),
        )
        if invoice.status == Invoice.Status.DRAFT:
            messages.warning(
                request,
                _("El PDF solo está disponible para documentos confirmados."),
            )
            return redirect("invoices:invoice_detail", pk=invoice.pk)

        try:
            from weasyprint import HTML as WeasyprintHTML
            from django.template.loader import render_to_string

            html_string = render_to_string(
                "invoices/invoice_pdf.html",
                {
                    "invoice": invoice,
                    "items": invoice.items.all(),
                    "org": invoice.organization,
                    "request": request,
                },
            )
            pdf_file = WeasyprintHTML(
                string=html_string, base_url=request.build_absolute_uri()
            ).write_pdf()
            filename = f"factura_{invoice.encf}.pdf"
            response = HttpResponse(pdf_file, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        except ImportError:
            messages.error(
                request,
                _(
                    "La generación de PDF requiere weasyprint. "
                    "Instálelo con: pip install weasyprint"
                ),
            )
            return redirect("invoices:invoice_detail", pk=invoice.pk)


class SaleOrderCloneView(ERPBaseViewMixin, View):
    """
    Clone any sale order into a new DRAFT with today's issue date.
    Copies header fields and all line items; clears delivery_date and signed_by.
    Redirects to the new order's edit page so the user can review before confirming.
    """

    required_module = "invoices"

    def post(self, request, pk):
        source = get_object_or_404(
            Invoice.objects.prefetch_related("items"),
            pk=pk,
            organization=_org(request),
            doc_type=Invoice.DocType.SALE_ORDER,
        )

        new_order = Invoice.objects.create(
            organization=source.organization,
            doc_type=Invoice.DocType.SALE_ORDER,
            status=Invoice.Status.DRAFT,
            customer=source.customer,
            department=source.department,
            issue_date=date.today(),
            payment_condition=source.payment_condition,
            currency=source.currency,
            exchange_rate=source.exchange_rate,
            notes=source.notes,
            terms=getattr(source, "terms", ""),
            # delivery_date and signed_by intentionally left blank
        )

        InvoiceItem.objects.bulk_create(
            [
                InvoiceItem(
                    invoice=new_order,
                    item=line.item,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    itbis_rate=line.itbis_rate,
                )
                for line in source.items.all()
            ]
        )

        messages.success(
            request,
            _("Orden clonada correctamente. Revise y confirme el nuevo borrador."),
        )
        return redirect("invoices:sale_order_edit", pk=new_order.pk)


class InvoicePrintView(ERPBaseViewMixin, View):
    """Browser-print HTML view for invoices (available for all statuses)."""

    required_module = "invoices"

    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer", "organization"),
            pk=pk,
            organization=_org(request),
            doc_type=Invoice.DocType.INVOICE,
        )
        return render(
            request,
            "invoices/invoice_print.html",
            {
                "invoice": invoice,
                "items": invoice.items.all(),
                "org": invoice.organization,
            },
        )


class QuotationPrintView(ERPBaseViewMixin, View):
    """Browser-print HTML view for quotations."""

    required_module = "invoices"

    def get(self, request, pk):
        quotation = get_object_or_404(
            Invoice.objects.select_related("customer", "organization"),
            pk=pk,
            organization=_org(request),
            doc_type=Invoice.DocType.QUOTATION,
        )
        return render(
            request,
            "invoices/quotation_print.html",
            {
                "quotation": quotation,
                "items": quotation.items.all(),
                "org": quotation.organization,
            },
        )


class SaleOrderPrintView(ERPBaseViewMixin, View):
    """Browser-print HTML view for sale orders."""

    required_module = "invoices"

    def get(self, request, pk):
        order = get_object_or_404(
            Invoice.objects.select_related("customer", "organization", "department"),
            pk=pk,
            organization=_org(request),
            doc_type=Invoice.DocType.SALE_ORDER,
        )
        return render(
            request,
            "invoices/sale_order_print.html",
            {
                "order": order,
                "items": order.items.all(),
                "org": order.organization,
            },
        )


# ── Payments ──────────────────────────────────────────────────────────────────


class PaymentListView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request):
        qs = (
            Payment.objects.filter(organization=_org(request))
            .select_related("customer")
            .prefetch_related("allocations__invoice")
            .order_by("-date", "-created_at")
        )
        f = PaymentFilter(request.GET, queryset=qs, organization=_org(request))
        total = sum(p.amount for p in f.qs)
        return render(
            request,
            "invoices/payment_list.html",
            {
                **self.get_context(
                    filter=f,
                    payments=f.qs,
                    total=total,
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Pagos")},
                    ],
                ),
            },
        )


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
        form = PaymentHeaderForm(
            organization=_org(request),
            initial={"date": date.today()},
        )
        return render(request, "invoices/payment_form.html", self._ctx(request, form))

    def post(self, request):
        form = PaymentHeaderForm(organization=_org(request), data=request.POST)

        if not form.is_valid():
            return render(
                request, "invoices/payment_form.html", self._ctx(request, form)
            )

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
            form.add_error(
                None, _("Seleccione al menos una factura y un monto mayor a cero.")
            )
            return render(
                request, "invoices/payment_form.html", self._ctx(request, form)
            )

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
            return render(
                request, "invoices/payment_form.html", self._ctx(request, form)
            )


class PaymentDetailView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("customer", "organization").prefetch_related(
                "allocations__invoice"
            ),
            pk=pk,
            organization=_org(request),
        )
        return render(
            request,
            "invoices/payment_detail.html",
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
    """
    HTMX endpoint: returns allocation row partials for all outstanding invoices
    of the selected customer.  Triggered by the customer <select> change in the
    payment form.
    """

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
                    paid_amount=Coalesce(
                        Sum("allocations__amount"), _zero, output_field=_dec
                    )
                )
                .order_by("due_date", "issue_date")
            )
            for inv in qs:
                inv.line_balance = inv.total - inv.paid_amount
            invoices = [inv for inv in qs if inv.line_balance > Decimal("0")]

        return render(
            request,
            "invoices/partials/payment_allocation_rows.html",
            {"invoices": invoices},
        )
