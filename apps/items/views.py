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
from .filters import ItemFilter
from .forms import ItemForm
from .models import Item


def _org(request):
    return request.organization



# ── List + Create ─────────────────────────────────────────────────────────────

class ItemListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "items/item_list.html"
    required_module = "invoices"

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
    dt_search_placeholder = _("Nombre o código…")

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        """
        Called by action views (create / edit / toggle / delete) to refresh
        the datatable after a mutation.  Returns a partial response that HTMX
        swaps into #dt-results, with a toast notification.
        """
        qs = Item.objects.filter(organization=_org(request))
        f = ItemFilter(request.GET, queryset=qs)
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
        qs = Item.objects.filter(organization=_org(self.request))
        f  = ItemFilter(self.request.GET, queryset=qs)
        ctx.update(self.apply_datatable(f.qs))
        ctx["filter"] = f
        ctx["form"]   = ItemForm()
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
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = _org(request)
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

class ItemDetailView(ERPBaseViewMixin, View):
    template_name = "items/item_detail.html"
    required_module = "invoices"

    def get(self, request, pk):
        item = get_object_or_404(Item, pk=pk, organization=_org(request))
        return render(request, self.template_name, self.get_context(
            item=item,
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Artículos"), "url": reverse("items:item_list")},
                {"label": item.name},
            ],
        ))


# ── Update ────────────────────────────────────────────────────────────────────

class ItemUpdateView(ERPBaseViewMixin, View):
    required_module = "invoices"

    def get(self, request, pk):
        item = get_object_or_404(Item, pk=pk, organization=_org(request))
        form = ItemForm(instance=item)

        if request.htmx:
            return render(request, "items/partials/item_modal_form.html", {
                "form":              form,
                "action_url":        reverse("items:item_edit", args=[pk]),
                "submit_label":      _("Guardar"),
                "initial_item_type": item.item_type,
            })

        return render(request, "items/item_form.html", self.get_context(
            form=form, item=item, action="edit",
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Artículos"), "url": reverse("items:item_list")},
                {"label": item.name, "url": reverse("items:item_detail", args=[item.pk])},
                {"label": _("Editar")},
            ],
        ))

    def post(self, request, pk):
        item = get_object_or_404(Item, pk=pk, organization=_org(request))
        form = ItemForm(request.POST, instance=item)

        if form.is_valid():
            form.save()
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
    required_module = "invoices"

    def post(self, request, pk):
        item = get_object_or_404(Item, pk=pk, organization=_org(request))
        item.is_active = not item.is_active
        item.save(update_fields=["is_active", "updated_at"])
        state = _("activado") if item.is_active else _("desactivado")
        msg   = _(f"Artículo {state}.")

        if request.htmx:
            return ItemListView.refresh_table(request, msg)

        messages.success(request, msg)
        return redirect("items:item_detail", pk=item.pk)


# ── Delete ────────────────────────────────────────────────────────────────────

class ItemDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def post(self, request, pk):
        item = get_object_or_404(Item, pk=pk, organization=_org(request))
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
            return ItemListView.refresh_table(request, _(f"Artículo «{name}» eliminado."))
        messages.success(request, _(f"Artículo «{name}» eliminado."))
        return redirect("items:item_list")


# ── HTMX item search (autocomplete for line-item rows) ────────────────────────

class ItemSearchView(ERPBaseViewMixin, View):
    """
    Returns matching items for the line-item autocomplete.

    GET params:
      q     — search string (min 2 chars)
      type  — SALE | PURCHASE | BOTH | (empty = all)  default: SALE
    """
    required_module = "invoices"

    def get(self, request):
        q         = request.GET.get("q", "").strip()
        item_type = request.GET.get("type", "SALE")

        if len(q) < 2:
            return HttpResponse("")

        qs = Item.objects.filter(organization=_org(request), is_active=True)

        if item_type == "SALE":
            qs = qs.filter(item_type__in=[Item.ItemType.SALE, Item.ItemType.BOTH])
        elif item_type == "PURCHASE":
            qs = qs.filter(item_type__in=[Item.ItemType.PURCHASE, Item.ItemType.BOTH])

        qs = fts_search(qs, q, fts_fields=["name"], trgm_fields=["code"])[:10]

        return render(request, "items/partials/item_search_results.html", {"items": qs})
