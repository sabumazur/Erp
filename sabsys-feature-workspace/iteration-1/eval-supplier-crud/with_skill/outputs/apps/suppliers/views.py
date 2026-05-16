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

from .filters import SupplierFilter
from .forms import SupplierForm
from .models import Supplier


class SupplierListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "suppliers/supplier_list.html"
    required_module = "suppliers"

    dt_columns = [
        DTColumn("name",       _("Nombre"),    sortable=True),
        DTColumn("rnc",        _("RNC"),        sortable=False),
        DTColumn("phone",      _("Teléfono"),   sortable=False),
        DTColumn("email",      _("Correo"),     sortable=False),
        DTColumn("status",     _("Estado"),     sortable=True),
        DTColumn("created_at", _("Creado"),     sortable=True),
    ]
    dt_default_sort = "-created_at"
    dt_page_size = 25
    dt_url = "suppliers:supplier_list"
    dt_row_template = "suppliers/partials/supplier_row.html"
    dt_filter_template = "suppliers/partials/supplier_filters.html"
    dt_search_placeholder = _("Buscar proveedores…")
    dt_id = "suppliers_supplier"

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        f = SupplierFilter(
            request.GET,
            queryset=Supplier.objects.for_org(request.organization),
        )
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
        f = SupplierFilter(
            self.request.GET,
            queryset=Supplier.objects.for_org(self.request.organization),
        )
        ctx.update(self.apply_datatable(f.qs))
        ctx["filter"] = f
        ctx["form"] = SupplierForm()
        ctx["create_url"] = reverse("suppliers:supplier_create")
        ctx["submit_label"] = _("Crear proveedor")
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


class SupplierDetailView(ERPBaseViewMixin, View):
    required_module = "suppliers"

    def get(self, request, pk):
        supplier = get_object_or_404(
            Supplier, pk=pk, organization=request.organization
        )
        return render(
            request,
            "suppliers/supplier_detail.html",
            self.get_context(
                supplier=supplier,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Proveedores"), "url": reverse("suppliers:supplier_list")},
                    {"label": supplier.name},
                ],
            ),
        )


class SupplierCreateView(ERPBaseViewMixin, View):
    admin_required = True
    required_module = "suppliers"

    def post(self, request):
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.organization = request.organization
            supplier.save()
            msg = _("Proveedor «%(name)s» creado.") % {"name": supplier.name}
            if request.htmx:
                return SupplierListView.refresh_table(request, msg)
            messages.success(request, msg)
            return redirect("suppliers:supplier_list")

        if request.htmx:
            resp = render(
                request,
                "suppliers/partials/supplier_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("suppliers:supplier_create"),
                    "submit_label": _("Crear proveedor"),
                },
            )
            resp["HX-Retarget"] = "#supplier-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp

        return render(
            request,
            "suppliers/supplier_list.html",
            self.get_context(
                form=form,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Proveedores"), "url": reverse("suppliers:supplier_list")},
                    {"label": _("Nuevo proveedor")},
                ],
            ),
        )


class SupplierUpdateView(ERPBaseViewMixin, View):
    admin_required = True
    required_module = "suppliers"

    def get(self, request, pk):
        supplier = get_object_or_404(
            Supplier, pk=pk, organization=request.organization
        )
        form = SupplierForm(instance=supplier)
        if request.htmx:
            return render(
                request,
                "suppliers/partials/supplier_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("suppliers:supplier_edit", args=[pk]),
                    "submit_label": _("Guardar"),
                },
            )
        return render(
            request,
            "suppliers/supplier_form.html",
            self.get_context(
                form=form,
                supplier=supplier,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Proveedores"), "url": reverse("suppliers:supplier_list")},
                    {"label": str(supplier)},
                    {"label": _("Editar")},
                ],
            ),
        )

    def post(self, request, pk):
        supplier = get_object_or_404(
            Supplier, pk=pk, organization=request.organization
        )
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            msg = _("Proveedor «%(name)s» actualizado.") % {"name": supplier.name}
            if request.htmx:
                return SupplierListView.refresh_table(request, msg)
            messages.success(request, msg)
            return redirect("suppliers:supplier_list")

        if request.htmx:
            resp = render(
                request,
                "suppliers/partials/supplier_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("suppliers:supplier_edit", args=[pk]),
                    "submit_label": _("Guardar"),
                },
            )
            resp["HX-Retarget"] = "#supplier-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp

        return render(
            request,
            "suppliers/supplier_form.html",
            self.get_context(
                form=form,
                supplier=supplier,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Proveedores"), "url": reverse("suppliers:supplier_list")},
                    {"label": str(supplier)},
                    {"label": _("Editar")},
                ],
            ),
        )


class SupplierDeleteView(ERPBaseViewMixin, View):
    admin_required = True
    required_module = "suppliers"

    def post(self, request, pk):
        supplier = get_object_or_404(
            Supplier, pk=pk, organization=request.organization
        )

        # Guard referential integrity.
        # Extend this block once purchase orders or bills reference suppliers:
        #   if supplier.purchase_orders.exists():
        #       msg = _("No se puede eliminar: tiene órdenes de compra asociadas.")
        #       if request.htmx:
        #           resp = HttpResponse(status=200)
        #           resp["HX-Trigger"] = json.dumps(
        #               {"showSwal": {"message": str(msg), "type": "error"}}
        #           )
        #           return resp
        #       messages.error(request, msg)
        #       return redirect("suppliers:supplier_list")

        name = str(supplier)
        supplier.delete()
        msg = _("Proveedor «%(name)s» eliminado.") % {"name": name}

        if request.htmx:
            return SupplierListView.refresh_table(request, msg)
        messages.success(request, msg)
        return redirect("suppliers:supplier_list")
