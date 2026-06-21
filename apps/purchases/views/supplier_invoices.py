from datetime import date

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, DetailView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.datatable import DTColumn, DataTableMixin
from apps.core.search import fts_search
from ..forms import SupplierInvoiceForm, PurchaseDocumentItemFormSet, PurchaseDocumentItemFormSetCreate
from ..models import PurchaseDocument, PurchaseDocumentItem
from ..services import SupplierInvoiceService


class SupplierInvoiceListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "purchases/supplier_invoice_list.html"
    required_module = "purchasing"

    dt_columns = [
        DTColumn("supplier_ncf",   _("NCF"),       sortable=True),
        DTColumn("supplier__name", _("Proveedor"), sortable=True),
        DTColumn("issue_date",     _("Emisión"),   sortable=True),
        DTColumn("due_date",       _("Vence"),     sortable=True, visible=False),
        DTColumn("total",          _("Total"),     sortable=True, numeric=True),
        DTColumn("status",         _("Estado"),    sortable=False, classes="text-center"),
    ]
    dt_default_sort = "-issue_date"
    dt_url = "purchases:supplier_invoice_list"
    dt_row_template = "purchases/partials/supplier_invoice_row.html"
    dt_filter_template = "purchases/partials/supplier_invoice_filters.html"
    dt_ribbon_template = "purchases/partials/supplier_invoice_ribbon.html"
    dt_search_placeholder = _("NCF o proveedor…")
    dt_id = "supplier_invoices"
    dt_create_url = "purchases:supplier_invoice_create"
    dt_create_label = _("Nueva factura de proveedor")

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.request.organization
        qs = PurchaseDocument.supplier_invoices.filter(organization=org).select_related("supplier")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["supplier__name"], trgm_fields=["supplier_ncf"])
        status_filter = self.request.GET.get("status", "")
        if status_filter:
            qs = qs.filter(status=status_filter)
        ctx.update(self.apply_datatable(qs))
        if not self.request.htmx:
            # REFACTOR PQ-11: 4 separate queries → 1 conditional aggregation.
            today = date.today()
            _DEC = DecimalField(max_digits=14, decimal_places=2)
            stats_agg = (
                PurchaseDocument.supplier_invoices
                .filter(organization=org)
                .aggregate(
                    total_count=Count("id"),
                    month_total=Coalesce(
                        Sum("total", filter=Q(
                            issue_date__year=today.year,
                            issue_date__month=today.month,
                        )),
                        Value(0, output_field=_DEC), output_field=_DEC,
                    ),
                    confirmed_total=Coalesce(
                        Sum("total", filter=Q(status="CONFIRMED")),
                        Value(0, output_field=_DEC), output_field=_DEC,
                    ),
                    paid_count=Count("id", filter=Q(status="PAID")),
                )
            )
            ctx["stats"] = [
                {"label": _("Total facturas"),
                 "value": stats_agg["total_count"],
                 "icon": "bi-receipt",          "color": "primary"},
                {"label": _("Comprado este mes"),
                 "value": "{:,.2f}".format(stats_agg["month_total"] or 0),
                 "icon": "bi-cash-stack",       "color": "success", "currency": "RD$"},
                {"label": _("Por pagar"),
                 "value": "{:,.2f}".format(stats_agg["confirmed_total"] or 0),
                 "icon": "bi-hourglass-split",  "color": "warning", "currency": "RD$"},
                {"label": _("Pagadas"),
                 "value": stats_agg["paid_count"],
                 "icon": "bi-check2-circle",    "color": "info"},
            ]
        ctx["module"] = "supplier-invoice"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Facturas de Proveedor")},
        ]
        return ctx


class SupplierInvoiceCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "purchases/supplier_invoice_form.html"
    required_module = "purchasing"
    admin_required = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", SupplierInvoiceForm(organization=self.request.organization))
        ctx.setdefault("formset", PurchaseDocumentItemFormSetCreate(
            form_kwargs={"organization": self.request.organization}
        ))
        ctx["module"] = "supplier-invoice"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Facturas de Proveedor"), "url": reverse("purchases:supplier_invoice_list")},
            {"label": _("Nueva factura")},
        ]
        return ctx

    def post(self, request):
        form = SupplierInvoiceForm(organization=request.organization, data=request.POST)
        formset = PurchaseDocumentItemFormSet(
            request.POST,
            form_kwargs={"organization": request.organization},
        )
        if form.is_valid() and formset.is_valid():
            si = form.save(commit=False)
            si.organization = request.organization
            si.doc_type = PurchaseDocument.DocType.SUPPLIER_INVOICE
            si.save()
            formset.instance = si
            formset.save()
            si.recompute_totals()
            messages.success(request, _("Factura de proveedor creada como borrador."))
            return redirect("purchases:supplier_invoice_detail", pk=si.pk)
        ctx = self.get_context_data()
        ctx["form"] = form
        ctx["formset"] = formset
        return self.render_to_response(ctx)


class SupplierInvoiceDetailView(ERPBaseViewMixin, DetailView):
    template_name = "purchases/supplier_invoice_detail.html"
    required_module = "purchasing"
    context_object_name = "invoice"

    def get_object(self):
        return get_object_or_404(
            PurchaseDocument.supplier_invoices.select_related("supplier", "organization", "linked_purchase_order"),
            pk=self.kwargs["pk"],
            organization=self.request.organization,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.select_related("item").all()
        ctx["module"] = "supplier-invoice"
        inv = self.object
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Facturas de Proveedor"), "url": reverse("purchases:supplier_invoice_list")},
            {"label": inv.supplier_ncf or str(_("Borrador"))},
        ]
        return ctx


