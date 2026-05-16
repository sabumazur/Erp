"""
apps/purchases/views.py

CRUD views and status-transition action views for the purchases app.
All views inherit ERPBaseViewMixin(LoginRequiredMixin).
"""
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.datatable import DTColumn, DataTableMixin
from apps.core.search import fts_search

from .filters import PurchaseOrderFilter, SupplierFilter
from .forms import PurchaseOrderForm, SupplierForm
from .models import PurchaseOrder, Supplier
from .services import PurchaseOrderService


def _org(request):
    return request.organization


# ── Supplier views ────────────────────────────────────────────────────────────


class SupplierListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "purchases/supplier_list.html"
    required_module = "purchases"

    dt_columns = [
        DTColumn("name",         _("Nombre"),   sortable=True),
        DTColumn("rnc",          _("RNC"),       sortable=True),
        DTColumn("email",        _("Correo"),    sortable=False),
        DTColumn("phone",        _("Teléfono"),  sortable=False),
        DTColumn("is_active",    _("Estado"),    sortable=True),
    ]
    dt_default_sort = "name"
    dt_url = "purchases:supplier_list"
    dt_row_template = "purchases/partials/supplier_row.html"
    dt_filter_template = "purchases/partials/supplier_filters.html"
    dt_search_placeholder = _("Nombre o RNC…")
    dt_id = "suppliers"

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = _org(self.request)
        qs = Supplier.objects.for_org(org)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["name"], trgm_fields=["rnc"])
        f = SupplierFilter(self.request.GET, queryset=qs)
        ctx["filter"] = f
        ctx.update(self.apply_datatable(f.qs))
        ctx["form"] = SupplierForm(organization=org)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Proveedores")},
        ]
        return ctx


class SupplierCreateView(ERPBaseViewMixin, View):
    required_module = "purchases"
    admin_required = True

    def post(self, request):
        form = SupplierForm(organization=_org(request), data=request.POST)
        if form.is_valid():
            supplier = form.save()
            messages.success(request, _(f"Proveedor «{supplier.name}» creado."))
        else:
            messages.error(request, _("No se pudo crear el proveedor. Verifique los datos."))
        return redirect("purchases:supplier_list")


class SupplierDetailView(ERPBaseViewMixin, DetailView):
    template_name = "purchases/supplier_detail.html"
    required_module = "purchases"
    context_object_name = "supplier"

    def get_object(self):
        return get_object_or_404(
            Supplier, pk=self.kwargs["pk"], organization=_org(self.request)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recent_orders"] = (
            self.object.purchase_orders.select_related("supplier")
            .order_by("-created_at")[:10]
        )
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Proveedores"), "url": reverse("purchases:supplier_list")},
            {"label": self.object.name},
        ]
        return ctx


class SupplierUpdateView(ERPBaseViewMixin, TemplateView):
    template_name = "purchases/supplier_form.html"
    required_module = "purchases"
    admin_required = True

    def _get_supplier(self, request, pk):
        return get_object_or_404(Supplier, pk=pk, organization=_org(request))

    def get(self, request, pk):
        supplier = self._get_supplier(request, pk)
        ctx = self.get_context_data(
            form=SupplierForm(organization=_org(request), instance=supplier),
            supplier=supplier,
        )
        return self.render_to_response(ctx)

    def post(self, request, pk):
        supplier = self._get_supplier(request, pk)
        form = SupplierForm(organization=_org(request), data=request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, _("Proveedor actualizado."))
            return redirect("purchases:supplier_detail", pk=supplier.pk)
        ctx = self.get_context_data(form=form, supplier=supplier)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        supplier = kwargs.get("supplier")
        ctx.setdefault("form", SupplierForm(organization=_org(self.request)))
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Proveedores"), "url": reverse("purchases:supplier_list")},
        ]
        if supplier:
            ctx["breadcrumbs"].append(
                {"label": supplier.name, "url": reverse("purchases:supplier_detail", args=[supplier.pk])}
            )
            ctx["breadcrumbs"].append({"label": _("Editar")})
        return ctx


class SupplierDeleteView(ERPBaseViewMixin, View):
    required_module = "purchases"
    admin_required = True

    def post(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk, organization=_org(request))
        name = supplier.name
        try:
            supplier.delete()
            messages.success(request, _(f"Proveedor «{name}» eliminado."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("purchases:supplier_list")


# ── PurchaseOrder views ───────────────────────────────────────────────────────


class PurchaseOrderListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "purchases/purchase_order_list.html"
    required_module = "purchases"

    dt_columns = [
        DTColumn("number",          _("Número"),   sortable=True),
        DTColumn("supplier__name",  _("Proveedor"), sortable=True),
        DTColumn("issue_date",      _("Emisión"),  sortable=True),
        DTColumn("expected_date",   _("Recepción esperada"), sortable=True, visible=False),
        DTColumn("status",          _("Estado"),   sortable=False, classes="text-center"),
    ]
    dt_default_sort = "-issue_date"
    dt_url = "purchases:purchase_order_list"
    dt_row_template = "purchases/partials/purchase_order_row.html"
    dt_filter_template = "purchases/partials/purchase_order_filters.html"
    dt_search_placeholder = _("Número o proveedor…")
    dt_id = "purchase_orders"

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = _org(self.request)
        qs = PurchaseOrder.objects.for_org(org).select_related("supplier")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["supplier__name"], trgm_fields=["number"])
        f = PurchaseOrderFilter(self.request.GET, queryset=qs, organization=org)
        ctx["filter"] = f
        ctx.update(self.apply_datatable(f.qs))

        agg = PurchaseOrder.objects.for_org(org).aggregate(
            total_count=Count("id"),
            draft_count=Count("id", filter=Q(status=PurchaseOrder.Status.DRAFT)),
            confirmed_count=Count("id", filter=Q(status=PurchaseOrder.Status.CONFIRMED)),
            received_count=Count("id", filter=Q(status=PurchaseOrder.Status.RECEIVED)),
        )
        ctx["stats"] = [
            {"label": _("Total órdenes"),  "value": agg["total_count"],    "icon": "bi-cart3",           "color": "primary"},
            {"label": _("Borradores"),     "value": agg["draft_count"],    "icon": "bi-file-earmark",    "color": "secondary"},
            {"label": _("Confirmadas"),    "value": agg["confirmed_count"],"icon": "bi-check-circle",    "color": "warning"},
            {"label": _("Recibidas"),      "value": agg["received_count"], "icon": "bi-box-seam",        "color": "success"},
        ]
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de compra")},
        ]
        return ctx


class PurchaseOrderCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "purchases/purchase_order_form.html"
    required_module = "purchases"
    admin_required = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", PurchaseOrderForm(organization=_org(self.request)))
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de compra"), "url": reverse("purchases:purchase_order_list")},
            {"label": _("Nueva orden")},
        ]
        return ctx

    def post(self, request):
        form = PurchaseOrderForm(organization=_org(request), data=request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.organization = _org(request)
            order.save()
            messages.success(request, _("Orden de compra creada como borrador."))
            return redirect("purchases:purchase_order_detail", pk=order.pk)
        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class PurchaseOrderDetailView(ERPBaseViewMixin, DetailView):
    template_name = "purchases/purchase_order_detail.html"
    required_module = "purchases"
    context_object_name = "order"

    def get_object(self):
        return get_object_or_404(
            PurchaseOrder.objects.select_related("supplier", "organization"),
            pk=self.kwargs["pk"],
            organization=_org(self.request),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        o = self.object
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de compra"), "url": reverse("purchases:purchase_order_list")},
            {"label": o.display_number},
        ]
        return ctx


class PurchaseOrderUpdateView(ERPBaseViewMixin, TemplateView):
    template_name = "purchases/purchase_order_form.html"
    required_module = "purchases"
    admin_required = True

    def _get_order(self, request, pk):
        o = get_object_or_404(PurchaseOrder, pk=pk, organization=_org(request))
        if not o.is_editable:
            messages.error(request, _("Solo se pueden editar órdenes en Borrador."))
            return None, redirect("purchases:purchase_order_detail", pk=o.pk)
        return o, None

    def get(self, request, pk):
        o, redir = self._get_order(request, pk)
        if redir:
            return redir
        ctx = self.get_context_data(
            form=PurchaseOrderForm(organization=_org(request), instance=o),
            order=o,
        )
        return self.render_to_response(ctx)

    def post(self, request, pk):
        o, redir = self._get_order(request, pk)
        if redir:
            return redir
        form = PurchaseOrderForm(organization=_org(request), data=request.POST, instance=o)
        if form.is_valid():
            form.save()
            messages.success(request, _("Orden de compra actualizada."))
            return redirect("purchases:purchase_order_detail", pk=o.pk)
        ctx = self.get_context_data(form=form, order=o)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", PurchaseOrderForm(organization=_org(self.request)))
        o = kwargs.get("order")
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de compra"), "url": reverse("purchases:purchase_order_list")},
        ]
        if o:
            ctx["breadcrumbs"].append(
                {"label": o.display_number, "url": reverse("purchases:purchase_order_detail", args=[o.pk])}
            )
            ctx["breadcrumbs"].append({"label": _("Editar")})
        return ctx


# ── PurchaseOrder transitions ─────────────────────────────────────────────────


class PurchaseOrderConfirmView(ERPBaseViewMixin, View):
    required_module = "purchases"
    admin_required = True

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk, organization=_org(request))
        try:
            PurchaseOrderService.confirm(order)
            messages.success(request, _(f"Orden confirmada: {order.number}"))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("purchases:purchase_order_detail", pk=order.pk)


class PurchaseOrderReceiveView(ERPBaseViewMixin, View):
    required_module = "purchases"
    admin_required = True

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk, organization=_org(request))
        try:
            PurchaseOrderService.receive(order)
            messages.success(request, _("Orden de compra marcada como recibida."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("purchases:purchase_order_detail", pk=order.pk)


class PurchaseOrderCancelView(ERPBaseViewMixin, View):
    required_module = "purchases"
    admin_required = True

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk, organization=_org(request))
        try:
            PurchaseOrderService.cancel(order)
            messages.success(request, _("Orden de compra anulada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("purchases:purchase_order_detail", pk=order.pk)


class PurchaseOrderDeleteView(ERPBaseViewMixin, View):
    required_module = "purchases"
    admin_required = True

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk, organization=_org(request))
        if order.status != PurchaseOrder.Status.DRAFT:
            messages.error(request, _("Solo se pueden eliminar órdenes en Borrador."))
            return redirect("purchases:purchase_order_detail", pk=order.pk)
        order.hard_delete()
        messages.success(request, _("Orden de compra eliminada."))
        return redirect("purchases:purchase_order_list")
