import json
from datetime import date

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, UpdateView, DetailView

from apps.accounts.views import ERPBaseViewMixin
from ..filters import InvoiceFilter
from ..forms import (
    InvoiceForm, InvoiceItemForm, InvoiceItemFormSet,
    PaymentForm, CreditNoteForm, NCFSequenceForm,
)
from ..models import Invoice, InvoiceItem, NCFSequence, Payment, PaymentAllocation
from ..services import NCFService
from ._helpers import _org, _active_filter_count, _sale_items_json, _customer_defaults_json


class InvoiceListView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/invoice_list.html"
    required_module = "invoices"

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "invoices/partials/invoice_table.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        from django.db.models import Q
        ctx = super().get_context_data(**kwargs)
        qs = (
            Invoice.invoices.filter(organization=_org(self.request))
            .select_related("customer")
            .order_by("-issue_date", "-created_at")
        )
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(encf__icontains=q) | Q(customer__name__icontains=q))
        f = InvoiceFilter(self.request.GET, queryset=qs, organization=_org(self.request))
        ctx["filter"] = f
        ctx["invoices"] = f.qs
        ctx["active_filter_count"] = _active_filter_count(self.request)
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
        ctx["allocations"] = self.object.allocations.select_related("payment").order_by("payment__date")
        ctx["payment_form"] = PaymentForm(initial={"amount": self.object.total, "date": date.today()})
        ctx["consolidated_orders"] = (
            self.object.consolidated_orders.select_related("customer").order_by("delivery_date")
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

    def _get_invoice(self, request, pk):
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
        invoice, redir = self._get_invoice(request, pk)
        if redir:
            return redir
        ctx = self.get_context_data(
            form=InvoiceForm(organization=_org(request), instance=invoice),
            formset=InvoiceItemFormSet(instance=invoice),
            invoice=invoice,
        )
        return self.render_to_response(ctx)

    def post(self, request, pk):
        invoice, redir = self._get_invoice(request, pk)
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
            messages.success(request, _(f"Factura confirmada. e-NCF asignado: {invoice.encf}"))
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
    required_module = "invoices"

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk, organization=_org(request))
        form = PaymentForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Por favor corrija los errores en el formulario de pago."))
            return redirect("invoices:invoice_detail", pk=invoice.pk)

        payment = form.save(commit=False)
        payment.customer = invoice.customer
        payment.organization = _org(request)
        payment.save()

        PaymentAllocation.objects.create(payment=payment, invoice=invoice, amount=payment.amount)

        try:
            NCFService.mark_paid(invoice)
            messages.success(request, _("Pago registrado. Factura marcada como pagada."))
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
                _(f"Factura {invoice.encf or invoice.pk} anulada. "
                  "Recuerde incluirla en el formato 608 de este período."),
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
            messages.error(request, _("Solo se pueden eliminar documentos en estado Borrador."))
            return redirect("invoices:invoice_detail", pk=invoice.pk)
        invoice.hard_delete()
        messages.success(request, _("Borrador eliminado."))
        return redirect("invoices:invoice_list")


# ── Credit / Debit Note ───────────────────────────────────────────────────────


class CreditNoteCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/credit_note_form.html"
    required_module = "invoices"

    def _get_original(self, request, pk):
        return get_object_or_404(Invoice, pk=pk, organization=_org(request))

    def get(self, request, pk):
        original = self._get_original(request, pk)
        form = CreditNoteForm(initial={"issue_date": date.today(), "ncf_type": 4})
        formset = InvoiceItemFormSet()
        ctx = self.get_context_data(form=form, formset=formset, original=original)
        return self.render_to_response(ctx)

    def post(self, request, pk):
        original = self._get_original(request, pk)
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


# ── PDF / Print ───────────────────────────────────────────────────────────────


class InvoicePDFView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer", "organization"),
            pk=pk, organization=_org(request),
        )
        if invoice.status == Invoice.Status.DRAFT:
            messages.warning(request, _("El PDF solo está disponible para documentos confirmados."))
            return redirect("invoices:invoice_detail", pk=invoice.pk)

        try:
            from weasyprint import HTML as WeasyprintHTML
            from django.template.loader import render_to_string

            html_string = render_to_string(
                "invoices/invoice_pdf.html",
                {"invoice": invoice, "items": invoice.items.all(), "org": invoice.organization, "request": request},
            )
            pdf_file = WeasyprintHTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()
            filename = f"factura_{invoice.encf}.pdf"
            response = HttpResponse(pdf_file, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except ImportError:
            messages.error(
                request,
                _("La generación de PDF requiere weasyprint. Instálelo con: pip install weasyprint"),
            )
            return redirect("invoices:invoice_detail", pk=invoice.pk)


class InvoicePrintView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related("customer", "organization"),
            pk=pk, organization=_org(request), doc_type=Invoice.DocType.INVOICE,
        )
        return render(
            request, "invoices/invoice_print.html",
            {"invoice": invoice, "items": invoice.items.all(), "org": invoice.organization},
        )


# ── NCF Sequences ─────────────────────────────────────────────────────────────


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
        return get_object_or_404(NCFSequence, pk=self.kwargs["pk"], organization=_org(self.request))

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


class NCFSequenceDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def post(self, request, pk):
        seq = get_object_or_404(NCFSequence, pk=pk, organization=_org(request))
        label = seq.get_ncf_type_display()
        seq.delete()
        messages.success(request, _(f"Secuencia NCF «{label}» eliminada."))
        return redirect("invoices:ncf_sequences")


# ── HTMX helpers ──────────────────────────────────────────────────────────────


class InvoiceItemRowView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request):
        index = int(request.GET.get("form_index", 0))
        form = InvoiceItemForm(prefix=f"items-{index}")
        return render(request, "invoices/partials/item_row.html", {"form": form, "index": index})


class RNCLookupView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request):
        import json as _json
        from ..validators import lookup_name, _digits_only

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
            resp["HX-Trigger"] = _json.dumps({"rncFound": {"name": name, "value": value}})
        else:
            resp["HX-Trigger"] = _json.dumps({"rncNotFound": {"value": value}})
        return resp
