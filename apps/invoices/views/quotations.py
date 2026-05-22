from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, DetailView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.mixins import HistoryMixin
from apps.core.datatable import DTColumn, DataTableMixin
from apps.core.search import fts_search
from ..filters import QuotationFilter
from ..forms import QuotationForm, InvoiceItemFormSet
from ..models import Invoice, NCFType
from ..email import send_quotation_email, _signature_url
from ..services import QuotationService
from ._helpers import _customer_defaults_json


class QuotationListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "invoices/quotation_list.html"
    required_module = "invoices"

    dt_columns = [
        DTColumn("doc_number",    _("Número"),      sortable=True),
        DTColumn("customer__name",_("Cliente"),     sortable=True),
        DTColumn("issue_date",    _("Emisión"),     sortable=True),
        DTColumn("valid_until",   _("Válida hasta"),sortable=True),
        DTColumn("total",         _("Total"),       sortable=True, numeric=True),
        DTColumn("status",        _("Estado"),      sortable=False, classes="text-center"),
    ]
    dt_default_sort = "-issue_date"
    dt_url = "invoices:quotation_list"
    dt_row_template = "invoices/partials/quotation_row.html"
    dt_filter_template = "invoices/partials/quotation_filters.html"
    dt_search_placeholder = _("Número o cliente…")
    dt_id = "quotations"

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.request.organization
        qs = Invoice.quotations.filter(organization=org).select_related("customer")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["customer__name"], trgm_fields=["doc_number"])
        f = QuotationFilter(self.request.GET, queryset=qs, organization=org)
        ctx["filter"] = f
        ctx.update(self.apply_datatable(f.qs))

        if not self.request.htmx:
            agg = Invoice.quotations.filter(organization=org).aggregate(
                total_count=Count("id"),
                draft_count=Count("id", filter=Q(status=Invoice.Status.DRAFT)),
                sent_count=Count("id", filter=Q(status=Invoice.Status.SENT)),
                accepted_count=Count("id", filter=Q(status=Invoice.Status.ACCEPTED)),
            )
            ctx["stats"] = [
                {"label": _("Total cotizaciones"), "value": agg["total_count"],
                 "icon": "bi-file-text",           "color": "primary"},
                {"label": _("Borradores"),          "value": agg["draft_count"],
                 "icon": "bi-pencil-square",        "color": "secondary"},
                {"label": _("Enviadas"),            "value": agg["sent_count"],
                 "icon": "bi-send",                 "color": "info"},
                {"label": _("Aceptadas"),           "value": agg["accepted_count"],
                 "icon": "bi-check-circle",         "color": "success"},
            ]
        ctx["module"] = "quotation"
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
        ctx.setdefault("form", QuotationForm(organization=self.request.organization))
        ctx.setdefault("formset", InvoiceItemFormSet())
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        ctx["module"] = "quotation"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Cotizaciones"), "url": reverse("invoices:quotation_list")},
            {"label": _("Nueva cotización")},
        ]
        return ctx

    def post(self, request):
        form = QuotationForm(organization=request.organization, data=request.POST)
        formset = InvoiceItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            quotation = form.save(commit=False)
            quotation.organization = request.organization
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


class QuotationDetailView(HistoryMixin, ERPBaseViewMixin, DetailView):
    template_name = "invoices/quotation_detail.html"
    required_module = "invoices"
    context_object_name = "quotation"

    def get_object(self):
        return get_object_or_404(
            Invoice.quotations.select_related("customer", "organization"),
            pk=self.kwargs["pk"],
            organization=self.request.organization,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all()
        ctx["ncf_type_choices"] = NCFType.choices
        ctx["module"] = "quotation"
        q = self.object
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Cotizaciones"), "url": reverse("invoices:quotation_list")},
            {"label": q.doc_number or str(_("Borrador"))},
        ]
        ctx["history_records"] = self.get_history(self.object)
        return ctx


class QuotationUpdateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/quotation_form.html"
    required_module = "invoices"

    def _get_quotation(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=request.organization)
        if not q.is_editable:
            messages.error(request, _("Solo se pueden editar cotizaciones en Borrador."))
            return None, redirect("invoices:quotation_detail", pk=q.pk)
        return q, None

    def get(self, request, pk):
        q, redir = self._get_quotation(request, pk)
        if redir:
            return redir
        ctx = self.get_context_data(
            form=QuotationForm(organization=request.organization, instance=q),
            formset=InvoiceItemFormSet(instance=q),
            quotation=q,
        )
        return self.render_to_response(ctx)

    def post(self, request, pk):
        q, redir = self._get_quotation(request, pk)
        if redir:
            return redir
        form = QuotationForm(organization=request.organization, data=request.POST, instance=q)
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
        ctx.setdefault("form", QuotationForm(organization=self.request.organization))
        ctx.setdefault("formset", InvoiceItemFormSet())
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        ctx["module"] = "quotation"
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
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=request.organization)
        try:
            QuotationService.confirm(q)
            messages.success(request, _(f"Cotización confirmada: {q.doc_number}"))
        except (ValueError, Exception) as exc:
            messages.error(request, str(exc))
        return redirect("invoices:quotation_detail", pk=q.pk)


class QuotationSendView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=request.organization)
        try:
            QuotationService.send(q)
            messages.success(request, _("Cotización marcada como enviada."))
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("invoices:quotation_detail", pk=q.pk)
        try:
            sent = send_quotation_email(q, request)
            if sent:
                messages.info(request, _("Correo enviado a %(email)s.") % {"email": q.customer.email})
            else:
                messages.warning(request, _("El cliente no tiene correo registrado."))
        except Exception as exc:
            messages.warning(request, _("No se pudo enviar el correo: %(error)s") % {"error": str(exc)})
        return redirect("invoices:quotation_detail", pk=q.pk)


class QuotationAcceptView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=request.organization)
        try:
            QuotationService.accept(q)
            messages.success(request, _("Cotización marcada como aceptada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:quotation_detail", pk=q.pk)


class QuotationRejectView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=request.organization)
        try:
            QuotationService.reject(q)
            messages.success(request, _("Cotización marcada como rechazada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:quotation_detail", pk=q.pk)


class QuotationConvertView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=request.organization)
        ncf_type = request.POST.get("ncf_type")
        if not ncf_type:
            messages.error(request, _("Debe seleccionar el tipo de comprobante fiscal."))
            return redirect("invoices:quotation_detail", pk=q.pk)
        try:
            invoice = QuotationService.convert_to_invoice(q, int(ncf_type))
            messages.success(request, _("Cotización convertida. Factura borrador creada."))
            return redirect("invoices:invoice_detail", pk=invoice.pk)
        except (ValueError, Exception) as exc:
            messages.error(request, str(exc))
            return redirect("invoices:quotation_detail", pk=q.pk)


class QuotationDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        q = get_object_or_404(Invoice.quotations, pk=pk, organization=request.organization)
        if q.status != Invoice.Status.DRAFT:
            messages.error(request, _("Solo se pueden eliminar cotizaciones en Borrador."))
            return redirect("invoices:quotation_detail", pk=q.pk)
        q.hard_delete()
        messages.success(request, _("Cotización eliminada."))
        return redirect("invoices:quotation_list")


class QuotationPrintView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request, pk):
        quotation = get_object_or_404(
            Invoice.objects.select_related("customer", "organization"),
            pk=pk, organization=request.organization, doc_type=Invoice.DocType.QUOTATION,
        )
        return render(
            request, "invoices/quotation_print.html",
            {
                "quotation": quotation,
                "items": quotation.items.all(),
                "org": quotation.organization,
                "sender_signature_url": _signature_url(request.user, request),
            },
        )
