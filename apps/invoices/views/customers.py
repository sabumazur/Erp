import json
from datetime import date

from django.contrib import messages
from django.db.models import Count, Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, UpdateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.datatable import DTColumn, DataTableMixin, build_datatable_context
from apps.core.search import fts_search
from ..filters import CustomerFilter
from ..forms import CustomerForm, CustomerDepartmentForm
from ..models import Customer, CustomerDepartment
from ._helpers import _org, _customers_with_depts


class CustomerListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "invoices/customer_list.html"
    required_module = "invoices"

    dt_columns = [
        DTColumn("name",             _("Nombre"),   sortable=True),
        DTColumn("rnc_cedula",       _("RNC/Cédula"),sortable=True),
        DTColumn("email",            _("Correo"),   sortable=False, visible=False),
        DTColumn("phone",            _("Teléfono"), sortable=False, visible=False),
        DTColumn("default_ncf_type", _("Tipo NCF"), sortable=False),
        DTColumn("depts",            _("Depts."),   sortable=False),
    ]
    dt_default_sort = "name"
    dt_url = "invoices:customer_list"
    dt_row_template = "invoices/partials/customer_row.html"
    dt_filter_template = "invoices/partials/customer_filters.html"
    dt_search_placeholder = _("Nombre o RNC…")
    dt_id = "customers"

    @classmethod
    def _refresh_table(cls, request, msg, msg_type="success"):
        qs = _customers_with_depts(_org(request))
        q = request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["name"], trgm_fields=["rnc_cedula"])
        f = CustomerFilter(request.GET, queryset=qs)
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
        resp["HX-Trigger"] = json.dumps({"showToast": {"message": msg, "type": msg_type}})
        return resp

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = _org(self.request)
        qs = _customers_with_depts(org)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["name"], trgm_fields=["rnc_cedula"])
        f = CustomerFilter(self.request.GET, queryset=qs)
        ctx["filter"] = f
        ctx.update(self.apply_datatable(f.qs))
        ctx["form"] = CustomerForm()

        today = date.today()
        active_dept = CustomerDepartment.objects.filter(
            customer=OuterRef("pk"), deleted_at__isnull=True, is_active=True,
        )
        stats_qs = Customer.objects.filter(organization=org)
        ctx["stats"] = [
            {"label": _("Total clientes"),     "value": stats_qs.count(),
             "icon": "bi-people",              "color": "primary"},
            {"label": _("Con límite de crédito"),"value": stats_qs.filter(credit_limit__isnull=False).count(),
             "icon": "bi-credit-card",         "color": "info"},
            {"label": _("Con departamentos"),  "value": stats_qs.filter(Exists(active_dept)).count(),
             "icon": "bi-building",            "color": "secondary"},
            {"label": _("Nuevos este mes"),    "value": stats_qs.filter(
                created_at__month=today.month, created_at__year=today.year,
             ).count(),
             "icon": "bi-person-plus",         "color": "success"},
        ]
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Clientes")},
        ]
        return ctx

    def post(self, request):
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.organization = _org(request)
            customer.save()
            if request.htmx:
                return self._refresh_table(request, str(_("Cliente creado correctamente.")))
            messages.success(request, _("Cliente creado correctamente."))
            return redirect("invoices:customer_list")

        if request.htmx:
            resp = render(
                request,
                "invoices/partials/customer_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("invoices:customer_list"),
                    "submit_label": _("Crear"),
                    "hx_target": "#dt-results",
                },
            )
            resp["HX-Retarget"] = "#customer-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class CustomerUpdateView(ERPBaseViewMixin, UpdateView):
    form_class = CustomerForm
    template_name = "invoices/customer_form.html"
    required_module = "invoices"
    success_url = None  # set in form_valid

    def get_success_url(self):
        from django.urls import reverse_lazy
        return reverse_lazy("invoices:customer_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Clientes"), "url": reverse("invoices:customer_list")},
            {"label": self.object.name},
        ]
        return ctx

    def get_object(self):
        return get_object_or_404(
            Customer, pk=self.kwargs["pk"], organization=_org(self.request)
        )

    def get(self, request, *args, **kwargs):
        if request.htmx:
            customer = self.get_object()
            form = CustomerForm(instance=customer)
            return render(
                request,
                "invoices/partials/customer_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("invoices:customer_edit", args=[customer.pk]),
                    "submit_label": _("Guardar"),
                    "hx_target": request.GET.get("hx_target", "#customer-table"),
                },
            )
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.htmx:
            hx_target = self.request.POST.get("_hx_target", "#customer-table")
            if hx_target == "#dt-results":
                return CustomerListView._refresh_table(
                    self.request, str(_("Cliente actualizado.")),
                )
            if hx_target != "#customer-table":
                messages.success(self.request, _("Cliente actualizado."))
                resp = HttpResponse()
                resp["HX-Refresh"] = "true"
                return resp
            resp = render(
                self.request,
                "invoices/partials/customer_table.html",
                {"customers": _customers_with_depts(_org(self.request))},
            )
            resp["HX-Trigger"] = json.dumps(
                {"showToast": {"message": str(_("Cliente actualizado.")), "type": "success"}}
            )
            return resp
        messages.success(self.request, _("Cliente actualizado."))
        return response

    def form_invalid(self, form):
        if self.request.htmx:
            customer = self.get_object()
            hx_target = self.request.POST.get("_hx_target", "#customer-table")
            resp = render(
                self.request,
                "invoices/partials/customer_modal_form.html",
                {
                    "form": form,
                    "action_url": reverse("invoices:customer_edit", args=[customer.pk]),
                    "submit_label": _("Guardar"),
                    "hx_target": hx_target,
                },
            )
            resp["HX-Retarget"] = "#customer-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        return super().form_invalid(form)


