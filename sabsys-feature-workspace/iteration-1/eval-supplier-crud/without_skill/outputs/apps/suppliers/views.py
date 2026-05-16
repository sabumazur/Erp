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
from apps.core.search import fts_search

from .filters import SupplierFilter
from .forms import SupplierForm
from .models import Supplier


def _org(request):
    return request.organization


# ── List + Create ─────────────────────────────────────────────────────────────

class SupplierListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "suppliers/supplier_list.html"
    required_module = "suppliers"

    dt_columns = [
        DTColumn("name",   _("Nombre"),  sortable=True),
        DTColumn("rnc",    _("RNC"),     sortable=True),
        DTColumn("phone",  _("Teléfono"), sortable=False),
        DTColumn("email",  _("Correo"),  sortable=True),
        DTColumn("status", _("Estado"),  sortable=True),
    ]
    dt_default_sort = "name"
    dt_page_size = 25
    dt_url = "suppliers:supplier_list"
    dt_row_template = "suppliers/partials/supplier_row.html"
    dt_filter_template = "suppliers/partials/supplier_filters.html"
    dt_search_placeholder = _("Nombre o RNC…")
    dt_id = "suppliers"

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        qs = Supplier.objects.for_org(_org(request))
        f = SupplierFilter(request.GET, queryset=qs)
        ctx = build_datatable_context(
            request, f.qs, cls.dt_columns,
            default_sort=cls.dt_default_sort,
            page_size=cls.dt_page_size,
            url=cls.dt_url,
            row_template=cls.dt_row_template,
            filter_template=cls.dt_filter_template,
        )
        ctx["filter"] = f
        resp = render(request, "components/datatable/results.html", ctx)
        resp["HX-Retarget"] = "#dt-results"
        resp["HX-Reswap"]   = "innerHTML"
        resp["HX-Trigger"]  = json.dumps(
            {"showToast": {"message": str(msg), "type": msg_type}}
        )
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Supplier.objects.for_org(_org(self.request))
        f  = SupplierFilter(self.request.GET, queryset=qs)
        ctx.update(self.apply_datatable(f.qs))
        ctx["filter"]      = f
        ctx["form"]        = SupplierForm()
        ctx["create_url"]  = reverse("suppliers:supplier_list")
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
            return redirect("suppliers:supplier_list")

        if request.htmx:
            resp = render(request, "suppliers/partials/supplier_modal_form.html", {
                "form":         form,
                "action_url":   reverse("suppliers:supplier_list"),
                "submit_label": _("Crear"),
            })
            resp["HX-Retarget"] = "#supplier-modal-body"
            resp["HX-Reswap"]   = "innerHTML"
            return resp

        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


# ── Detail ────────────────────────────────────────────────────────────────────

class SupplierDetailView(ERPBaseViewMixin, View):
    template_name = "suppliers/supplier_detail.html"
    required_module = "suppliers"

    def get(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk, organization=_org(request))
        return render(request, self.template_name, self.get_context(
            supplier=supplier,
            breadcrumbs=[
                {"label": _("Dashboard"),    "url": reverse("accounts:dashboard")},
                {"label": _("Proveedores"),  "url": reverse("suppliers:supplier_list")},
                {"label": supplier.name},
            ],
        ))


# ── Update ────────────────────────────────────────────────────────────────────

class SupplierUpdateView(ERPBaseViewMixin, View):
    required_module = "suppliers"

    def get(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk, organization=_org(request))
        form = SupplierForm(instance=supplier)

        if request.htmx:
            return render(request, "suppliers/partials/supplier_modal_form.html", {
                "form":         form,
                "action_url":   reverse("suppliers:supplier_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })

        return render(request, "suppliers/supplier_form.html", self.get_context(
            form=form, supplier=supplier,
            breadcrumbs=[
                {"label": _("Dashboard"),   "url": reverse("accounts:dashboard")},
                {"label": _("Proveedores"), "url": reverse("suppliers:supplier_list")},
                {"label": supplier.name,    "url": reverse("suppliers:supplier_detail", args=[supplier.pk])},
                {"label": _("Editar")},
            ],
        ))

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
            return redirect("suppliers:supplier_detail", pk=supplier.pk)

        if request.htmx:
            resp = render(request, "suppliers/partials/supplier_modal_form.html", {
                "form":         form,
                "action_url":   reverse("suppliers:supplier_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })
            resp["HX-Retarget"] = "#supplier-modal-body"
            resp["HX-Reswap"]   = "innerHTML"
            return resp

        return render(request, "suppliers/supplier_form.html", self.get_context(
            form=form, supplier=supplier,
            breadcrumbs=[
                {"label": _("Dashboard"),   "url": reverse("accounts:dashboard")},
                {"label": _("Proveedores"), "url": reverse("suppliers:supplier_list")},
                {"label": supplier.name,    "url": reverse("suppliers:supplier_detail", args=[supplier.pk])},
                {"label": _("Editar")},
            ],
        ))


# ── Delete ────────────────────────────────────────────────────────────────────

class SupplierDeleteView(ERPBaseViewMixin, View):
    required_module = "suppliers"
    admin_required = True

    def post(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk, organization=_org(request))
        name = supplier.name
        supplier.delete()

        if request.htmx:
            return SupplierListView.refresh_table(
                request, _(f"Proveedor «{name}» eliminado.")
            )
        messages.success(request, _(f"Proveedor «{name}» eliminado."))
        return redirect("suppliers:supplier_list")