class SupplierInvoiceUpdateView(ERPBaseViewMixin, TemplateView):
    template_name = "purchases/supplier_invoice_form.html"
    required_module = "purchasing"
    admin_required = True

    def _get_invoice(self, request, pk):
        inv = get_object_or_404(PurchaseDocument.supplier_invoices, pk=pk, organization=request.organization)
        if not inv.is_editable:
            messages.error(request, _("Solo se pueden editar facturas en Borrador."))
            return None, redirect("purchases:supplier_invoice_detail", pk=inv.pk)
        return inv, None

    def get(self, request, pk):
        inv, redir = self._get_invoice(request, pk)
        if redir:
            return redir
        ctx = self.get_context_data(
            form=SupplierInvoiceForm(organization=request.organization, instance=inv),
            formset=PurchaseDocumentItemFormSet(instance=inv, form_kwargs={"organization": request.organization}),
            invoice=inv,
        )
        return self.render_to_response(ctx)

    def post(self, request, pk):
        inv, redir = self._get_invoice(request, pk)
        if redir:
            return redir
        form = SupplierInvoiceForm(organization=request.organization, data=request.POST, instance=inv)
        formset = PurchaseDocumentItemFormSet(
            request.POST, instance=inv, form_kwargs={"organization": request.organization}
        )
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            inv.recompute_totals()
            messages.success(request, _("Factura de proveedor actualizada."))
            return redirect("purchases:supplier_invoice_detail", pk=inv.pk)
        ctx = self.get_context_data(form=form, formset=formset, invoice=inv)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", SupplierInvoiceForm(organization=self.request.organization))
        ctx.setdefault("formset", PurchaseDocumentItemFormSet(form_kwargs={"organization": self.request.organization}))
        ctx["module"] = "supplier-invoice"
        inv = kwargs.get("invoice")
        if inv:
            ctx["breadcrumbs"] = [
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Facturas de Proveedor"), "url": reverse("purchases:supplier_invoice_list")},
                {"label": inv.supplier_ncf or str(_("Borrador")), "url": reverse("purchases:supplier_invoice_detail", args=[inv.pk])},
                {"label": _("Editar")},
            ]
        return ctx


class SupplierInvoiceConfirmView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def post(self, request, pk):
        inv = get_object_or_404(PurchaseDocument.supplier_invoices, pk=pk, organization=request.organization)
        try:
            SupplierInvoiceService.confirm(inv)
            messages.success(request, _(f"Factura confirmada: {inv.supplier_ncf}"))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("purchases:supplier_invoice_detail", pk=inv.pk)


class SupplierInvoiceCancelView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def post(self, request, pk):
        inv = get_object_or_404(PurchaseDocument.supplier_invoices, pk=pk, organization=request.organization)
        try:
            SupplierInvoiceService.cancel(inv)
            messages.success(request, _("Factura de proveedor anulada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("purchases:supplier_invoice_detail", pk=inv.pk)


class SupplierInvoiceReopenView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def post(self, request, pk):
        inv = get_object_or_404(PurchaseDocument.supplier_invoices, pk=pk, organization=request.organization)
        try:
            SupplierInvoiceService.reopen(inv)
            messages.success(request, _("Factura reabierta como borrador."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("purchases:supplier_invoice_detail", pk=inv.pk)


class SupplierInvoiceDeleteView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def post(self, request, pk):
        inv = get_object_or_404(PurchaseDocument.supplier_invoices, pk=pk, organization=request.organization)
        if inv.status != PurchaseDocument.Status.DRAFT:
            messages.error(request, _("Solo se pueden eliminar facturas en Borrador."))
            return redirect("purchases:supplier_invoice_detail", pk=inv.pk)
        inv.hard_delete()
        messages.success(request, _("Factura eliminada."))
        return redirect("purchases:supplier_invoice_list")


class SupplierInvoiceCloneView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def post(self, request, pk):
        source = get_object_or_404(
            PurchaseDocument.objects.prefetch_related("items"),
            pk=pk,
            organization=request.organization,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
        )
        new_inv = PurchaseDocument.objects.create(
            organization=source.organization,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
            supplier=source.supplier,
            issue_date=date.today(),
            due_date=source.due_date,
            currency=source.currency,
            exchange_rate=source.exchange_rate,
            notes=source.notes,
            # Clear fiscal fields
            supplier_ncf="",
            supplier_ncf_type="",
            supplier_rnc="",
        )
        # REFACTOR PQ-002: bulk_create all line items in 1 INSERT instead of N.
        # No post_save signal on PurchaseDocumentItem; recompute_totals() called
        # once below as before.
        PurchaseDocumentItem.objects.bulk_create([
            PurchaseDocumentItem(
                purchase_document=new_inv,
                item=line.item,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                itbis_rate=line.itbis_rate,
            )
            for line in source.items.all()
        ])
        new_inv.recompute_totals()
        messages.success(request, _("Factura clonada correctamente. Ingrese el NCF del proveedor."))
        return redirect("purchases:supplier_invoice_edit", pk=new_inv.pk)
