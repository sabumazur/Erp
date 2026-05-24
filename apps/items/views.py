import json

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.history import record_change_reason
from apps.core.mixins import HistoryMixin
from apps.core.datatable import DTColumn, DataTableMixin, build_datatable_context
from .filters import ItemFilter
from .forms import ItemForm
from .models import Item, item_catalog_search


# ── List + Create ─────────────────────────────────────────────────────────────

class ItemListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "items/item_list.html"
    required_module = "sales"

    dt_columns = [
        DTColumn("code",       _("Código"),   sortable=True),
        DTColumn("name",       _("Nombre"),   sortable=True),
        DTColumn("item_type",  _("Tipo"),     sortable=True),
        DTColumn("unit",       _("Unidad"),   sortable=False),
        DTColumn("unit_price", _("P. Venta"), sortable=True,  numeric=True),
        DTColumn("cost_price", _("P. Costo"), sortable=True,  numeric=True, visible=False),
        DTColumn("itbis_rate", _("ITBIS"),    sortable=False),
        DTColumn("is_active",  _("Estado"),   sortable=True),
    ]
    dt_default_sort = "name"
    dt_page_size = 15
    dt_url = "items:item_list"
    dt_row_template = "items/partials/item_row.html"
    dt_filter_template = "items/partials/item_filters.html"
    dt_ribbon_template = "items/partials/item_ribbon.html"
    dt_search_placeholder = _("Nombre o código…")

    @classmethod
    def columns_for(cls, request):
        if request.membership.is_admin:
            return cls.dt_columns
        return [column for column in cls.dt_columns if column.key != "cost_price"]

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        """
        Called by action views (create / edit / toggle / delete) to refresh
        the datatable after a mutation.  Returns a partial response that HTMX
        swaps into #dt-results, with a toast notification.
        """
        qs = Item.objects.for_org(request.organization)
        f = ItemFilter(request.GET, queryset=qs)
        ctx = build_datatable_context(
            request, f.qs, cls.columns_for(request),
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
        qs = Item.objects.for_org(self.request.organization)
        f  = ItemFilter(self.request.GET, queryset=qs)
        ctx.update(build_datatable_context(
            self.request,
            f.qs,
            self.columns_for(self.request),
            default_sort=self.dt_default_sort,
            page_size=self.dt_page_size,
            url=self.dt_url,
            row_template=self.dt_row_template,
            filter_template=self.dt_filter_template,
            search_placeholder=self.dt_search_placeholder,
            dt_id=self.dt_id,
        ))
        ctx["filter"] = f
        if self.request.membership.is_admin:
            ctx["form"] = ItemForm(organization=self.request.organization)
        ctx["module"]              = "item"
        ctx["create_url"]          = reverse("items:item_list")
        ctx["submit_label"]        = _("Crear")
        ctx["breadcrumbs"]         = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Artículos")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def post(self, request):
        if not request.membership.is_admin:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        form = ItemForm(request.POST, organization=request.organization)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = request.organization
            item.save()
            if request.htmx:
                return ItemListView.refresh_table(request, _("Artículo creado correctamente."))
            messages.success(request, _("Artículo creado correctamente."))
            return redirect("items:item_list")

        if request.htmx:
            resp = render(request, "items/partials/item_modal_form.html", {
                "form":              form,
                "action_url":        reverse("items:item_list"),
                "submit_label":      _("Crear"),
                "initial_item_type": request.POST.get("item_type", "BOTH"),
            })
            resp["HX-Retarget"] = "#item-modal-body"
            resp["HX-Reswap"]   = "innerHTML"
            return resp

        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


# ── Detail ────────────────────────────────────────────────────────────────────

class ItemDetailView(HistoryMixin, ERPBaseViewMixin, View):
    template_name = "items/item_detail.html"
    required_module = "sales"

    def get(self, request, pk):
        item = get_object_or_404(Item, pk=pk, organization=request.organization)
        return render(request, self.template_name, self.get_context(
            module="item",
            item=item,
            history_records=self.get_history(item) if request.membership.is_admin else [],
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Artículos"), "url": reverse("items:item_list")},
                {"label": item.name},
            ],
        ))


