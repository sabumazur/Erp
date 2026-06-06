import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, UpdateView, DetailView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.mixins import HistoryMixin
from apps.core.datatable import DTColumn, DataTableMixin
from apps.core.search import fts_search
from ..filters import InvoiceFilter
from ..forms import (
    InvoiceForm, InvoiceItemForm, InvoiceItemFormSet, InvoiceItemFormSetCreate,
    PaymentForm, CreditNoteForm, NCFSequenceForm,
)
from ..models import SalesDocument, SalesDocumentItem, NCFSequence, Payment
from ..email import send_invoice_email, _signature_url
from ..services import NCFService, PaymentService
from ..signals import suspend_recompute
from ._helpers import _customer_defaults_json


class InvoiceListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "sales/invoice_list.html"
    required_module = "sales"

    dt_columns = [
        DTColumn("encf",          _("e-NCF"),   sortable=True),
        DTColumn("customer__name",_("Cliente"), sortable=True),
        DTColumn("issue_date",    _("Fecha"),   sortable=True),
        DTColumn("due_date",      _("Vence"),   sortable=True),
        DTColumn("total",         _("Total"),   sortable=True, numeric=True),
        DTColumn("status",        _("Estado"),  sortable=False, classes="text-center"),
    ]
    dt_default_sort = "-issue_date"
    dt_url = "sales:invoice_list"
    dt_row_template = "sales/partials/invoice_row.html"
    dt_filter_template = "sales/partials/invoice_filters.html"
    dt_ribbon_template = "sales/partials/invoice_ribbon.html"
    dt_search_placeholder = _("e-NCF o cliente…")
    dt_id = "invoices"

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.request.organization
        qs = SalesDocument.invoices.filter(organization=org).select_related("customer")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["customer__name"], trgm_fields=["encf"])
        f = InvoiceFilter(self.request.GET, queryset=qs, organization=org)
        ctx["filter"] = f
        org_qs = SalesDocument.invoices.filter(organization=org)
        ctx.update(self.apply_datatable(f.qs))

        if not self.request.htmx:
            today = date.today()
            month_qs = org_qs.filter(
                issue_date__year=today.year, issue_date__month=today.month,
            )
            ctx["stats"] = [
                {"label": _("Total facturas"), "value": org_qs.count(),
                 "icon": "bi-receipt", "color": "primary"},
                {"label": _("Facturado este mes"),
                 "value": "{:,.2f}".format(month_qs.aggregate(t=Sum("total"))["t"] or 0),
                 "icon": "bi-cash-stack", "color": "success", "currency": "RD$"},
                {"label": _("Por cobrar"),
                 "value": "{:,.2f}".format(
                     org_qs.filter(status__in=["CONFIRMED", "SENT", "OVERDUE"])
                     .aggregate(t=Sum("total"))["t"] or 0),
                 "icon": "bi-hourglass-split", "color": "warning", "currency": "RD$"},
                {"label": _("Vencidas"), "value": org_qs.filter(status="OVERDUE").count(),
                 "icon": "bi-exclamation-circle", "color": "danger"},
            ]

        ctx["module"] = "invoice"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Facturas")},
        ]
        return ctx


class InvoiceDetailView(HistoryMixin, ERPBaseViewMixin, DetailView):
    template_name = "sales/invoice_detail.html"
    required_module = "sales"
    context_object_name = "invoice"

    def get_object(self):
        return get_object_or_404(
            SalesDocument.objects.select_related("customer", "organization", "encf_modified"),
            pk=self.kwargs["pk"], doc_type=SalesDocument.DocType.INVOICE,
            organization=self.request.organization,
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
        ctx["module"] = "invoice"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Facturas"), "url": reverse("sales:invoice_list")},
            {"label": invoice.doc_number or invoice.encf or str(_("Borrador"))},
        ]
        ctx["history_records"] = self.get_history(self.object)
        return ctx


class InvoiceCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "sales/invoice_form.html"
    required_module = "sales"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", InvoiceForm(organization=self.request.organization))
        ctx.setdefault("formset", InvoiceItemFormSetCreate(form_kwargs={"organization": self.request.organization}))
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        ctx["module"] = "invoice"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Facturas"), "url": reverse("sales:invoice_list")},
            {"label": _("Nueva factura")},
        ]
        return ctx

    def post(self, request):
        form = InvoiceForm(organization=request.organization, data=request.POST)
        formset = InvoiceItemFormSet(request.POST, form_kwargs={"organization": request.organization})
        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.organization = request.organization
            invoice.doc_type = SalesDocument.DocType.INVOICE
            invoice.save()
            formset.instance = invoice
            with suspend_recompute(invoice):
                formset.save()
            messages.success(request, _("Factura creada como borrador."))
            return redirect("sales:invoice_detail", pk=invoice.pk)
        ctx = self.get_context_data()
        ctx["form"] = form
        ctx["formset"] = formset
        return self.render_to_response(ctx)


