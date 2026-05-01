import csv
import io
from datetime import date

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, UpdateView, DetailView

from apps.accounts.views import ERPBaseViewMixin
from .filters import InvoiceFilter
from .forms import (
    CustomerForm, InvoiceForm, InvoiceItemFormSet,
    PaymentForm, CreditNoteForm, NCFSequenceForm,
)
from .models import Customer, Invoice, InvoiceItem, NCFSequence, Payment
from .services import NCFService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org(request):
    return request.organization


# ═════════════════════════════════════════════════════════════════════════════
#  CUSTOMER VIEWS
# ═════════════════════════════════════════════════════════════════════════════

class CustomerListView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/customer_list.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["customers"] = (
            Customer.objects
            .filter(organization=_org(self.request))
            .order_by("name")
        )
        ctx["form"] = CustomerForm()
        return ctx

    def post(self, request):
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.organization = _org(request)
            customer.save()
            if request.htmx:
                customers = Customer.objects.filter(organization=_org(request)).order_by("name")
                return render(request, "invoices/partials/customer_table.html",
                              {"customers": customers})
            messages.success(request, _("Cliente creado correctamente."))
            return redirect("invoices:customer_list")
        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class CustomerUpdateView(ERPBaseViewMixin, UpdateView):
    form_class = CustomerForm
    template_name = "invoices/customer_form.html"
    required_module = "invoices"
    success_url = reverse_lazy("invoices:customer_list")

    def get_object(self):
        return get_object_or_404(
            Customer, pk=self.kwargs["pk"], organization=_org(self.request)
        )

    def form_valid(self, form):
        messages.success(self.request, _("Cliente actualizado."))
        return super().form_valid(form)


class CustomerDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk, organization=_org(request))
        if customer.invoices.exists():
            messages.error(
                request,
                _("No se puede eliminar un cliente con facturas asociadas."),
            )
            return redirect("invoices:customer_list")
        name = customer.name
        customer.delete()
        messages.success(request, _(f"Cliente «{name}» eliminado."))
        return redirect("invoices:customer_list")


# ═════════════════════════════════════════════════════════════════════════════
#  INVOICE VIEWS
# ═════════════════════════════════════════════════════════════════════════════

class InvoiceListView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/invoice_list.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = (
            Invoice.objects
            .filter(organization=_org(self.request))
            .select_related("customer")
            .order_by("-issue_date", "-created_at")
        )
        f = InvoiceFilter(self.request.GET, queryset=qs, organization=_org(self.request))
        ctx["filter"] = f
        ctx["invoices"] = f.qs
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
        ctx["payments"] = self.object.payments.all()
        ctx["payment_form"] = PaymentForm(
            initial={"amount": self.object.total, "date": date.today()}
        )
        return ctx


class InvoiceCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/invoice_form.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", InvoiceForm(organization=_org(self.request)))
        ctx.setdefault("formset", InvoiceItemFormSet())
        return ctx

    def post(self, request):
        form = InvoiceForm(organization=_org(request), data=request.POST)
        formset = InvoiceItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.organization = _org(request)
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
                _("Esta factura ya fue confirmada y no puede editarse. "
                  "Emita una Nota de Crédito para corregirla."),
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
        form = InvoiceForm(organization=_org(request), data=request.POST, instance=invoice)
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
        return ctx


# ── Status transitions ────────────────────────────────────────────────────────

class InvoiceConfirmView(ERPBaseViewMixin, View):
    """Assign e-NCF and transition DRAFT → CONFIRMED."""
    required_module = "invoices"

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, organization=_org(request))
        try:
            NCFService.confirm(invoice)
            messages.success(
                request,
                _(f"Factura confirmada. e-NCF asignado: {invoice.encf}"),
            )
        except (ValueError, Exception) as exc:
            messages.error(request, str(exc))
        return redirect("invoices:invoice_detail", pk=invoice.pk)


