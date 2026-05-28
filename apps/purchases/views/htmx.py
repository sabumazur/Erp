from django.db.models import Q
from django.shortcuts import render
from django.views import View

from apps.accounts.views import ERPBaseViewMixin
from apps.items.models import item_catalog_search, Item
from ..forms import SupplierQuickCreateForm
from ..models import Supplier


class SupplierSearchView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        org = request.organization
        qs = Supplier.objects.filter(organization=org, is_active=True).order_by("name")
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(id_number__icontains=q)
            )
        suppliers = qs[:50]
        return render(
            request,
            "purchases/partials/supplier_picker_results.html",
            {"suppliers": suppliers},
        )


class SupplierQuickCreateView(ERPBaseViewMixin, View):
    required_module = "purchasing"

    def post(self, request):
        form = SupplierQuickCreateForm(request.POST, organization=request.organization)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.organization = request.organization
            supplier.save()
            return render(
                request,
                "purchases/partials/supplier_quick_create_row.html",
                {"supplier": supplier},
            )
        return render(
            request,
            "purchases/partials/supplier_quick_create_row.html",
            {"form": form, "errors": form.errors},
        )


class PurchaseItemSearchView(ERPBaseViewMixin, View):
    """Item search for purchase documents — returns PURCHASE+BOTH items only."""
    required_module = "purchasing"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        items = item_catalog_search(request.organization, q, sale_only=False, limit=50)
        return render(
            request,
            "purchases/partials/item_picker_results.html",
            {"items": items},
        )