class InvoiceUpdateView(ERPBaseViewMixin, TemplateView):
    template_name = "sales/invoice_form.html"
    required_module = "sales"

    def _get_invoice(self, request, pk):
        invoice = get_object_or_404(SalesDocument.invoices, pk=pk, organization=request.organization)
        if not invoice.is_editable:
            messages.error(
                request,
                _("Esta factura ya fue confirmada y no puede editarse. "
                  "Emita una Nota de Crédito para corregirla."),
            )
            return None, redirect("sales:invoice_detail", pk=invoice.pk)
        return invoice, None

    def get(self, request, pk):
        invoice, redir = self._get_invoice(request, pk)
        if redir:
            return redir
        ctx = self.get_context_data(
            form=InvoiceForm(organization=request.organization, instance=invoice),
            formset=InvoiceItemFormSet(instance=invoice, form_kwargs={"organization": request.organization}),
            invoice=invoice,
        )
        return self.render_to_response(ctx)

    def post(self, request, pk):
        invoice, redir = self._get_invoice(request, pk)
        if redir:
            return redir
        form = InvoiceForm(organization=request.organization, data=request.POST, instance=invoice)
        formset = InvoiceItemFormSet(request.POST, instance=invoice, form_kwargs={"organization": request.organization})
        if form.is_valid() and formset.is_valid():
            form.save()
            with suspend_recompute(invoice):
                formset.save()
            messages.success(request, _("Factura actualizada."))
            return redirect("sales:invoice_detail", pk=invoice.pk)
        ctx = self.get_context_data(form=form, formset=formset, invoice=invoice)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", InvoiceForm(organization=self.request.organization))
        ctx.setdefault("formset", InvoiceItemFormSet(form_kwargs={"organization": self.request.organization}))
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        ctx["module"] = "invoice"
        invoice = kwargs.get("invoice")
        if invoice:
            ctx["breadcrumbs"] = [
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Facturas"), "url": reverse("sales:invoice_list")},
                {
                    "label": invoice.doc_number or str(_("Borrador")),
                    "url": reverse("sales:invoice_detail", args=[invoice.pk]),
                },
                {"label": _("Editar")},
            ]
        return ctx


# ── Invoice status transitions ────────────────────────────────────────────────


class InvoiceConfirmView(ERPBaseViewMixin, View):
    required_module = "sales"

    def post(self, request, pk):
        invoice = get_object_or_404(SalesDocument.invoices, pk=pk, organization=request.organization)
        try:
            NCFService.confirm(invoice)
            messages.success(request, _(f"Factura confirmada. e-NCF asignado: {invoice.encf}"))
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("sales:invoice_detail", pk=invoice.pk)


class InvoiceSendView(ERPBaseViewMixin, View):
    required_module = "sales"

    def post(self, request, pk):
        invoice = get_object_or_404(SalesDocument.invoices, pk=pk, organization=request.organization)
        try:
            NCFService.mark_sent(invoice)
            messages.success(request, _("Factura marcada como enviada."))
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("sales:invoice_detail", pk=invoice.pk)
        try:
            sent = send_invoice_email(invoice, request)
            if sent:
                messages.info(request, _("Correo enviado a %(email)s.") % {"email": invoice.customer.email})
            else:
                messages.warning(request, _("El cliente no tiene correo registrado."))
        except Exception as exc:
            messages.warning(request, _("No se pudo enviar el correo: %(error)s") % {"error": str(exc)})
        return redirect("sales:invoice_detail", pk=invoice.pk)