# ── Update ────────────────────────────────────────────────────────────────────

class ItemUpdateView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def get(self, request, pk):
        item = get_object_or_404(Item, pk=pk, organization=request.organization)
        form = ItemForm(instance=item, organization=request.organization)

        if request.htmx:
            return render(request, "items/partials/item_modal_form.html", {
                "form":              form,
                "action_url":        reverse("items:item_edit", args=[pk]),
                "submit_label":      _("Guardar"),
                "initial_item_type": item.item_type,
            })

        return render(request, "items/item_form.html", self.get_context(
            module="item",
            form=form, item=item, action="edit",
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Artículos"), "url": reverse("items:item_list")},
                {"label": item.name, "url": reverse("items:item_detail", args=[item.pk])},
                {"label": _("Editar")},
            ],
        ))

    def post(self, request, pk):
        item = get_object_or_404(Item, pk=pk, organization=request.organization)
        form = ItemForm(request.POST, instance=item, organization=request.organization)

        if form.is_valid():
            item = form.save()
            record_change_reason(item, form.cleaned_data.get("change_reason", ""))
            if request.htmx:
                return ItemListView.refresh_table(request, _("Artículo actualizado correctamente."))
            messages.success(request, _("Artículo actualizado correctamente."))
            return redirect("items:item_detail", pk=item.pk)

        if request.htmx:
            resp = render(request, "items/partials/item_modal_form.html", {
                "form":              form,
                "action_url":        reverse("items:item_edit", args=[pk]),
                "submit_label":      _("Guardar"),
                "initial_item_type": request.POST.get("item_type", item.item_type),
            })
            resp["HX-Retarget"] = "#item-modal-body"
            resp["HX-Reswap"]   = "innerHTML"
            return resp

        return render(request, "items/item_form.html", self.get_context(
            module="item",
            form=form, item=item, action="edit",
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Artículos"), "url": reverse("items:item_list")},
                {"label": item.name, "url": reverse("items:item_detail", args=[item.pk])},
                {"label": _("Editar")},
            ],
        ))


# ── Toggle active / inactive ─────────────────────────────────────────────────

class ItemToggleView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def post(self, request, pk):
        item = get_object_or_404(Item, pk=pk, organization=request.organization)
        item.is_active = not item.is_active
        item.save(update_fields=["is_active", "updated_at"])
        state = _("activado") if item.is_active else _("desactivado")
        msg   = _("Artículo %(state)s.") % {"state": state}

        if request.htmx:
            return ItemListView.refresh_table(request, msg)

        messages.success(request, msg)
        return redirect("items:item_detail", pk=item.pk)


# ── Delete ────────────────────────────────────────────────────────────────────

class ItemDeleteView(ERPBaseViewMixin, View):
    required_module = "sales"
    admin_required = True

    def post(self, request, pk):
        item = get_object_or_404(Item, pk=pk, organization=request.organization)
        name = item.name
        try:
            item.delete()
        except ValueError as exc:
            if request.htmx:
                resp = HttpResponse()
                resp["HX-Reswap"]  = "none"
                resp["HX-Trigger"] = json.dumps({"showSwal": {
                    "icon":  "error",
                    "title": str(_("No se puede eliminar")),
                    "text":  str(exc),
                }})
                return resp
            messages.error(request, str(exc))
            return redirect("items:item_list")
        if request.htmx:
            return ItemListView.refresh_table(request, _("Artículo «%(name)s» eliminado.") % {"name": name})
        messages.success(request, _("Artículo «%(name)s» eliminado.") % {"name": name})
        return redirect("items:item_list")


# ── HTMX item search (autocomplete for line-item rows) ────────────────────────

class ItemSearchView(ERPBaseViewMixin, View):
    """
    Returns matching items for the line-item autocomplete.

    GET params:
      q — search string (min 2 chars)
    """
    required_module = "sales"

    def get(self, request):
        q         = request.GET.get("q", "").strip()

        if len(q) < 2:
            return HttpResponse("")

        items = item_catalog_search(request.organization, q, sale_only=True, limit=10)
        return render(request, "items/partials/item_search_results.html", {"items": items})
