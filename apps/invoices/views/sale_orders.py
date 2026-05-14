from datetime import date

from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, DetailView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.datatable import DTColumn, DataTableMixin
from apps.core.search import fts_search
from ..filters import SaleOrderFilter
from ..forms import SaleOrderForm, InvoiceItemFormSet, SaleOrderDeliverForm, ConsolidateForm
from ..models import Invoice, InvoiceItem, CustomerDepartment
from ..email import send_sale_order_email
from ..services import SaleOrderService
from ._helpers import _org, _sale_items_json, _customer_defaults_json


class SaleOrderListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "invoices/sale_order_list.html"
    required_module = "invoices"

    dt_columns = [
        DTColumn("doc_number",     _("Número"),     sortable=True),
        DTColumn("customer__name", _("Cliente"),    sortable=True),
        DTColumn("department__name",_("Depto."),    sortable=True, visible=False),
        DTColumn("issue_date",     _("Emisión"),    sortable=True),
        DTColumn("delivery_date",  _("Entrega"),    sortable=True),
        DTColumn("total",          _("Total"),      sortable=True, numeric=True),
        DTColumn("status",         _("Estado"),     sortable=False, classes="text-center"),
    ]
    dt_default_sort = "-delivery_date"
    dt_url = "invoices:sale_order_list"
    dt_row_template = "invoices/partials/sale_order_row.html"
    dt_filter_template = "invoices/partials/sale_order_filters.html"
    dt_search_placeholder = _("Número o cliente…")
    dt_id = "sale_orders"

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        org = _org(self.request)
        qs = (
            Invoice.sale_orders.filter(organization=org)
            .select_related("customer", "department")
        )
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = fts_search(qs, q, fts_fields=["customer__name"], trgm_fields=["doc_number"])
        f = SaleOrderFilter(self.request.GET, queryset=qs, organization=org)
        ctx["filter"] = f
        ctx.update(self.apply_datatable(f.qs))

        agg = Invoice.sale_orders.filter(organization=org).aggregate(
            total_count=Count("id"),
            pending_count=Count("id", filter=Q(status__in=[
                Invoice.Status.DRAFT, Invoice.Status.CONFIRMED,
            ])),
            delivered_count=Count("id", filter=Q(status=Invoice.Status.DELIVERED)),
            invoiced_count=Count("id", filter=Q(status=Invoice.Status.INVOICED)),
        )
        ctx["stats"] = [
            {"label": _("Total órdenes"),   "value": agg["total_count"],
             "icon": "bi-cart3",            "color": "primary"},
            {"label": _("Pendientes"),      "value": agg["pending_count"],
             "icon": "bi-hourglass-split",  "color": "warning"},
            {"label": _("Entregadas"),      "value": agg["delivered_count"],
             "icon": "bi-truck",            "color": "info"},
            {"label": _("Facturadas"),      "value": agg["invoiced_count"],
             "icon": "bi-receipt-cutoff",   "color": "success"},
        ]
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de venta")},
        ]
        return ctx


class SaleOrderCreateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/sale_order_form.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", SaleOrderForm(organization=_org(self.request)))
        ctx.setdefault("formset", InvoiceItemFormSet())
        ctx["sale_items_json"] = _sale_items_json(self.request)
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de venta"), "url": reverse("invoices:sale_order_list")},
            {"label": _("Nueva orden")},
        ]
        return ctx

    def post(self, request):
        form = SaleOrderForm(organization=_org(request), data=request.POST)
        formset = InvoiceItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            order = form.save(commit=False)
            order.organization = _org(request)
            order.doc_type = Invoice.DocType.SALE_ORDER
            order.save()
            formset.instance = order
            formset.save()
            messages.success(request, _("Orden de venta creada como borrador."))
            return redirect("invoices:sale_order_detail", pk=order.pk)
        ctx = self.get_context_data()
        ctx["form"] = form
        ctx["formset"] = formset
        return self.render_to_response(ctx)


class SaleOrderDetailView(ERPBaseViewMixin, DetailView):
    template_name = "invoices/sale_order_detail.html"
    required_module = "invoices"
    context_object_name = "order"

    def get_object(self):
        return get_object_or_404(
            Invoice.sale_orders.select_related("customer", "organization", "consolidated_into", "department"),
            pk=self.kwargs["pk"],
            organization=_org(self.request),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all()
        ctx["deliver_form"] = SaleOrderDeliverForm()
        o = self.object
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de venta"), "url": reverse("invoices:sale_order_list")},
            {"label": o.doc_number or str(_("Borrador"))},
        ]
        return ctx


class SaleOrderUpdateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/sale_order_form.html"
    required_module = "invoices"

    def _get_order(self, request, pk):
        o = get_object_or_404(Invoice.sale_orders, pk=pk, organization=_org(request))
        if not o.is_editable:
            messages.error(request, _("Solo se pueden editar órdenes en Borrador."))
            return None, redirect("invoices:sale_order_detail", pk=o.pk)
        return o, None

    def get(self, request, pk):
        o, redir = self._get_order(request, pk)
        if redir:
            return redir
        ctx = self.get_context_data(
            form=SaleOrderForm(organization=_org(request), instance=o),
            formset=InvoiceItemFormSet(instance=o),
            order=o,
        )
        return self.render_to_response(ctx)

    def post(self, request, pk):
        o, redir = self._get_order(request, pk)
        if redir:
            return redir
        form = SaleOrderForm(organization=_org(request), data=request.POST, instance=o)
        formset = InvoiceItemFormSet(request.POST, instance=o)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Orden de venta actualizada."))
            return redirect("invoices:sale_order_detail", pk=o.pk)
        ctx = self.get_context_data(form=form, formset=formset, order=o)
        return self.render_to_response(ctx)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", SaleOrderForm(organization=_org(self.request)))
        ctx.setdefault("formset", InvoiceItemFormSet())
        ctx["sale_items_json"] = _sale_items_json(self.request)
        ctx["customer_defaults_json"] = _customer_defaults_json(self.request)
        o = kwargs.get("order")
        if o:
            ctx["breadcrumbs"] = [
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Órdenes de venta"), "url": reverse("invoices:sale_order_list")},
                {
                    "label": o.doc_number or str(_("Borrador")),
                    "url": reverse("invoices:sale_order_detail", args=[o.pk]),
                },
                {"label": _("Editar")},
            ]
        return ctx


# ── Sale Order transitions ────────────────────────────────────────────────────


class SaleOrderConfirmView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        o = get_object_or_404(Invoice.sale_orders, pk=pk, organization=_org(request))
        try:
            SaleOrderService.confirm(o)
            messages.success(request, _(f"Orden confirmada: {o.doc_number}"))
        except (ValueError, Exception) as exc:
            messages.error(request, str(exc))
        return redirect("invoices:sale_order_detail", pk=o.pk)


class SaleOrderDeliverView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        o = get_object_or_404(Invoice.sale_orders, pk=pk, organization=_org(request))
        form = SaleOrderDeliverForm(request.POST)
        if not form.is_valid():
            messages.error(request, _("Debe indicar el nombre de quien recibe la entrega."))
            return redirect("invoices:sale_order_detail", pk=o.pk)
        try:
            SaleOrderService.mark_delivered(o, form.cleaned_data["signed_by"])
            messages.success(request, _(f"Orden marcada como entregada. Recibido por: {o.signed_by}"))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:sale_order_detail", pk=o.pk)


