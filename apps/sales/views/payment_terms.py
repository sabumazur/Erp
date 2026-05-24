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
from ..filters import PaymentTermFilter
from ..forms import PaymentTermForm
from ..models import PaymentTerm


# ── List + Create ─────────────────────────────────────────────────────────────

class PaymentTermListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "sales/payment_term_list.html"
    required_module = "sales"
    admin_required = True

    dt_columns = [
        DTColumn("name",     _("Nombre"),              sortable=True),
        DTColumn("days_due", _("Días vencimiento"),    sortable=True, classes="text-center"),
        DTColumn("description", _("Descripción"),      sortable=False),
    ]
    dt_default_sort = "days_due"
    dt_page_size = 25
    dt_url = "sales:payment_term_list"
    dt_row_template = "sales/partials/payment_term_row.html"
    dt_ribbon_template = "sales/partials/payment_term_ribbon.html"
    dt_filter_template = "sales/partials/payment_term_filters.html"
    dt_search_placeholder = _("Nombre…")

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        qs = PaymentTerm.objects.filter(organization=request.organization)
        f = PaymentTermFilter(request.GET, queryset=qs)
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
        qs = PaymentTerm.objects.filter(organization=self.request.organization)
        f  = PaymentTermFilter(self.request.GET, queryset=qs)
        ctx.update(self.apply_datatable(f.qs))
        ctx["filter"]       = f
        ctx["form"]         = PaymentTermForm()
        ctx["create_url"]   = reverse("sales:payment_term_list")
        ctx["submit_label"] = _("Crear")
        ctx["breadcrumbs"]  = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Términos de pago")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def post(self, request):
        form = PaymentTermForm(request.POST)
        if form.is_valid():
            term = form.save(commit=False)
            term.organization = request.organization
            term.save()
            if request.htmx:
                return PaymentTermListView.refresh_table(
                    request, _("Término de pago creado correctamente.")
                )
            messages.success(request, _("Término de pago creado correctamente."))
            return redirect("sales:payment_term_list")

        if request.htmx:
            resp = render(request, "sales/partials/payment_term_modal_form.html", {
                "form":         form,
                "action_url":   reverse("sales:payment_term_list"),
                "submit_label": _("Crear"),
            })
            resp["HX-Retarget"] = "#payment-term-modal-body"
            resp["HX-Reswap"]   = "innerHTML"
            return resp

        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


# ── Update ────────────────────────────────────────────────────────────────────

class PaymentTermUpdateView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def get(self, request, pk):
        term = get_object_or_404(PaymentTerm, pk=pk, organization=request.organization)
        form = PaymentTermForm(instance=term)

        if request.htmx:
            return render(request, "sales/partials/payment_term_modal_form.html", {
                "form":         form,
                "action_url":   reverse("sales:payment_term_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })

        ctx = self.get_context(
            form=form, term=term,
            breadcrumbs=[
                {"label": _("Dashboard"),          "url": reverse("accounts:dashboard")},
                {"label": _("Términos de pago"),   "url": reverse("sales:payment_term_list")},
                {"label": term.name},
            ],
        )
        return render(request, "sales/payment_term_form.html", ctx)

    def post(self, request, pk):
        term = get_object_or_404(PaymentTerm, pk=pk, organization=request.organization)
        form = PaymentTermForm(request.POST, instance=term)

        if form.is_valid():
            form.save()
            if request.htmx:
                return PaymentTermListView.refresh_table(
                    request, _("Término de pago actualizado correctamente.")
                )
            messages.success(request, _("Término de pago actualizado correctamente."))
            return redirect("sales:payment_term_list")

        if request.htmx:
            resp = render(request, "sales/partials/payment_term_modal_form.html", {
                "form":         form,
                "action_url":   reverse("sales:payment_term_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })
            resp["HX-Retarget"] = "#payment-term-modal-body"
            resp["HX-Reswap"]   = "innerHTML"
            return resp

        ctx = self.get_context(
            form=form, term=term,
            breadcrumbs=[
                {"label": _("Dashboard"),          "url": reverse("accounts:dashboard")},
                {"label": _("Términos de pago"),   "url": reverse("sales:payment_term_list")},
                {"label": term.name},
            ],
        )
        return render(request, "sales/payment_term_form.html", ctx)


# ── Delete ────────────────────────────────────────────────────────────────────

class PaymentTermDeleteView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def post(self, request, pk):
        term = get_object_or_404(PaymentTerm, pk=pk, organization=request.organization)
        name = term.name

        customers_using = term.customer_set.count()
        if customers_using:
            msg = _(
                f"No se puede eliminar «{name}»: "
                f"{customers_using} cliente(s) lo tienen asignado."
            )
            if request.htmx:
                resp = HttpResponse()
                resp["HX-Reswap"]  = "none"
                resp["HX-Trigger"] = json.dumps({"showSwal": {
                    "icon":  "error",
                    "title": str(_("No se puede eliminar")),
                    "text":  str(msg),
                }})
                return resp
            messages.error(request, str(msg))
            return redirect("sales:payment_term_list")

        term.delete()
        if request.htmx:
            return PaymentTermListView.refresh_table(
                request, _(f"Término «{name}» eliminado.")
            )
        messages.success(request, _(f"Término «{name}» eliminado."))
        return redirect("sales:payment_term_list")