class CustomerDetailView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request, pk):
        from decimal import Decimal
        from django.db.models import DecimalField, Sum
        from django.db.models.functions import Coalesce
        from ..models import Invoice, Payment

        customer = get_object_or_404(Customer, pk=pk, organization=_org(request))
        departments = customer.departments.filter(deleted_at__isnull=True).order_by("name")

        _zero = Decimal("0.00")
        _dec_field = DecimalField(max_digits=14, decimal_places=2)

        invoices = list(
            Invoice.invoices.filter(organization=_org(request), customer=customer)
            .exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
            .annotate(
                paid_amount=Coalesce(Sum("allocations__amount"), _zero, output_field=_dec_field)
            )
            .select_related("customer")
            .order_by("-issue_date")
        )

        for inv in invoices:
            inv.line_balance = inv.total - inv.paid_amount

        total_invoiced = sum((inv.total for inv in invoices), _zero)
        total_paid = sum((inv.paid_amount for inv in invoices), _zero)
        balance = total_invoiced - total_paid
        overdue = sum(
            inv.line_balance for inv in invoices if inv.status == Invoice.Status.OVERDUE
        )

        _aging = {b: _zero for b in Invoice.AgingBucket.values}
        for inv in invoices:
            if inv.line_balance > _zero:
                _aging[inv.aging_bucket] += inv.line_balance
        aging_breakdown = [
            {"label": Invoice.AgingBucket(b).label, "amount": _aging[b], "bucket": b}
            for b in Invoice.AgingBucket.values
        ]

        recent_payments = list(
            Payment.objects.filter(customer=customer, organization=_org(request))
            .prefetch_related("allocations__invoice")
            .order_by("-date", "-created_at")[:30]
        )

        from ..forms import CustomerDepartmentForm as _DeptForm
        return render(
            request,
            "invoices/customer_detail.html",
            {
                **self.get_context(
                    customer=customer,
                    departments=departments,
                    dept_form=_DeptForm(),
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Clientes"), "url": reverse("invoices:customer_list")},
                        {"label": customer.name},
                    ],
                ),
                "invoices": invoices,
                "total_invoiced": total_invoiced,
                "total_paid": total_paid,
                "balance": balance,
                "overdue": overdue,
                "aging_breakdown": aging_breakdown,
                "recent_payments": recent_payments,
                "credit_available": (
                    (customer.credit_limit - balance)
                    if customer.credit_limit is not None
                    else None
                ),
            },
        )


class CustomerDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk, organization=_org(request))
        name = customer.name
        try:
            customer.delete()
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
            return redirect("invoices:customer_list")
        if request.htmx:
            return CustomerListView._refresh_table(
                request, str(_(f"Cliente «{name}» eliminado.")),
            )
        messages.success(request, _(f"Cliente «{name}» eliminado."))
        return redirect("invoices:customer_list")


# ── Customer Department CRUD ──────────────────────────────────────────────────


class CustomerDepartmentCreateView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def _customer(self, request, customer_pk):
        return get_object_or_404(Customer, pk=customer_pk, organization=_org(request))

    def _departments(self, customer):
        return customer.departments.filter(deleted_at__isnull=True).order_by("name")

    def get(self, request, customer_pk):
        customer = self._customer(request, customer_pk)
        form = CustomerDepartmentForm()
        return render(
            request,
            "invoices/partials/department_modal_form.html",
            {
                "form": form,
                "customer": customer,
                "action_url": reverse("invoices:department_create", args=[customer_pk]),
                "submit_label": _("Crear"),
            },
        )

    def post(self, request, customer_pk):
        customer = self._customer(request, customer_pk)
        form = CustomerDepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save(commit=False)
            dept.organization = _org(request)
            dept.customer = customer
            dept.save()
            if request.htmx:
                resp = render(
                    request,
                    "invoices/partials/department_table.html",
                    {"departments": self._departments(customer), "customer": customer},
                )
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showToast": {"message": str(_("Departamento creado.")), "type": "success"},
                        "closeDeptModal": True,
                    }
                )
                return resp
            messages.success(request, _("Departamento creado."))
            return redirect("invoices:customer_detail", pk=customer_pk)

        if request.htmx:
            resp = render(
                request,
                "invoices/partials/department_modal_form.html",
                {
                    "form": form,
                    "customer": customer,
                    "action_url": reverse("invoices:department_create", args=[customer_pk]),
                    "submit_label": _("Crear"),
                },
            )
            resp["HX-Retarget"] = "#dept-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        messages.error(request, _("Por favor corrija los errores."))
        return redirect("invoices:customer_detail", pk=customer_pk)


