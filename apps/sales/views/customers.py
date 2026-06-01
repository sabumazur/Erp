import json
from datetime import date

from django.contrib import messages
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, UpdateView, CreateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.history import record_change_reason
from apps.core.mixins import HistoryMixin
from apps.core.datatable import DTColumn, DataTableMixin, build_datatable_context
from apps.core.search import fts_search
from ..filters import CustomerFilter
from ..forms import CustomerForm, CustomerDepartmentForm
from ..models import Customer, CustomerDepartment
from ._helpers import _customers_with_depts


DEPARTMENT_DT_COLUMNS = [
    DTColumn("name", _("Nombre"), sortable=True),
    DTColumn("contact_name", _("Contacto"), sortable=True),
    DTColumn("phone", _("Teléfono"), sortable=True),
    DTColumn("address", _("Dirección de entrega"), sortable=True),
    DTColumn("is_active", _("Estado"), sortable=True),
]


def _department_qs(customer):
    return customer.departments.filter(deleted_at__isnull=True)


def _department_datatable_context(request, customer):
    qs = _department_qs(customer)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(contact_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(address__icontains=q)
        )

    ctx = build_datatable_context(
        request,
        qs,
        DEPARTMENT_DT_COLUMNS,
        default_sort="name",
        page_size=10,
        row_template="sales/partials/department_row.html",
        ribbon_template="sales/partials/department_ribbon.html",
        search_placeholder=_("Buscar departamentos…"),
        dt_id=f"customer-departments-{customer.pk}",
    )
    ctx.update(
        {
            "customer": customer,
            "dt_action_url": reverse("sales:department_table", args=[customer.pk]),
            "dt_push_url": "false",
        }
    )
    return ctx


class CustomerListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "sales/customer_list.html"
    required_module = "sales"

    dt_columns = [
        DTColumn("name",             _("Nombre"),   sortable=True),
        DTColumn("rnc_cedula",       _("RNC/Cédula"),sortable=True),
        DTColumn("email",            _("Correo"),   sortable=False, visible=False),
        DTColumn("phone",            _("Teléfono"), sortable=False, visible=False),
        DTColumn("default_ncf_type", _("Tipo NCF"), sortable=False),
        DTColumn("depts",            _("Depts."),   sortable=False),
    ]
    dt_default_sort = "name"
    dt_url = "sales:customer_list"
    dt_row_template = "sales/partials/customer_row.html"
    dt_filter_template = "sales/partials/customer_filters.html"
    dt_ribbon_template = "sales/partials/customer_ribbon.html"
    dt_search_placeholder = _("Nombre o RNC…")
    dt_id = "customers"

    @classmethod
    def _refresh_table(cls, request, msg, msg_type="success"):
        qs = _customers_with_depts(request.organization)
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
        org = self.request.organization
        qs = _customers_with_depts(org)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["name"], trgm_fields=["rnc_cedula"])
        f = CustomerFilter(self.request.GET, queryset=qs)
        ctx["filter"] = f
        ctx.update(self.apply_datatable(f.qs))
        if not self.request.htmx:
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
        ctx["module"] = "customer"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Clientes")},
        ]
        return ctx

class CustomerCreateView(ERPBaseViewMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "sales/customer_form.html"
    required_module = "sales"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["module"] = "customer"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Clientes"), "url": reverse("sales:customer_list")},
            {"label": _("Nuevo cliente")},
        ]
        return ctx

    def form_valid(self, form):
        form.instance.organization = self.request.organization
        customer = form.save()
        messages.success(self.request, _("Cliente creado correctamente."))
        return redirect("sales:customer_detail", pk=customer.pk)