class InvoicePayView(ERPBaseViewMixin, View):
    required_module = "sales"

    def post(self, request, pk):
        invoice = get_object_or_404(SalesDocument.invoices, pk=pk, organization=request.organization)
        form = PaymentForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Por favor corrija los errores en el formulario de pago."))
            return redirect("sales:invoice_detail", pk=invoice.pk)

        cd = form.cleaned_data
        try:
            PaymentService.register(
                organization=request.organization,
                customer=invoice.customer,
                payment_date=cd["date"],
                method=cd["method"],
                reference=cd.get("reference", ""),
                notes=cd.get("notes", ""),
                allocations=[{"invoice": invoice, "amount": cd["amount"]}],
            )
            messages.success(request, _("Pago registrado. Factura marcada como pagada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("sales:invoice_detail", pk=invoice.pk)


class InvoiceCancelView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def post(self, request, pk):
        invoice = get_object_or_404(SalesDocument.invoices, pk=pk, organization=request.organization)
        try:
            NCFService.cancel(invoice)
            messages.success(
                request,
                _(f"Factura {invoice.encf or invoice.pk} anulada. "
                  "Recuerde incluirla en el formato 608 de este período."),
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("sales:invoice_detail", pk=invoice.pk)


class InvoiceDeleteView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def post(self, request, pk):
        invoice = get_object_or_404(SalesDocument.invoices, pk=pk, organization=request.organization)
        if invoice.status != SalesDocument.Status.DRAFT:
            messages.error(request, _("Solo se pueden eliminar documentos en estado Borrador."))
            return redirect("sales:invoice_detail", pk=invoice.pk)
        invoice.hard_delete()
        messages.success(request, _("Borrador eliminado."))
        return redirect("sales:invoice_list")


# ── Credit / Debit Note ───────────────────────────────────────────────────────


class CreditNoteCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "sales/credit_note_form.html"
    required_module = "sales"

    def _get_original(self, request, pk):
        return get_object_or_404(
            SalesDocument.invoices.filter(
                status__in=[
                    SalesDocument.Status.CONFIRMED,
                    SalesDocument.Status.SENT,
                    SalesDocument.Status.PAID,
                    SalesDocument.Status.OVERDUE,
                ],
            ).exclude(ncf_type__in=SalesDocument.NOTE_TYPES).exclude(encf=""),
            pk=pk,
            organization=request.organization,
        )

    def get(self, request, pk):
        original = self._get_original(request, pk)
        form = CreditNoteForm(initial={"issue_date": date.today(), "ncf_type": 4})
        formset = InvoiceItemFormSet(form_kwargs={"organization": request.organization})
        ctx = self.get_context_data(form=form, formset=formset, original=original)
        return self.render_to_response(ctx)

    def post(self, request, pk):
        original = self._get_original(request, pk)
        note = SalesDocument(
            organization=request.organization,
            customer=original.customer,
            encf_modified=original,
            doc_type=SalesDocument.DocType.INVOICE,
            payment_condition=original.payment_condition,
        )
        form = CreditNoteForm(request.POST, instance=note)
        formset = InvoiceItemFormSet(request.POST, form_kwargs={"organization": request.organization})
        if form.is_valid() and formset.is_valid():
            note = form.save(commit=False)
            note.save()
            formset.instance = note
            with suspend_recompute(note):
                formset.save()
            messages.success(request, _("Nota de Crédito/Débito creada como borrador."))
            return redirect("sales:invoice_detail", pk=note.pk)
        ctx = self.get_context_data(form=form, formset=formset, original=original)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", CreditNoteForm())
        ctx.setdefault("formset", InvoiceItemFormSet(form_kwargs={"organization": self.request.organization}))
        ctx["module"] = "invoice"
        original = kwargs.get("original")
        if original:
            ctx["breadcrumbs"] = [
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Facturas"), "url": reverse("sales:invoice_list")},
                {
                    "label": original.doc_number or str(_("Borrador")),
                    "url": reverse("sales:invoice_detail", args=[original.pk]),
                },
                {"label": _("Nota de crédito/débito")},
            ]
        return ctx


# ── PDF / Print ───────────────────────────────────────────────────────────────


class InvoicePDFView(ERPBaseViewMixin, View):
    required_module = "sales"

    def get(self, request, pk):
        invoice = get_object_or_404(
            SalesDocument.objects.select_related("customer", "organization"),
            pk=pk, organization=request.organization, doc_type=SalesDocument.DocType.INVOICE,
        )
        if invoice.status == SalesDocument.Status.DRAFT:
            messages.warning(request, _("El PDF solo está disponible para documentos confirmados."))
            return redirect("sales:invoice_detail", pk=invoice.pk)

        try:
            from weasyprint import HTML as WeasyprintHTML
            from django.template.loader import render_to_string

            html_string = render_to_string(
                "sales/invoice_pdf.html",
                {
                    "invoice": invoice,
                    "items": invoice.items.all(),
                    "org": invoice.organization,
                    "request": request,
                    "sender_signature_url": _signature_url(request.user, request),
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
                _("La generación de PDF requiere weasyprint. Instálelo con: pip install weasyprint"),
            )
            return redirect("sales:invoice_detail", pk=invoice.pk)


class InvoicePrintView(ERPBaseViewMixin, View):
    required_module = "sales"

    def get(self, request, pk):
        invoice = get_object_or_404(
            SalesDocument.objects.select_related("customer", "organization"),
            pk=pk, organization=request.organization, doc_type=SalesDocument.DocType.INVOICE,
        )
        return render(
            request, "sales/invoice_print.html",
            {
                "invoice": invoice,
                "items": invoice.items.all(),
                "org": invoice.organization,
                "sender_signature_url": _signature_url(request.user, request),
            },
        )


# ── NCF Sequences ─────────────────────────────────────────────────────────────


class NCFSequenceListView(ERPBaseViewMixin, TemplateView):
    template_name = "sales/ncf_sequence_list.html"
    required_module = "sales"
    admin_required = True

    def _sequences(self, request):
        return NCFSequence.objects.filter(organization=request.organization).order_by("ncf_type")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sequences"] = self._sequences(self.request)
        ctx["form"] = NCFSequenceForm(organization=self.request.organization)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Secuencias NCF")},
        ]
        return ctx

    def post(self, request):
        form = NCFSequenceForm(request.POST, organization=request.organization)
        if form.is_valid():
            seq = form.save(commit=False)
            seq.organization = request.organization
            try:
                seq.save()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                if request.htmx:
                    resp = render(
                        request,
                        "sales/partials/ncf_sequence_table.html",
                        {"sequences": self._sequences(request)},
                    )
                    resp["HX-Trigger"] = json.dumps(
                        {"showToast": {"message": str(_("Secuencia NCF registrada.")), "type": "success"}}
                    )
                    return resp
                messages.success(request, _("Secuencia NCF registrada."))
                return redirect("sales:ncf_sequences")

        if request.htmx:
            resp = render(
                request,
                "sales/partials/ncf_sequence_modal_form.html",
                {"form": form, "action_url": reverse("sales:ncf_sequences")},
            )
            resp["HX-Retarget"] = "#ncf-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class NCFSequenceUpdateView(ERPBaseViewMixin, UpdateView):
    form_class = NCFSequenceForm
    template_name = "sales/ncf_sequence_form.html"
    required_module = "sales"
    admin_required = True
    success_url = reverse_lazy("sales:ncf_sequences")

    def get_object(self):
        return get_object_or_404(NCFSequence, pk=self.kwargs["pk"], organization=self.request.organization)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Secuencias NCF"), "url": reverse("sales:ncf_sequences")},
            {"label": self.object.get_ncf_type_display()},
        ]
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _("Secuencia NCF actualizada."))
        return super().form_valid(form)


class NCFSequenceDeleteView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def post(self, request, pk):
        seq = get_object_or_404(NCFSequence, pk=pk, organization=request.organization)
        label = seq.get_ncf_type_display()
        try:
            seq.delete()
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect("sales:ncf_sequences")
        messages.success(request, _(f"Secuencia NCF «{label}» eliminada."))
        return redirect("sales:ncf_sequences")


# ── HTMX helpers ──────────────────────────────────────────────────────────────


class InvoiceItemRowView(ERPBaseViewMixin, View):
    required_module = "sales"

    def get(self, request):
        index = int(request.GET.get("form_index", 0))
        form = InvoiceItemForm(prefix=f"items-{index}", organization=request.organization)
        return render(request, "components/_line_item_row.html", {"form": form})


class RNCLookupView(ERPBaseViewMixin, View):
    required_module = "sales"

    def get(self, request):
        import json as _json
        from django.core.cache import cache
        from ..validators import lookup_name, _digits_only

        value = (request.GET.get("rnc_cedula") or "").strip()
        id_type = (request.GET.get("id_type") or "").strip()

        if not value:
            return HttpResponse("")

        digits = _digits_only(value)
        if id_type not in ("RNC", "CED") and len(digits) not in (9, 11):
            return HttpResponse("")

        # DGII records are stable — cache successful lookups for 24 hours so
        # repeated lookups of the same RNC/cédula skip the external API call.
        cache_key = f"rnc_lookup:{digits}"
        cached = cache.get(cache_key)
        if cached is not None:
            name, source = cached
        else:
            name, source = lookup_name(value, id_type)
            if name:
                cache.set(cache_key, (name, source), timeout=86400)

        resp = HttpResponse("")
        payload = {"value": value, "normalized_value": digits}
        if name:
            resp["HX-Trigger"] = _json.dumps({"rncFound": {"name": name, **payload}})
        else:
            resp["HX-Trigger"] = _json.dumps({"rncNotFound": payload})
        return resp
