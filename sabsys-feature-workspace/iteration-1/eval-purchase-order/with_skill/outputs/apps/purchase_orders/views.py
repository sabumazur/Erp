import json

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.datatable import DTColumn, DataTableMixin, build_datatable_context

from .filters import PurchaseOrderFilter, SupplierFilter
from .forms import PurchaseOrderForm, SupplierForm
from .models import PurchaseOrder, Supplier
from .services import PurchaseOrderService


def _org(request):
    return request.organization


# ── Supplier views ─────────────────────────────────────────────────────────────


class SupplierListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "purchase_orders/supplier_list.html"
    required_module = "purchase_orders"

    dt_columns = [
        DTColumn("name", _("Nombre"), sortable=True),
        DTColumn("tax_id", _("RNC / Cédula"), sortable=False),
        DTColumn("email", _("Correo"), sortable=False),
        DTColumn("phone", _("Teléfono"), sortable=False),
        DTColumn("contact_name", _("Contacto"), sortable=False),
    ]
    dt_default_sort = "name"
    dt_page_size = 25
    dt_url = "purchase_orders:supplier_list"
    dt_row_template = "purchase_orders/partials/supplier_row.html"
    dt_filter_template = "purchase_orders/partials/supplier_filters.html"
    dt_search_placeholder = _("Buscar proveedores…")
    dt_id = "purchase_orders_suppliers"

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        qs = Supplier.objects.for_org(_org(request))
        f = SupplierFilter(request.GET, queryset=qs)
        ctx = build_datatable_context(
            request,
            f.qs,
            cls.dt_columns,
            default_sort=cls.dt_default_sort,
            page_size=cls.dt_page_size,
            url=cls.dt_url,
            row_template=cls.dt_row_template,
            filter_template=cls.dt_filter_template,
        )
        ctx["filter"] = f
        resp = render(request, "components/datatable/results.html", ctx)
        resp["HX-Retarget"] = "#dt-results"
        resp["HX-Reswap"] = "innerHTML"
        resp["HX-Trigger"] = json.dumps(
            {"showToast": {"message": str(msg), "type": msg_type}}
        )
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Supplier.objects.for_org(_org(self.request))
        f = SupplierFilter(self.request.GET, queryset=qs)
        ctx.update(self.apply_datatable(f.qs))
        ctx["filter"] = f
        ctx["form"] = SupplierForm()
        ctx["create_url"] = reverse("purchase_orders:supplier_list")
        ctx["submit_label"] = _("Crear")
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Proveedores")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def post(self, request):
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.organization = _org(request)
            supplier.save()
            if request.htmx:
                return SupplierListView.refresh_table(
                    request, _("Proveedor creado correctamente.")
                )
            messages.success(request, _("Proveedor creado correctamente."))
            return redirect("purchase_orders:supplier_list")

        if request.htmx:
            resp = render(
                request,
                "purchase_orders/partials/supplier_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("purchase_orders:supplier_list"),
                    "submit_label": _("Crear"),
                },
            )
            resp["HX-Retarget"] = "#supplier-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp

        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class SupplierUpdateView(ERPBaseViewMixin, View):
    required_module = "purchase_orders"
    admin_required = True

    def get(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk, organization=_org(request))
        form = SupplierForm(instance=supplier)

        if request.htmx:
            return render(
                request,
                "purchase_orders/partials/supplier_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("purchase_orders:supplier_edit", args=[pk]),
                    "submit_label": _("Guardar"),
                },
            )

        return render(
            request,
            "purchase_orders/supplier_form.html",
            self.get_context(
                form=form,
                supplier=supplier,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {
                        "label": _("Proveedores"),
                        "url": reverse("purchase_orders:supplier_list"),
                    },
                    {"label": str(supplier)},
                    {"label": _("Editar")},
                ],
            ),
        )

    def post(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk, organization=_org(request))
        form = SupplierForm(request.POST, instance=supplier)

        if form.is_valid():
            form.save()
            if request.htmx:
                return SupplierListView.refresh_table(
                    request, _("Proveedor actualizado correctamente.")
                )
            messages.success(request, _("Proveedor actualizado correctamente."))
            return redirect("purchase_orders:supplier_list")

        if request.htmx:
            resp = render(
                request,
                "purchase_orders/partials/supplier_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("purchase_orders:supplier_edit", args=[pk]),
                    "submit_label": _("Guardar"),
                },
            )
            resp["HX-Retarget"] = "#supplier-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp

        return render(
            request,
            "purchase_orders/supplier_form.html",
            self.get_context(
                form=form,
                supplier=supplier,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {
                        "label": _("Proveedores"),
                        "url": reverse("purchase_orders:supplier_list"),
                    },
                    {"label": str(supplier)},
                    {"label": _("Editar")},
                ],
            ),
        )