class InvoiceSendView(ERPBaseViewMixin, View):
    """Transition CONFIRMED → SENT (email dispatch handled separately)."""
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
    """Register a payment and transition to PAID."""
    required_module = "invoices"

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, organization=_org(request))
        form = PaymentForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Por favor corrija los errores en el formulario de pago."))
            return redirect("invoices:invoice_detail", pk=invoice.pk)

        payment = form.save(commit=False)
        payment.invoice = invoice
        payment.organization = _org(request)
        payment.save()

        try:
            NCFService.mark_paid(invoice, payment)
            messages.success(request, _("Pago registrado. Factura marcada como pagada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:invoice_detail", pk=invoice.pk)


class InvoiceCancelView(ERPBaseViewMixin, View):
    """Annul an invoice. The e-NCF goes to format 608."""
    required_module = "invoices"
    admin_required = True

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, organization=_org(request))
        try:
            NCFService.cancel(invoice)
            messages.success(
                request,
                _(f"Factura {invoice.encf or invoice.pk} anulada. "
                  "Recuerde incluirla en el formato 608 de este período."),
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:invoice_detail", pk=invoice.pk)


class InvoiceDeleteView(ERPBaseViewMixin, View):
    """Hard-delete a DRAFT invoice (no e-NCF assigned yet)."""
    required_module = "invoices"
    admin_required = True

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, organization=_org(request))
        if invoice.status != Invoice.Status.DRAFT:
            messages.error(request, _("Solo se pueden eliminar facturas en estado Borrador."))
            return redirect("invoices:invoice_detail", pk=invoice.pk)
        invoice.hard_delete()
        messages.success(request, _("Borrador eliminado."))
        return redirect("invoices:invoice_list")


# ── Credit / Debit Note ───────────────────────────────────────────────────────

class CreditNoteCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/credit_note_form.html"
    required_module = "invoices"

    def get_original(self, request, pk):
        return get_object_or_404(
            Invoice,
            pk=pk,
            organization=_org(request),
        )

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
            note.currency = original.currency
            note.exchange_rate = original.exchange_rate
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
        return ctx


# ── HTMX: RNC / Cédula lookup ────────────────────────────────────────────────

class RNCLookupView(ERPBaseViewMixin, View):
    """
    HTMX endpoint: look up the registered name for an RNC or Cédula.

    GET params:
        rnc_cedula  — the raw value typed by the user
        id_type     — "RNC" | "CED" | "PAS" | "EXT"

    Returns an HTML partial that either:
      - auto-fills the name field (Alpine.js) when the name field is empty
      - shows a suggestion badge with a "Usar" button when the field already
        has a value
    """
    required_module = "invoices"

    def get(self, request):
        import json
        from .validators import lookup_name, _digits_only

        value   = (request.GET.get("rnc_cedula") or "").strip()
        id_type = (request.GET.get("id_type") or "").strip()

        if not value:
            return HttpResponse("")

        digits = _digits_only(value)
        if id_type not in ("RNC", "CED") and len(digits) not in (9, 11):
            return HttpResponse("")

        name, source = lookup_name(value, id_type)

        resp = HttpResponse("")
        if name:
            resp["HX-Trigger"] = json.dumps({"rncFound": {"name": name, "value": value}})
        else:
            resp["HX-Trigger"] = json.dumps({"rncNotFound": {"value": value}})
        return resp


# ── HTMX: empty item row ──────────────────────────────────────────────────────

class InvoiceItemRowView(ERPBaseViewMixin, View):
    """
    Returns an empty InvoiceItem form row for HTMX dynamic formset expansion.
    The client must supply ?form_index=N in the query string.
    """
    required_module = "invoices"

    def get(self, request):
        index = int(request.GET.get("form_index", 0))
        formset = InvoiceItemFormSet(prefix="items")
        form = InvoiceItemForm(prefix=f"items-{index}")
        return render(request, "invoices/partials/item_row.html",
                      {"form": form, "index": index})


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
        return ctx