class CustomerDepartmentUpdateView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def _get_objects(self, request, customer_pk, pk):
        customer = get_object_or_404(Customer, pk=customer_pk, organization=_org(request))
        dept = get_object_or_404(CustomerDepartment, pk=pk, customer=customer)
        return customer, dept

    def _departments(self, customer):
        return customer.departments.filter(deleted_at__isnull=True).order_by("name")

    def get(self, request, customer_pk, pk):
        customer, dept = self._get_objects(request, customer_pk, pk)
        form = CustomerDepartmentForm(instance=dept)
        return render(
            request,
            "invoices/partials/department_modal_form.html",
            {
                "form": form,
                "customer": customer,
                "action_url": reverse("invoices:department_edit", args=[customer_pk, pk]),
                "submit_label": _("Guardar"),
            },
        )

    def post(self, request, customer_pk, pk):
        customer, dept = self._get_objects(request, customer_pk, pk)
        form = CustomerDepartmentForm(request.POST, instance=dept)
        if form.is_valid():
            form.save()
            if request.htmx:
                resp = render(
                    request,
                    "invoices/partials/department_table.html",
                    {"departments": self._departments(customer), "customer": customer},
                )
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showToast": {"message": str(_("Departamento actualizado.")), "type": "success"},
                        "closeDeptModal": True,
                    }
                )
                return resp
            messages.success(request, _("Departamento actualizado."))
            return redirect("invoices:customer_detail", pk=customer_pk)

        if request.htmx:
            resp = render(
                request,
                "invoices/partials/department_modal_form.html",
                {
                    "form": form,
                    "customer": customer,
                    "action_url": reverse("invoices:department_edit", args=[customer_pk, pk]),
                    "submit_label": _("Guardar"),
                },
            )
            resp["HX-Retarget"] = "#dept-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        messages.error(request, _("Por favor corrija los errores."))
        return redirect("invoices:customer_detail", pk=customer_pk)


class CustomerDepartmentToggleView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, customer_pk, pk):
        customer = get_object_or_404(Customer, pk=customer_pk, organization=_org(request))
        dept = get_object_or_404(CustomerDepartment, pk=pk, customer=customer)
        dept.is_active = not dept.is_active
        dept.save(update_fields=["is_active", "updated_at"])
        if request.htmx:
            departments = customer.departments.filter(deleted_at__isnull=True).order_by("name")
            return render(
                request,
                "invoices/partials/department_table.html",
                {"departments": departments, "customer": customer},
            )
        return redirect("invoices:customer_detail", pk=customer_pk)


class CustomerDepartmentDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def post(self, request, customer_pk, pk):
        from ..models import Invoice
        customer = get_object_or_404(Customer, pk=customer_pk, organization=_org(request))
        dept = get_object_or_404(CustomerDepartment, pk=pk, customer=customer)

        order_count = Invoice.sale_orders.filter(
            organization=_org(request), department=dept
        ).count()
        if order_count:
            msg = _(
                f"No se puede eliminar «{dept.name}»: "
                f"{order_count} orden(es) de venta lo tienen asignado."
            )
            if request.htmx:
                resp = HttpResponse()
                resp["HX-Reswap"] = "none"
                resp["HX-Trigger"] = json.dumps({"showSwal": {
                    "icon": "error",
                    "title": str(_("No se puede eliminar")),
                    "text": str(msg),
                }})
                return resp
            messages.error(request, str(msg))
            return redirect("invoices:customer_detail", pk=customer_pk)

        name = dept.name
        dept.delete()

        if request.htmx:
            departments = customer.departments.filter(deleted_at__isnull=True).order_by("name")
            resp = render(
                request,
                "invoices/partials/department_table.html",
                {"departments": departments, "customer": customer},
            )
            resp["HX-Trigger"] = json.dumps(
                {"showToast": {"message": str(_(f"Departamento «{name}» eliminado.")), "type": "success"}}
            )
            return resp

        messages.success(request, _(f"Departamento «{name}» eliminado."))
        return redirect("invoices:customer_detail", pk=customer_pk)