class CustomerUpdateView(ERPBaseViewMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "sales/customer_form.html"
    required_module = "sales"

    def get_object(self):
        return get_object_or_404(
            Customer, pk=self.kwargs["pk"], organization=self.request.organization
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organization"] = self.request.organization
        return kwargs

    def get_context_data(self, **kwargs):
        from ..models import SalesDocument, Payment

        ctx = super().get_context_data(**kwargs)
        customer = self.object
        org = self.request.organization

        invoice_count = SalesDocument.invoices.filter(
            organization=org, customer=customer
        ).exclude(
            status__in=[SalesDocument.Status.DRAFT, SalesDocument.Status.CANCELLED]
        ).count()

        payment_count = Payment.objects.filter(
            customer=customer, organization=org
        ).count()

        dept_count = customer.departments.filter(
            deleted_at__isnull=True, is_active=True
        ).count()

        ctx["smart_buttons"] = {
            "invoice_count": invoice_count,
            "payment_count": payment_count,
            "dept_count": dept_count,
            "detail_url": reverse("sales:customer_detail", args=[customer.pk]),
        }
        ctx["module"] = "customer"
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Clientes"), "url": reverse("sales:customer_list")},
            {"label": customer.name},
        ]
        return ctx

    def form_valid(self, form):
        self.object = form.save()
        record_change_reason(self.object, form.cleaned_data.get("change_reason", ""))
        messages.success(self.request, _("Cliente actualizado."))
        return redirect("sales:customer_detail", pk=self.object.pk)


class CustomerDetailView(HistoryMixin, ERPBaseViewMixin, View):
    required_module = "sales"

    def get(self, request, pk):
        from decimal import Decimal
        from django.db.models import DecimalField, Sum
        from django.db.models.functions import Coalesce
        from ..models import SalesDocument, Payment

        customer = get_object_or_404(Customer, pk=pk, organization=request.organization)
        _zero = Decimal("0.00")
        _dec_field = DecimalField(max_digits=14, decimal_places=2)

        invoices = list(
            SalesDocument.invoices.filter(organization=request.organization, customer=customer)
            .exclude(status__in=[SalesDocument.Status.DRAFT, SalesDocument.Status.CANCELLED])
            .with_signed_totals()
            .annotate(
                paid_amount=Coalesce(Sum("allocations__amount"), _zero, output_field=_dec_field)
            )
            .select_related("customer")
            .order_by("-issue_date")
        )

        for inv in invoices:
            inv.line_balance = inv.signed_total - inv.paid_amount

        total_invoiced = sum((inv.signed_total for inv in invoices), _zero)
        total_paid = sum((inv.paid_amount for inv in invoices), _zero)
        balance = total_invoiced - total_paid
        overdue = sum(
            inv.line_balance for inv in invoices if inv.status == SalesDocument.Status.OVERDUE
        )

        _aging = {b: _zero for b in SalesDocument.AgingBucket.values}
        for inv in invoices:
            if inv.line_balance > _zero:
                _aging[inv.aging_bucket] += inv.line_balance
        aging_breakdown = [
            {"label": SalesDocument.AgingBucket(b).label, "amount": _aging[b], "bucket": b}
            for b in SalesDocument.AgingBucket.values
        ]

        recent_payments = list(
            Payment.objects.filter(customer=customer, organization=request.organization)
            .prefetch_related("allocations__invoice")
            .order_by("-date", "-created_at")[:30]
        )

        from ..forms import CustomerDepartmentForm as _DeptForm
        return render(
            request,
            "sales/customer_detail.html",
            {
                **self.get_context(
                    module="customer",
                    customer=customer,
                    dept_table=_department_datatable_context(request, customer),
                    dept_form=_DeptForm(),
                    breadcrumbs=[
                        {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                        {"label": _("Clientes"), "url": reverse("sales:customer_list")},
                        {"label": customer.name},
                    ],
                ),
                "history_records": self.get_history(customer),
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
    required_module = "sales"
    admin_required = True

    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk, organization=request.organization)
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
            return redirect("sales:customer_list")
        if request.htmx:
            return CustomerListView._refresh_table(
                request, str(_(f"Cliente «{name}» eliminado.")),
            )
        messages.success(request, _(f"Cliente «{name}» eliminado."))
        return redirect("sales:customer_list")


# ── Customer Department CRUD ──────────────────────────────────────────────────


class CustomerDepartmentTableView(ERPBaseViewMixin, View):
    required_module = "sales"

    def get(self, request, customer_pk):
        customer = get_object_or_404(Customer, pk=customer_pk, organization=request.organization)
        if request.htmx:
            return render(
                request,
                "components/datatable/results.html",
                _department_datatable_context(request, customer),
            )
        return redirect("sales:customer_detail", pk=customer_pk)


class CustomerDepartmentCreateView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def _customer(self, request, customer_pk):
        return get_object_or_404(Customer, pk=customer_pk, organization=request.organization)

    def get(self, request, customer_pk):
        if not request.htmx:
            return redirect("sales:customer_detail", pk=customer_pk)
        customer = self._customer(request, customer_pk)
        form = CustomerDepartmentForm()
        return render(
            request,
            "sales/partials/department_modal_form.html",
            {
                "form": form,
                "customer": customer,
                "action_url": reverse("sales:department_create", args=[customer_pk]),
                "submit_label": _("Crear"),
            },
        )

    def post(self, request, customer_pk):
        customer = self._customer(request, customer_pk)
        form = CustomerDepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save(commit=False)
            dept.organization = request.organization
            dept.customer = customer
            dept.save()
            if request.htmx:
                resp = render(
                    request,
                    "components/datatable/results.html",
                    _department_datatable_context(request, customer),
                )
                resp["HX-Retarget"] = "#dt-results"
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showToast": {"message": str(_("Departamento creado.")), "type": "success"},
                        "closeDeptModal": True,
                    }
                )
                return resp
            messages.success(request, _("Departamento creado."))
            return redirect("sales:customer_detail", pk=customer_pk)

        if request.htmx:
            resp = render(
                request,
                "sales/partials/department_modal_form.html",
                {
                    "form": form,
                    "customer": customer,
                    "action_url": reverse("sales:department_create", args=[customer_pk]),
                    "submit_label": _("Crear"),
                },
            )
            resp["HX-Retarget"] = "#dept-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        messages.error(request, _("Por favor corrija los errores."))
        return redirect("sales:customer_detail", pk=customer_pk)


class CustomerDepartmentUpdateView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def _get_objects(self, request, customer_pk, pk):
        customer = get_object_or_404(Customer, pk=customer_pk, organization=request.organization)
        dept = get_object_or_404(CustomerDepartment, pk=pk, customer=customer)
        return customer, dept

    def get(self, request, customer_pk, pk):
        if not request.htmx:
            return redirect("sales:customer_detail", pk=customer_pk)
        customer, dept = self._get_objects(request, customer_pk, pk)
        form = CustomerDepartmentForm(instance=dept)
        return render(
            request,
            "sales/partials/department_modal_form.html",
            {
                "form": form,
                "customer": customer,
                "action_url": reverse("sales:department_edit", args=[customer_pk, pk]),
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
                    "components/datatable/results.html",
                    _department_datatable_context(request, customer),
                )
                resp["HX-Retarget"] = "#dt-results"
                resp["HX-Trigger"] = json.dumps(
                    {
                        "showToast": {"message": str(_("Departamento actualizado.")), "type": "success"},
                        "closeDeptModal": True,
                    }
                )
                return resp
            messages.success(request, _("Departamento actualizado."))
            return redirect("sales:customer_detail", pk=customer_pk)

        if request.htmx:
            resp = render(
                request,
                "sales/partials/department_modal_form.html",
                {
                    "form": form,
                    "customer": customer,
                    "action_url": reverse("sales:department_edit", args=[customer_pk, pk]),
                    "submit_label": _("Guardar"),
                },
            )
            resp["HX-Retarget"] = "#dept-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp
        messages.error(request, _("Por favor corrija los errores."))
        return redirect("sales:customer_detail", pk=customer_pk)


class CustomerDepartmentToggleView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def post(self, request, customer_pk, pk):
        customer = get_object_or_404(Customer, pk=customer_pk, organization=request.organization)
        dept = get_object_or_404(CustomerDepartment, pk=pk, customer=customer)
        dept.is_active = not dept.is_active
        dept.save(update_fields=["is_active", "updated_at"])
        if request.htmx:
            return render(
                request,
                "components/datatable/results.html",
                _department_datatable_context(request, customer),
            )
        return redirect("sales:customer_detail", pk=customer_pk)


class CustomerDepartmentDeleteView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def post(self, request, customer_pk, pk):
        from ..models import SalesDocument
        customer = get_object_or_404(Customer, pk=customer_pk, organization=request.organization)
        dept = get_object_or_404(CustomerDepartment, pk=pk, customer=customer)

        order_count = SalesDocument.sale_orders.filter(
            organization=request.organization, department=dept
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
            return redirect("sales:customer_detail", pk=customer_pk)

        name = dept.name
        dept.delete()

        if request.htmx:
            resp = render(
                request,
                "components/datatable/results.html",
                _department_datatable_context(request, customer),
            )
            resp["HX-Retarget"] = "#dt-results"
            resp["HX-Trigger"] = json.dumps(
                {"showToast": {"message": str(_(f"Departamento «{name}» eliminado.")), "type": "success"}}
            )
            return resp

        messages.success(request, _(f"Departamento «{name}» eliminado."))
        return redirect("sales:customer_detail", pk=customer_pk)
