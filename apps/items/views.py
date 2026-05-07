import json

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, UpdateView

from apps.accounts.views import ERPBaseViewMixin
from .filters import ItemFilter
from .forms import ItemForm
from .models import Item


def _org(request):
    return request.organization


def _active_filter_count(request) -> int:
    skip = {"q", "page", "csrfmiddlewaretoken"}
    return sum(1 for k, v in request.GET.items() if k not in skip and v.strip())


def _item_table_response(request, msg, msg_type="success"):
    """Return the full item table partial with an HX-Trigger toast."""
    items = Item.objects.filter(organization=_org(request)).order_by("name")
    resp = render(request, "items/partials/item_table.html", {"items": items})
    resp["HX-Trigger"] = json.dumps({
        "showToast": {"message": str(msg), "type": msg_type}
    })
    return resp


# ── List + Create ─────────────────────────────────────────────────────────────

class ItemListView(ERPBaseViewMixin, TemplateView):
    template_name = "items/item_list.html"
    required_module = "invoices"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Item.objects.filter(organization=_org(self.request))
        f  = ItemFilter(self.request.GET, queryset=qs)
        ctx["filter"]               = f
        ctx["items"]                = f.qs
        ctx["active_filter_count"]  = _active_filter_count(self.request)
        ctx["form"]                 = ItemForm()
        ctx["create_url"]           = reverse("items:item_list")
        ctx["submit_label"]         = _("Crear")
        ctx["breadcrumbs"]          = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Artículos")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "items/partials/item_table.html", ctx)
        return self.render_to_response(ctx)

    def post(self, request):
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = _org(request)
            item.save()
            if request.htmx:
                return _item_table_response(request, _("Artículo creado correctamente."))
            messages.success(request, _("Artículo creado correctamente."))
            return redirect("items:item_list")

        # Validation failed — return form with errors back into the modal
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

        # Non-HTMX fallback — full page
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
                return _item_table_response(request, _("Artículo actualizado correctamente."))
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
            return _item_table_response(request, msg)

        messages.success(request, msg)
        return redirect("items:item_detail", pk=item.pk)


# ── Delete ────────────────────────────────────────────────────────────────────

class ItemDeleteView(ERPBaseViewMixin, View):
    required_module = "invoices"
    admin_required = True

    def post(self, request, pk):
        from apps.invoices.models import InvoiceItem
        item = get_object_or_404(Item, pk=pk, organization=_org(request))
        if InvoiceItem.objects.filter(item=item).exists():
            if request.htmx:
                resp = HttpResponse()
                resp["HX-Reswap"] = "none"
                resp["HX-Trigger"] = json.dumps({"showSwal": {
                    "icon": "error",
                    "title": str(_("No se puede eliminar")),
                    "text": str(_("Este artículo está siendo usado en uno o más documentos y no puede eliminarse.")),
                }})
                return resp
            messages.error(request, _("Este artículo está siendo usado en documentos y no puede eliminarse."))
            return redirect("items:item_list")
        name = item.name
        item.delete()
        if request.htmx:
            return _item_table_response(request, _(f"Artículo «{name}» eliminado."))
        messages.success(request, _(f"Artículo «{name}» eliminado."))
        return redirect("items:item_list")


# ── HTMX item search (autocomplete for line-item rows) ────────────────────────

class ItemSearchView(ERPBaseViewMixin, View):
    """
    Returns a list of matching items for the line-item autocomplete.

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

        qs = qs.filter(
            Q(name__icontains=q) | Q(code__icontains=q)
        )[:10]

        return render(request, "items/partials/item_search_results.html", {"items": qs})
