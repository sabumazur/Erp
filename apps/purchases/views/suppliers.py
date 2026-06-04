import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.datatable import DTColumn, DataTableMixin, build_datatable_context
from apps.core.search import fts_search
from ..forms import SupplierForm
from ..models import Supplier, PurchaseDocument, SupplierPayment


class SupplierListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "purchases/supplier_list.html"
    required_module = "purchasing"

    dt_columns = [
        DTColumn("name",      _("Nombre"),      sortable=True),
        DTColumn("rnc_cedula", _("RNC/Cédula"),  sortable=True),
        DTColumn("email",     _("Correo"),      sortable=False, visible=False),
        DTColumn("phone",     _("Teléfono"),    sortable=False, visible=False),
        DTColumn("is_active", _("Estado"),      sortable=False, classes="text-center"),
    ]
    dt_default_sort = "name"
    dt_url = "purchases:supplier_list"
    dt_row_template = "purchases/partials/supplier_row.html"
    dt_filter_template = "purchases/partials/supplier_filters.html"
    dt_ribbon_template = "purchases/partials/supplier_ribbon.html"
    dt_search_placeholder = _("Nombre o RNC…")
    dt_id = "suppliers"

    @classmethod
    def _refresh_table(cls, request, msg, msg_type="success"):
        qs = Supplier.objects.filter(organization=request.organization)
        q = request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["name"], trgm_fields=["rnc_cedula"])
        ctx = build_datatable_context(
            request, qs, cls.dt_columns,
            default_sort=cls.dt_default_sort,
            page_size=cls.dt_page_size,
            url=cls.dt_url,
            row_template=cls.dt_row_template,
            filter_template=cls.dt_filter_template,
        )
        resp = render(request, "components/datatable/results.html", ctx)
        resp["HX-Retarget"] = "#dt-results"
        resp["HX-Trigger"] = json.dumps({"showToast": {"message": msg, "type": msg_type}})
        return resp

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = self.request.organization
        qs = Supplier.objects.filter(organization=org)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["name"], trgm_fields=["rnc_cedula"])
        ctx.update(self.apply_datatable(qs))
        ctx["form"] = SupplierForm(organization=org)
        ctx["module"] = "supplier"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Proveedores")},
        ]
        return ctx

    def post(self, request):
        if not request.membership or not request.membership.is_admin:
            raise PermissionDenied
        form = SupplierForm(request.POST, organization=request.organization)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.organization = request.organization
            supplier.save()
            if request.htmx:
                return self._refresh_table(request, str(_("Proveedor creado correctamente.")))
            messages.success(request, _("Proveedor creado correctamente."))
            return redirect("purchases:supplier_list")

        if request.htmx:
            resp = render(
                request,
                "purchases/partials/supplier_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("purchases:supplier_list"),
                    "submit_label": _("Crear"),
                },
            )
            resp["HX-Retarget"] = "#supplier-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class SupplierCreateView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def get(self, request):
        form = SupplierForm(organization=request.organization)
        return render(
            request, "purchases/supplier_form.html",
            self.get_context(
                form=form,
                module="supplier",
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Proveedores"), "url": reverse("purchases:supplier_list")},
                    {"label": _("Nuevo proveedor")},
                ],
            ),
        )

    def post(self, request):
        form = SupplierForm(request.POST, organization=request.organization)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.organization = request.organization
            supplier.save()
            messages.success(request, _("Proveedor creado correctamente."))
            return redirect("purchases:supplier_detail", pk=supplier.pk)
        return render(
            request, "purchases/supplier_form.html",
            self.get_context(
                form=form,
                module="supplier",
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Proveedores"), "url": reverse("purchases:supplier_list")},
                    {"label": _("Nuevo proveedor")},
                ],
            ),
        )