class Report607View(ERPBaseViewMixin, View):
    """
    Generate Formato 607 (Ventas de Bienes y Servicios).
    Pipe-delimited TXT compatible with the DGII's Oficina Virtual.

    Fields (per DGII Norma General 07-18):
      RNC/Cédula | Tipo ID | e-NCF | NCF modificado | Tipo ingreso |
      Fecha comprobante | Fecha retención | Monto facturado |
      ITBIS facturado | ITBIS retenido | Tipo pago
    """
    required_module = "invoices"
    admin_required = True

    # DGII payment method codes
    PAYMENT_METHOD_CODE = {
        "CASH":     "01",
        "CHECK":    "02",
        "CARD":     "03",
        "TRANSFER": "04",
        "SWAP":     "05",
        "OTHER":    "06",
        "CREDIT":   "07",
    }

    def get(self, request):
        month = request.GET.get("month")
        year  = request.GET.get("year")
        if not (month and year):
            messages.error(request, _("Debe seleccionar mes y año."))
            return redirect("invoices:reports")

        month, year = int(month), int(year)
        invoices = (
            Invoice.objects
            .filter(
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
            # Type ID: 1=RNC, 2=Cédula, 3=Pasaporte, 4=Extranjero, empty=consumidor final
            id_type_code = {"RNC": "1", "CED": "2", "PAS": "3", "EXT": "4"}.get(c.id_type, "")

            # For Consumo invoices under RD$250,000, buyer ID is optional
            buyer_id   = c.rnc_cedula or ""
            buyer_type = id_type_code if buyer_id else ""

            # NCF modificado
            encf_mod = inv.encf_modified.encf if inv.encf_modified else ""

            # Payment method from latest payment, fallback to payment_condition
            last_payment = inv.payments.order_by("-date").first()
            if last_payment:
                pay_code = self.PAYMENT_METHOD_CODE.get(last_payment.method, "06")
            else:
                pay_code = "07" if inv.payment_condition == "CREDIT" else "01"

            row = "|".join([
                buyer_id,
                buyer_type,
                inv.encf,
                encf_mod,
                str(inv.ncf_type),
                inv.issue_date.strftime("%Y%m%d"),
                "",                                     # fecha retención (no aplica ventas)
                f"{inv.subtotal:.2f}",
                f"{inv.itbis_total:.2f}",
                "0.00",                                 # ITBIS retenido (typically 0 on sales)
                pay_code,
            ])
            buf.write(row + "\r\n")

        filename = f"607_{year}{month:02d}_{_org(request).slug}.txt"
        response = HttpResponse(buf.getvalue(), content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class Report608View(ERPBaseViewMixin, View):
    """
    Generate Formato 608 (Comprobantes Anulados).

    Fields:
      e-NCF | Tipo | Fecha anulación
    """
    required_module = "invoices"
    admin_required = True

    def get(self, request):
        month = request.GET.get("month")
        year  = request.GET.get("year")
        if not (month and year):
            messages.error(request, _("Debe seleccionar mes y año."))
            return redirect("invoices:reports")

        month, year = int(month), int(year)
        cancelled = (
            Invoice.objects
            .filter(
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
            row = "|".join([
                inv.encf,
                str(inv.ncf_type),
                inv.updated_at.strftime("%Y%m%d"),
            ])
            buf.write(row + "\r\n")

        filename = f"608_{year}{month:02d}_{_org(request).slug}.txt"
        response = HttpResponse(buf.getvalue(), content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


# ── PDF ───────────────────────────────────────────────────────────────────────

class InvoicePDFView(ERPBaseViewMixin, View):
    """
    Render invoice as PDF using weasyprint.
    Falls back gracefully if weasyprint is not installed.
    """
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
                _("El PDF solo está disponible para facturas confirmadas."),
            )
            return redirect("invoices:invoice_detail", pk=invoice.pk)

        try:
            from weasyprint import HTML as WeasyprintHTML
            from django.template.loader import render_to_string

            html_string = render_to_string(
                "invoices/invoice_pdf.html",
                {
                    "invoice": invoice,
                    "items":   invoice.items.all(),
                    "org":     invoice.organization,
                    "request": request,
                },
            )
            pdf_file = WeasyprintHTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
            filename = f"factura_{invoice.encf}.pdf"
            response = HttpResponse(pdf_file, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        except ImportError:
            messages.error(
                request,
                _("La generación de PDF requiere weasyprint. "
                  "Instálelo con: pip install weasyprint"),
            )
            return redirect("invoices:invoice_detail", pk=invoice.pk)