class SupplierDeleteView(ERPBaseViewMixin, View):
    required_module = "purchase_orders"
    admin_required = True

    def post(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk, organization=_org(request))
        name = str(supplier)

        if supplier.purchase_orders.exists():
            msg = _(
                f"No se puede eliminar «{name}»: tiene órdenes de compra asociadas."
            )
            if request.htmx:
                resp = HttpResponse()
                resp["HX-Reswap"] = "none"
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showSwal": {
                            "icon": "error",
                            "title": str(_("No se puede eliminar")),
                            "text": str(msg),
                        }
                    }
                )
                return resp
            messages.error(request, str(msg))
            return redirect("purchase_orders:supplier_list")

        supplier.delete()
        msg = _(f"Proveedor «{name}» eliminado.")

        if request.htmx:
            return SupplierListView.refresh_table(request, msg)
        messages.success(request, msg)
        return redirect("purchase_orders:supplier_list")


# ── PurchaseOrder views ────────────────────────────────────────────────────────


class PurchaseOrderListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "purchase_orders/purchase_order_list.html"
    required_module = "purchase_orders"

    dt_columns = [
        DTColumn("number", _("Número"), sortable=True),
        DTColumn("supplier", _("Proveedor"), sortable=True),
        DTColumn("status", _("Estado"), sortable=True),
        DTColumn("issue_date", _("Fecha emisión"), sortable=True),
        DTColumn("expected_date", _("Fecha esperada"), sortable=True),
    ]
    dt_default_sort = "-created_at"
    dt_page_size = 25
    dt_url = "purchase_orders:purchase_order_list"
    dt_row_template = "purchase_orders/partials/purchase_order_row.html"
    dt_filter_template = "purchase_orders/partials/purchase_order_filters.html"
    dt_search_placeholder = _("Buscar órdenes de compra…")
    dt_id = "purchase_orders_list"

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        qs = PurchaseOrder.objects.for_org(_org(request)).select_related("supplier")
        f = PurchaseOrderFilter(request.GET, queryset=qs, organization=_org(request))
        ctx = build_datatable_context(
            request,
            f.qs,
            cls.dt_columns,
            default_sort=cls.dt_default_sort,
            page_size=cls.dt_page_size,
            url=cls.dt_url,
            row_template=cls.dt_row_template,
            filter_template=cls.dt_filter_template,
        )
        ctx["filter"] = f
        resp = render(request, "components/datatable/results.html", ctx)
        resp["HX-Retarget"] = "#dt-results"
        resp["HX-Reswap"] = "innerHTML"
        resp["HX-Trigger"] = json.dumps(
            {"showToast": {"message": str(msg), "type": msg_type}}
        )
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = PurchaseOrder.objects.for_org(_org(self.request)).select_related(
            "supplier"
        )
        f = PurchaseOrderFilter(
            self.request.GET, queryset=qs, organization=_org(self.request)
        )
        ctx.update(self.apply_datatable(f.qs))
        ctx["filter"] = f
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de compra")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)


class PurchaseOrderCreateView(ERPBaseViewMixin, View):
    required_module = "purchase_orders"
    admin_required = True

    def get(self, request):
        form = PurchaseOrderForm(organization=_org(request))
        return render(
            request,
            "purchase_orders/purchase_order_form.html",
            self.get_context(
                form=form,
                title=_("Nueva orden de compra"),
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {
                        "label": _("Órdenes de compra"),
                        "url": reverse("purchase_orders:purchase_order_list"),
                    },
                    {"label": _("Nueva")},
                ],
            ),
        )

    def post(self, request):
        form = PurchaseOrderForm(request.POST, organization=_org(request))
        if form.is_valid():
            order = form.save(commit=False)
            order.organization = _org(request)
            order.save()
            messages.success(request, _("Orden de compra creada."))
            return redirect("purchase_orders:purchase_order_detail", pk=order.pk)

        return render(
            request,
            "purchase_orders/purchase_order_form.html",
            self.get_context(
                form=form,
                title=_("Nueva orden de compra"),
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {
                        "label": _("Órdenes de compra"),
                        "url": reverse("purchase_orders:purchase_order_list"),
                    },
                    {"label": _("Nueva")},
                ],
            ),
        )