class SupplierDetailView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def get(self, request, pk):
        from decimal import Decimal
        supplier = get_object_or_404(Supplier, pk=pk, organization=request.organization)
        invoices = list(
            PurchaseDocument.supplier_invoices.filter(
                organization=request.organization, supplier=supplier
            ).exclude(status=PurchaseDocument.Status.CANCELLED)
            .order_by("-issue_date")
        )
        from django.db.models import Sum
        total_invoiced = sum((inv.total for inv in invoices), Decimal("0.00"))
        total_paid = SupplierPayment.objects.filter(
            supplier=supplier, organization=request.organization
        ).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")
        balance = total_invoiced - total_paid
        recent_payments = list(
            SupplierPayment.objects.filter(supplier=supplier, organization=request.organization)
            .prefetch_related("allocations__supplier_invoice")
            .order_by("-date", "-created_at")[:30]
        )
        return render(
            request,
            "purchases/supplier_detail.html",
            self.get_context(
                module="supplier",
                supplier=supplier,
                invoices=invoices,
                total_invoiced=total_invoiced,
                total_paid=total_paid,
                balance=balance,
                recent_payments=recent_payments,
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Proveedores"), "url": reverse("purchases:supplier_list")},
                    {"label": supplier.name},
                ],
            ),
        )


class SupplierUpdateView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def _get_supplier(self, request, pk):
        return get_object_or_404(Supplier, pk=pk, organization=request.organization)

    def _smart_buttons(self, request, supplier, pk):
        invoice_count = PurchaseDocument.supplier_invoices.filter(
            organization=request.organization, supplier=supplier
        ).exclude(status=PurchaseDocument.Status.CANCELLED).count()
        payment_count = SupplierPayment.objects.filter(
            supplier=supplier, organization=request.organization
        ).count()
        return {
            "invoice_count": invoice_count,
            "payment_count": payment_count,
            "detail_url": reverse("purchases:supplier_detail", args=[pk]),
        }

    def get(self, request, pk):
        supplier = self._get_supplier(request, pk)
        if request.htmx:
            form = SupplierForm(instance=supplier, organization=request.organization)
            return render(
                request,
                "purchases/partials/supplier_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("purchases:supplier_edit", args=[pk]),
                    "submit_label": _("Guardar"),
                },
            )
        form = SupplierForm(instance=supplier, organization=request.organization)
        return render(
            request, "purchases/supplier_form.html",
            self.get_context(
                form=form,
                supplier=supplier,
                smart_buttons=self._smart_buttons(request, supplier, pk),
                module="supplier",
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Proveedores"), "url": reverse("purchases:supplier_list")},
                    {"label": supplier.name, "url": reverse("purchases:supplier_detail", args=[pk])},
                    {"label": _("Editar")},
                ],
            ),
        )

    def post(self, request, pk):
        supplier = self._get_supplier(request, pk)
        form = SupplierForm(request.POST, instance=supplier, organization=request.organization)
        if form.is_valid():
            form.save()
            if request.htmx:
                resp = SupplierListView._refresh_table(request, str(_("Proveedor actualizado.")))
                return resp
            messages.success(request, _("Proveedor actualizado."))
            return redirect("purchases:supplier_detail", pk=pk)

        if request.htmx:
            resp = render(
                request,
                "purchases/partials/supplier_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("purchases:supplier_edit", args=[pk]),
                    "submit_label": _("Guardar"),
                },
            )
            resp["HX-Retarget"] = "#supplier-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        return render(
            request, "purchases/supplier_form.html",
            self.get_context(
                form=form,
                supplier=supplier,
                smart_buttons=self._smart_buttons(request, supplier, pk),
                module="supplier",
                breadcrumbs=[
                    {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                    {"label": _("Proveedores"), "url": reverse("purchases:supplier_list")},
                    {"label": supplier.name, "url": reverse("purchases:supplier_detail", args=[pk])},
                    {"label": _("Editar")},
                ],
            ),
        )


class SupplierDeleteView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def post(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk, organization=request.organization)
        name = supplier.name
        try:
            supplier.delete()
        except ValueError as exc:
            if request.htmx:
                resp = HttpResponse()
                resp["HX-Reswap"] = "none"
                resp["HX-Trigger"] = json.dumps({"showSwal": {
                    "icon": "error",
                    "title": str(_("No se puede eliminar")),
                    "text": str(exc),
                }})
                return resp
            messages.error(request, str(exc))
            return redirect("purchases:supplier_list")
        if request.htmx:
            return SupplierListView._refresh_table(request, str(_(f"Proveedor «{name}» eliminado.")))
        messages.success(request, _(f"Proveedor «{name}» eliminado."))
        return redirect("purchases:supplier_list")