class SaleOrderCancelView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        o = get_object_or_404(Invoice.sale_orders, pk=pk, organization=_org(request))
        try:
            SaleOrderService.cancel(o)
            messages.success(request, _("Orden de venta anulada."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("invoices:sale_order_detail", pk=o.pk)


class SaleOrderDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        o = get_object_or_404(Invoice.sale_orders, pk=pk, organization=_org(request))
        if o.status != Invoice.Status.DRAFT:
            messages.error(request, _("Solo se pueden eliminar órdenes en Borrador."))
            return redirect("invoices:sale_order_detail", pk=o.pk)
        o.hard_delete()
        messages.success(request, _("Orden eliminada."))
        return redirect("invoices:sale_order_list")


class SaleOrderEmailView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        o = get_object_or_404(Invoice.sale_orders, pk=pk, organization=_org(request))
        try:
            sent = send_sale_order_email(o, request)
            if sent:
                messages.success(request, _("Correo enviado a %(email)s.") % {"email": o.customer.email})
            else:
                messages.warning(request, _("El cliente no tiene correo registrado."))
        except Exception as exc:
            messages.error(request, _("No se pudo enviar el correo: %(error)s") % {"error": str(exc)})
        return redirect("invoices:sale_order_detail", pk=o.pk)


# ── Consolidation ─────────────────────────────────────────────────────────────


class SaleOrderConsolidateView(ERPBaseViewMixin, TemplateView):
    template_name = "invoices/sale_order_consolidate.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", ConsolidateForm(organization=_org(self.request)))
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Órdenes de venta"), "url": reverse("invoices:sale_order_list")},
            {"label": _("Consolidar en factura")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        if request.htmx and request.GET.get("preview"):
            return self._render_preview(request)
        return self.render_to_response(self.get_context_data())

    def _render_preview(self, request):
        from datetime import datetime
        customer_id = request.GET.get("customer", "").strip()
        department_id = request.GET.get("department", "").strip()
        start = request.GET.get("period_start")
        end = request.GET.get("period_end")

        orders = []
        grand_total = 0
        if customer_id and start and end:
            try:
                p_start = datetime.strptime(start, "%Y-%m-%d").date()
                p_end = datetime.strptime(end, "%Y-%m-%d").date()
                qs = (
                    Invoice.sale_orders.filter(
                        organization=_org(request),
                        customer_id=customer_id,
                        status=Invoice.Status.DELIVERED,
                        consolidated_into__isnull=True,
                        delivery_date__gte=p_start,
                        delivery_date__lte=p_end,
                    )
                    .select_related("customer", "department")
                    .order_by("delivery_date")
                )
                if department_id:
                    qs = qs.filter(department_id=department_id)
                orders = list(qs)
                grand_total = sum(o.total for o in orders)
            except (ValueError, TypeError):
                pass

        return render(
            request, "invoices/partials/consolidate_preview.html",
            {"orders": orders, "grand_total": grand_total},
        )

    def post(self, request):
        form = ConsolidateForm(organization=_org(request), data=request.POST)
        if not form.is_valid():
            ctx = self.get_context_data()
            ctx["form"] = form
            return self.render_to_response(ctx)

        cd = form.cleaned_data
        try:
            invoice = SaleOrderService.consolidate_and_invoice(
                organization=_org(request),
                customer=cd["customer"],
                period_start=cd["period_start"],
                period_end=cd["period_end"],
                ncf_type=int(cd["ncf_type"]),
                department=cd.get("department"),
            )
            messages.success(request, _("Se generó la factura consolidada. Revise y confirme el e-NCF."))
            return redirect("invoices:invoice_detail", pk=invoice.pk)
        except ValueError as exc:
            messages.error(request, str(exc))
            ctx = self.get_context_data()
            ctx["form"] = form
            return self.render_to_response(ctx)


class SaleOrderCloneView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def post(self, request, pk):
        source = get_object_or_404(
            Invoice.objects.prefetch_related("items"),
            pk=pk, organization=_org(request), doc_type=Invoice.DocType.SALE_ORDER,
        )
        new_order = Invoice.objects.create(
            organization=source.organization,
            doc_type=Invoice.DocType.SALE_ORDER,
            status=Invoice.Status.DRAFT,
            customer=source.customer,
            department=source.department,
            issue_date=date.today(),
            payment_condition=source.payment_condition,
            currency=source.currency,
            exchange_rate=source.exchange_rate,
            notes=source.notes,
            terms=getattr(source, "terms", ""),
        )
        InvoiceItem.objects.bulk_create(
            [
                InvoiceItem(
                    invoice=new_order,
                    item=line.item,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    itbis_rate=line.itbis_rate,
                )
                for line in source.items.all()
            ]
        )
        messages.success(request, _("Orden clonada correctamente. Revise y confirme el nuevo borrador."))
        return redirect("invoices:sale_order_edit", pk=new_order.pk)


class SaleOrderPrintView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request, pk):
        order = get_object_or_404(
            Invoice.objects.select_related("customer", "organization", "department"),
            pk=pk, organization=_org(request), doc_type=Invoice.DocType.SALE_ORDER,
        )
        return render(
            request, "invoices/sale_order_print.html",
            {"order": order, "items": order.items.all(), "org": order.organization},
        )


# ── HTMX: department options for a customer ──────────────────────────────────


class CustomerDepartmentsView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request):
        customer_id = request.GET.get("customer", "").strip()
        departments = []
        if customer_id:
            departments = list(
                CustomerDepartment.objects.filter(
                    customer_id=customer_id,
                    organization=_org(request),
                    is_active=True,
                    deleted_at__isnull=True,
                ).order_by("name")
            )
        return render(
            request, "invoices/partials/department_options.html",
            {"departments": departments},
        )
