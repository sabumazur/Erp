from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, DetailView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.datatable import DTColumn, DataTableMixin
from apps.core.search import fts_search
from ..forms import PurchaseOrderForm, PurchaseDocumentItemFormSet, PurchaseDocumentItemFormSetCreate
from ..models import PurchaseDocument, PurchaseDocumentItem
from ..services import PurchaseOrderService


class PurchaseOrderListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "purchases/purchase_order_list.html"
    required_module = "purchasing"

    dt_columns = [
        DTColumn("number",         _("Número"),    sortable=True),
        DTColumn("supplier__name", _("Proveedor"), sortable=True),
        DTColumn("issue_date",     _("Emisión"),   sortable=True),
        DTColumn("expected_date",  _("Entrega"),   sortable=True, visible=False),
        DTColumn("total",          _("Total"),     sortable=True, numeric=True),
        DTColumn("status",         _("Estado"),    sortable=False, classes="text-center"),
    ]
    dt_default_sort = "-issue_date"
    dt_url = "purchases:po_list"
    dt_row_template = "purchases/partials/purchase_order_row.html"
    dt_filter_template = "purchases/partials/purchase_order_filters.html"
    dt_ribbon_template = "purchases/partials/purchase_order_ribbon.html"
    dt_search_placeholder = _("Número o proveedor…")
    dt_id = "purchase_orders"

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.request.organization
        qs = PurchaseDocument.purchase_orders.filter(organization=org).select_related("supplier")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["supplier__name"], trgm_fields=["number"])
        status_filter = self.request.GET.get("status", "")
        if status_filter:
            qs = qs.filter(status=status_filter)
        org_qs = PurchaseDocument.purchase_orders.filter(organization=org)
        status_pills = [
            {"value": "DRAFT",     "label": _("Borrador"),   "color": "#94a3b8",
             "count": org_qs.filter(status="DRAFT").count()},
            {"value": "CONFIRMED", "label": _("Confirmada"), "color": "#3b82f6",
             "count": org_qs.filter(status="CONFIRMED").count()},
            {"value": "RECEIVED",  "label": _("Recibida"),   "color": "#10b981",
             "count": org_qs.filter(status="RECEIVED").count()},
            {"value": "CANCELLED", "label": _("Anulada"),    "color": "#ef4444",
             "count": org_qs.filter(status="CANCELLED").count()},
        ]
        ctx.update(self.apply_datatable(qs, status_pills=status_pills))
        ctx["module"] = "purchase-order"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de Compra")},
        ]
        return ctx


class PurchaseOrderCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "purchases/purchase_order_form.html"
    required_module = "purchasing"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", PurchaseOrderForm(organization=self.request.organization))
        ctx.setdefault("formset", PurchaseDocumentItemFormSetCreate(
            form_kwargs={"organization": self.request.organization}
        ))
        ctx["module"] = "purchase-order"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de Compra"), "url": reverse("purchases:po_list")},
            {"label": _("Nueva orden")},
        ]
        return ctx

    def post(self, request):
        form = PurchaseOrderForm(organization=request.organization, data=request.POST)
        formset = PurchaseDocumentItemFormSet(
            request.POST,
            form_kwargs={"organization": request.organization},
        )
        if form.is_valid() and formset.is_valid():
            po = form.save(commit=False)
            po.organization = request.organization
            po.doc_type = PurchaseDocument.DocType.PURCHASE_ORDER
            po.save()
            formset.instance = po
            formset.save()
            po.recompute_totals()
            messages.success(request, _("Orden de compra creada como borrador."))
            return redirect("purchases:po_detail", pk=po.pk)
        ctx = self.get_context_data()
        ctx["form"] = form
        ctx["formset"] = formset
        return self.render_to_response(ctx)


class PurchaseOrderDetailView(ERPBaseViewMixin, DetailView):
    template_name = "purchases/purchase_order_detail.html"
    required_module = "purchasing"
    context_object_name = "po"

    def get_object(self):
        return get_object_or_404(
            PurchaseDocument.purchase_orders.select_related("supplier", "organization"),
            pk=self.kwargs["pk"],
            organization=self.request.organization,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all()
        ctx["module"] = "purchase-order"
        o = self.object
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de Compra"), "url": reverse("purchases:po_list")},
            {"label": o.number or str(_("Borrador"))},
        ]
        return ctx


