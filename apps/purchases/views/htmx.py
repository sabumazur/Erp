from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from apps.accounts.views import ERPBaseViewMixin
from apps.core.search import fts_search
from apps.items.models import Item
from ..forms import PurchaseItemQuickCreateForm, SupplierQuickCreateForm
from ..models import Supplier


class SupplierSearchView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        org = request.organization
        qs = Supplier.objects.filter(organization=org, is_active=True).order_by("name")
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(rnc_cedula__icontains=q)
            )
        suppliers = qs[:50]
        return render(
            request,
            "purchases/partials/supplier_picker_results.html",
            {"suppliers": suppliers},
        )


class SupplierQuickCreateView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def post(self, request):
        form = SupplierQuickCreateForm(request.POST, organization=request.organization)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.organization = request.organization
            supplier.save()
            return JsonResponse({
                "pk": str(supplier.pk),
                "name": supplier.name,
                "rnc_cedula": supplier.rnc_cedula,
            })
        return JsonResponse(
            {"errors": {field: [str(e) for e in errs] for field, errs in form.errors.items()}},
            status=422,
        )


class PurchaseItemSearchView(ERPBaseViewMixin, View):
    """Item search for purchase documents — returns PURCHASE+BOTH items only."""
    required_module = "purchasing"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        items = Item.objects.for_org(request.organization).filter(
            is_active=True,
            item_type__in=[Item.ItemType.PURCHASE, Item.ItemType.BOTH],
        )
        if q:
            items = fts_search(items, q, fts_fields=["name"], trgm_fields=["code"])
        else:
            items = items.order_by("name")
        return render(
            request,
            "purchases/partials/item_picker_results.html",
            {"items": items[:50]},
        )


class PurchaseItemQuickCreateView(ERPBaseViewMixin, View):
    required_module = "purchasing"
    admin_required = True

    def post(self, request):
        form = PurchaseItemQuickCreateForm(request.POST, organization=request.organization)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = request.organization
            item.item_type = Item.ItemType.PURCHASE
            item.save()
            price = item.cost_price or 0
            return JsonResponse({
                "pk": str(item.pk),
                "name": item.name,
                "code": item.code,
                "unit_price": str(price),
                "itbis_rate": item.itbis_rate,
                "unit": item.unit,
            })
        return JsonResponse(
            {"errors": {field: [str(e) for e in errs] for field, errs in form.errors.items()}},
            status=422,
        )
