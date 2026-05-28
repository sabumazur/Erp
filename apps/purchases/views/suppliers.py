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
from ..forms import SupplierForm, SupplierDepartmentForm
from ..models import Supplier, SupplierDepartment, PurchaseDocument, SupplierPayment


class SupplierListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "purchases/supplier_list.html"
    required_module = "purchasing"

    dt_columns = [
        DTColumn("name",      _("Nombre"),      sortable=True),
        DTColumn("id_number", _("RNC/Cédula"),  sortable=True),
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
            qs = fts_search(qs, q, fts_fields=["name"], trgm_fields=["id_number"])
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
            qs = fts_search(qs, q, fts_fields=["name"], trgm_fields=["id_number"])
        ctx.update(self.apply_datatable(qs))
        ctx["form"] = SupplierForm(organization=org)
        ctx["module"] = "supplier"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Proveedores")},
        ]
        return ctx

    def post(self, request):
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
        departments = supplier.departments.filter(deleted_at__isnull=True).order_by("name")
        invoices = list(
            PurchaseDocument.supplier_invoices.filter(
                organization=request.organization, supplier=supplier
            ).exclude(status=PurchaseDocument.Status.CANCELLED)
            .order_by("-issue_date")
        )
        total_invoiced = sum((inv.total for inv in invoices), Decimal("0.00"))
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
                departments=departments,
                dept_form=SupplierDepartmentForm(),
                invoices=invoices,
                total_invoiced=total_invoiced,
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

    def _get_supplier(self, request, pk):
        return get_object_or_404(Supplier, pk=pk, organization=request.organization)

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


# ── Supplier Department CRUD ──────────────────────────────────────────────────


class SupplierDepartmentCreateView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def _supplier(self, request, supplier_pk):
        return get_object_or_404(Supplier, pk=supplier_pk, organization=request.organization)

    def _departments(self, supplier):
        return supplier.departments.filter(deleted_at__isnull=True).order_by("name")

    def get(self, request, supplier_pk):
        supplier = self._supplier(request, supplier_pk)
        form = SupplierDepartmentForm()
        return render(
            request,
            "purchases/partials/department_modal_form.html",
            {
                "form": form,
                "supplier": supplier,
                "action_url": reverse("purchases:dept_create", args=[supplier_pk]),
                "submit_label": _("Crear"),
            },
        )

    def post(self, request, supplier_pk):
        supplier = self._supplier(request, supplier_pk)
        form = SupplierDepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save(commit=False)
            dept.organization = request.organization
            dept.supplier = supplier
            dept.save()
            if request.htmx:
                resp = render(
                    request,
                    "purchases/partials/department_table.html",
                    {"departments": self._departments(supplier), "supplier": supplier},
                )
                resp["HX-Trigger"] = json.dumps(
                    {"showToast": {"message": str(_("Departamento creado.")), "type": "success"}, "closeDeptModal": True}
                )
                return resp
            messages.success(request, _("Departamento creado."))
            return redirect("purchases:supplier_detail", pk=supplier_pk)

        if request.htmx:
            resp = render(
                request,
                "purchases/partials/department_modal_form.html",
                {
                    "form": form,
                    "supplier": supplier,
                    "action_url": reverse("purchases:dept_create", args=[supplier_pk]),
                    "submit_label": _("Crear"),
                },
            )
            resp["HX-Retarget"] = "#dept-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        messages.error(request, _("Por favor corrija los errores."))
        return redirect("purchases:supplier_detail", pk=supplier_pk)


class SupplierDepartmentUpdateView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def _get_objects(self, request, supplier_pk, dept_pk):
        supplier = get_object_or_404(Supplier, pk=supplier_pk, organization=request.organization)
        dept = get_object_or_404(SupplierDepartment, pk=dept_pk, supplier=supplier)
        return supplier, dept

    def _departments(self, supplier):
        return supplier.departments.filter(deleted_at__isnull=True).order_by("name")

    def get(self, request, supplier_pk, dept_pk):
        supplier, dept = self._get_objects(request, supplier_pk, dept_pk)
        form = SupplierDepartmentForm(instance=dept)
        return render(
            request,
            "purchases/partials/department_modal_form.html",
            {
                "form": form,
                "supplier": supplier,
                "action_url": reverse("purchases:dept_edit", args=[supplier_pk, dept_pk]),
                "submit_label": _("Guardar"),
            },
        )

    def post(self, request, supplier_pk, dept_pk):
        supplier, dept = self._get_objects(request, supplier_pk, dept_pk)
        form = SupplierDepartmentForm(request.POST, instance=dept)
        if form.is_valid():
            form.save()
            if request.htmx:
                resp = render(
                    request,
                    "purchases/partials/department_table.html",
                    {"departments": self._departments(supplier), "supplier": supplier},
                )
                resp["HX-Trigger"] = json.dumps(
                    {"showToast": {"message": str(_("Departamento actualizado.")), "type": "success"}, "closeDeptModal": True}
                )
                return resp
            messages.success(request, _("Departamento actualizado."))
            return redirect("purchases:supplier_detail", pk=supplier_pk)

        if request.htmx:
            resp = render(
                request,
                "purchases/partials/department_modal_form.html",
                {
                    "form": form,
                    "supplier": supplier,
                    "action_url": reverse("purchases:dept_edit", args=[supplier_pk, dept_pk]),
                    "submit_label": _("Guardar"),
                },
            )
            resp["HX-Retarget"] = "#dept-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        messages.error(request, _("Por favor corrija los errores."))
        return redirect("purchases:supplier_detail", pk=supplier_pk)


class SupplierDepartmentToggleView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def post(self, request, supplier_pk, dept_pk):
        supplier = get_object_or_404(Supplier, pk=supplier_pk, organization=request.organization)
        dept = get_object_or_404(SupplierDepartment, pk=dept_pk, supplier=supplier)
        dept.is_active = not dept.is_active
        dept.save(update_fields=["is_active", "updated_at"])
        if request.htmx:
            departments = supplier.departments.filter(deleted_at__isnull=True).order_by("name")
            return render(
                request,
                "purchases/partials/department_table.html",
                {"departments": departments, "supplier": supplier},
            )
        return redirect("purchases:supplier_detail", pk=supplier_pk)


class SupplierDepartmentDeleteView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def post(self, request, supplier_pk, dept_pk):
        supplier = get_object_or_404(Supplier, pk=supplier_pk, organization=request.organization)
        dept = get_object_or_404(SupplierDepartment, pk=dept_pk, supplier=supplier)
        name = dept.name
        dept.delete()

        if request.htmx:
            departments = supplier.departments.filter(deleted_at__isnull=True).order_by("name")
            resp = render(
                request,
                "purchases/partials/department_table.html",
                {"departments": departments, "supplier": supplier},
            )
            resp["HX-Trigger"] = json.dumps(
                {"showToast": {"message": str(_(f"Departamento «{name}» eliminado.")), "type": "success"}}
            )
            return resp
        messages.success(request, _(f"Departamento «{name}» eliminado."))
        return redirect("purchases:supplier_detail", pk=supplier_pk)


class SupplierDepartmentsView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def get(self, request, supplier_pk):
        supplier = get_object_or_404(Supplier, pk=supplier_pk, organization=request.organization)
        departments = supplier.departments.filter(deleted_at__isnull=True, is_active=True).order_by("name")
        return render(
            request,
            "purchases/partials/department_options.html",
            {"departments": departments},
        )