class PurchaseOrderUpdateView(ERPBaseViewMixin, TemplateView):
    template_name = "purchases/purchase_order_form.html"
    required_module = "purchasing"

    def _get_po(self, request, pk):
        o = get_object_or_404(PurchaseDocument.purchase_orders, pk=pk, organization=request.organization)
        if not o.is_editable:
            messages.error(request, _("Solo se pueden editar órdenes en Borrador."))
            return None, redirect("purchases:po_detail", pk=o.pk)
        return o, None

    def get(self, request, pk):
        o, redir = self._get_po(request, pk)
        if redir:
            return redir
        ctx = self.get_context_data(
            form=PurchaseOrderForm(organization=request.organization, instance=o),
            formset=PurchaseDocumentItemFormSet(instance=o, form_kwargs={"organization": request.organization}),
            po=o,
        )
        return self.render_to_response(ctx)

    def post(self, request, pk):
        o, redir = self._get_po(request, pk)
        if redir:
            return redir
        form = PurchaseOrderForm(organization=request.organization, data=request.POST, instance=o)
        formset = PurchaseDocumentItemFormSet(
            request.POST, instance=o, form_kwargs={"organization": request.organization}
        )
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            o.recompute_totals()
            messages.success(request, _("Orden de compra actualizada."))
            return redirect("purchases:po_detail", pk=o.pk)
        ctx = self.get_context_data(form=form, formset=formset, po=o)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", PurchaseOrderForm(organization=self.request.organization))
        ctx.setdefault("formset", PurchaseDocumentItemFormSet(form_kwargs={"organization": self.request.organization}))
        ctx["module"] = "purchase-order"
        o = kwargs.get("po")
        if o:
            ctx["breadcrumbs"] = [
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Órdenes de Compra"), "url": reverse("purchases:po_list")},
                {"label": o.number or str(_("Borrador")), "url": reverse("purchases:po_detail", args=[o.pk])},
                {"label": _("Editar")},
            ]
        return ctx


class PurchaseOrderConfirmView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def post(self, request, pk):
        po = get_object_or_404(PurchaseDocument.purchase_orders, pk=pk, organization=request.organization)
        try:
            PurchaseOrderService.confirm(po)
            messages.success(request, _(f"Orden confirmada: {po.number}"))
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("purchases:po_detail", pk=po.pk)


class PurchaseOrderReceiveView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def post(self, request, pk):
        po = get_object_or_404(PurchaseDocument.purchase_orders, pk=pk, organization=request.organization)
        try:
            po, si = PurchaseOrderService.receive_and_invoice(po)
            messages.success(request, _("Orden recibida. Se creó una factura de proveedor borrador."))
            return redirect("purchases:supplier_invoice_edit", pk=si.pk)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("purchases:po_detail", pk=po.pk)


class PurchaseOrderCancelView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def post(self, request, pk):
        po = get_object_or_404(PurchaseDocument.purchase_orders, pk=pk, organization=request.organization)
        try:
            PurchaseOrderService.cancel(po)
            messages.success(request, _("Orden de compra anulada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("purchases:po_detail", pk=po.pk)


class PurchaseOrderDeleteView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def post(self, request, pk):
        po = get_object_or_404(PurchaseDocument.purchase_orders, pk=pk, organization=request.organization)
        if po.status != PurchaseDocument.Status.DRAFT:
            messages.error(request, _("Solo se pueden eliminar órdenes en Borrador."))
            return redirect("purchases:po_detail", pk=po.pk)
        po.hard_delete()
        messages.success(request, _("Orden eliminada."))
        return redirect("purchases:po_list")


class PurchaseOrderCloneView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def post(self, request, pk):
        source = get_object_or_404(
            PurchaseDocument.objects.prefetch_related("items"),
            pk=pk,
            organization=request.organization,
            doc_type=PurchaseDocument.DocType.PURCHASE_ORDER,
        )
        new_po = PurchaseDocument.objects.create(
            organization=source.organization,
            doc_type=PurchaseDocument.DocType.PURCHASE_ORDER,
            status=PurchaseDocument.Status.DRAFT,
            supplier=source.supplier,
            issue_date=date.today(),
            currency=source.currency,
            exchange_rate=source.exchange_rate,
            notes=source.notes,
        )
        for line in source.items.all():
            PurchaseDocumentItem.objects.create(
                purchase_document=new_po,
                item=line.item,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                itbis_rate=line.itbis_rate,
            )
        new_po.recompute_totals()
        messages.success(request, _("Orden clonada correctamente. Revise y confirme el nuevo borrador."))
        return redirect("purchases:po_edit", pk=new_po.pk)