class PurchaseOrderDetailView(ERPBaseViewMixin, View):
    required_module = "purchase_orders"

    def get(self, request, pk):
        order = get_object_or_404(
            PurchaseOrder.objects.select_related("supplier"),
            pk=pk,
            organization=_org(request),
        )
        return render(
            request,
            "purchase_orders/purchase_order_detail.html",
            self.get_context(
                order=order,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {
                        "label": _("Órdenes de compra"),
                        "url": reverse("purchase_orders:purchase_order_list"),
                    },
                    {"label": str(order)},
                ],
            ),
        )


class PurchaseOrderUpdateView(ERPBaseViewMixin, View):
    required_module = "purchase_orders"
    admin_required = True

    def _get_order(self, request, pk):
        return get_object_or_404(
            PurchaseOrder, pk=pk, organization=_org(request)
        )

    def get(self, request, pk):
        order = self._get_order(request, pk)
        if order.status != PurchaseOrder.Status.DRAFT:
            messages.error(
                request,
                _("Solo se pueden editar órdenes de compra en estado Borrador."),
            )
            return redirect("purchase_orders:purchase_order_detail", pk=pk)

        form = PurchaseOrderForm(instance=order, organization=_org(request))
        return render(
            request,
            "purchase_orders/purchase_order_form.html",
            self.get_context(
                form=form,
                order=order,
                title=_("Editar orden de compra"),
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {
                        "label": _("Órdenes de compra"),
                        "url": reverse("purchase_orders:purchase_order_list"),
                    },
                    {
                        "label": str(order),
                        "url": reverse(
                            "purchase_orders:purchase_order_detail", args=[pk]
                        ),
                    },
                    {"label": _("Editar")},
                ],
            ),
        )

    def post(self, request, pk):
        order = self._get_order(request, pk)
        if order.status != PurchaseOrder.Status.DRAFT:
            messages.error(
                request,
                _("Solo se pueden editar órdenes de compra en estado Borrador."),
            )
            return redirect("purchase_orders:purchase_order_detail", pk=pk)

        form = PurchaseOrderForm(request.POST, instance=order, organization=_org(request))
        if form.is_valid():
            form.save()
            messages.success(request, _("Orden de compra actualizada."))
            return redirect("purchase_orders:purchase_order_detail", pk=pk)

        return render(
            request,
            "purchase_orders/purchase_order_form.html",
            self.get_context(
                form=form,
                order=order,
                title=_("Editar orden de compra"),
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {
                        "label": _("Órdenes de compra"),
                        "url": reverse("purchase_orders:purchase_order_list"),
                    },
                    {
                        "label": str(order),
                        "url": reverse(
                            "purchase_orders:purchase_order_detail", args=[pk]
                        ),
                    },
                    {"label": _("Editar")},
                ],
            ),
        )


class PurchaseOrderDeleteView(ERPBaseViewMixin, View):
    required_module = "purchase_orders"
    admin_required = True

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk, organization=_org(request))

        if order.status != PurchaseOrder.Status.DRAFT:
            msg = _("Solo se pueden eliminar órdenes de compra en estado Borrador.")
            if request.htmx:
                resp = HttpResponse()
                resp["HX-Reswap"] = "none"
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showSwal": {
                            "icon": "error",
                            "title": str(_("No se puede eliminar")),
                            "text": str(msg),
                        }
                    }
                )
                return resp
            messages.error(request, str(msg))
            return redirect("purchase_orders:purchase_order_list")

        label = str(order)
        order.delete()
        msg = _(f"Orden «{label}» eliminada.")

        if request.htmx:
            return PurchaseOrderListView.refresh_table(request, msg)
        messages.success(request, msg)
        return redirect("purchase_orders:purchase_order_list")


# ── Status-transition action views ─────────────────────────────────────────────


class PurchaseOrderConfirmView(ERPBaseViewMixin, View):
    required_module = "purchase_orders"
    admin_required = True

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk, organization=_org(request))
        try:
            PurchaseOrderService.confirm(order)
            messages.success(
                request,
                _(f"Orden confirmada. Número asignado: {order.number}"),
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("purchase_orders:purchase_order_detail", pk=pk)


class PurchaseOrderReceiveView(ERPBaseViewMixin, View):
    required_module = "purchase_orders"
    admin_required = True

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk, organization=_org(request))
        try:
            PurchaseOrderService.receive(order)
            messages.success(request, _("Orden marcada como recibida."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("purchase_orders:purchase_order_detail", pk=pk)


class PurchaseOrderCancelView(ERPBaseViewMixin, View):
    required_module = "purchase_orders"
    admin_required = True

    def post(self, request, pk):
        order = get_object_or_404(PurchaseOrder, pk=pk, organization=_org(request))
        try:
            PurchaseOrderService.cancel(order)
            messages.success(request, _("Orden de compra anulada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("purchase_orders:purchase_order_detail", pk=pk)
