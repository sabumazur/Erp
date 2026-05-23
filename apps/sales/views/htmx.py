"""
Dedicated HTMX/JSON endpoints that replace the full page-level data dumps
(_customer_defaults_json, _sale_items_json).

Usage — swap these into your templates instead of injecting window.CUSTOMER_DEFAULTS
and window.ITEM_CATALOG on page load:

  Customer defaults (triggered by customer <select> change):
    hx-get="{% url 'invoices:customer_defaults' %}?customer_id=<id>"

  Item search (triggered by item search input):
    hx-get="{% url 'invoices:item_search' %}?q=<query>"
"""
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render as _render
from django.views import View

from apps.accounts.views import ERPBaseViewMixin
from ..forms import CustomerQuickCreateForm, ItemQuickCreateForm
from ..models import Customer


class CustomerDefaultsView(ERPBaseViewMixin, View):
    """
    Returns billing defaults for a single customer as JSON.
    Replaces the full window.CUSTOMER_DEFAULTS dump on form pages.
    """
    required_module = "sales"

    def get(self, request):
        customer_id = request.GET.get("customer_id", "").strip()
        if not customer_id:
            return JsonResponse({})
        try:
            c = Customer.objects.select_related("payment_term").get(
                pk=customer_id, organization=request.organization
            )
        except Customer.DoesNotExist:
            return JsonResponse({})

        return JsonResponse({
            "ncf_type": c.default_ncf_type,
            "payment_condition": (
                "CREDIT" if c.payment_term and c.payment_term.days_due > 0 else "CASH"
            ),
            "days_due": (
                c.payment_term.days_due
                if c.payment_term and c.payment_term.days_due > 0
                else 0
            ),
        })


class ItemSearchView(ERPBaseViewMixin, View):
    """
    HTMX endpoint: returns item_picker_results.html partial for the item picker modal.
    GET ?q=<search> — scoped to org, top 50 SALE/BOTH active items.
    """
    required_module = "sales"

    def get(self, request):
        from apps.items.models import Item
        from django.shortcuts import render

        q = request.GET.get("q", "").strip()
        org = request.organization

        qs = Item.objects.filter(
            organization=org,
            is_active=True,
            item_type__in=[Item.ItemType.SALE, Item.ItemType.BOTH],
        ).order_by("name")

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

        items = qs[:50]
        return render(request, "sales/partials/item_picker_results.html", {"items": items})


class CustomerSearchView(ERPBaseViewMixin, View):
    """Returns customer rows for the picker modal via HTMX."""
    required_module = "sales"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        org = request.organization
        qs = Customer.objects.filter(organization=org).order_by("name")
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(rnc_cedula__icontains=q)
            )
        customers = qs[:25]
        return _render(request, "sales/partials/customer_picker_results.html",
                       {"customers": customers})


class CustomerQuickCreateView(ERPBaseViewMixin, View):
    """Creates a customer from the picker modal quick-create panel."""
    required_module = "sales"
    admin_required = True

    def post(self, request):
        org = request.organization
        form = CustomerQuickCreateForm(request.POST, organization=org)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.organization = org
            customer.save()
            return JsonResponse({
                "pk": str(customer.pk),
                "name": customer.name,
                "rnc_cedula": customer.rnc_cedula,
                "default_ncf_type": customer.default_ncf_type,
            })
        return JsonResponse(
            {"errors": {field: [str(e) for e in errs]
                        for field, errs in form.errors.items()}},
            status=422,
        )


class ItemQuickCreateView(ERPBaseViewMixin, View):
    """Creates a catalog item from the item picker modal quick-create panel."""
    required_module = "sales"
    admin_required = True

    def post(self, request):
        from apps.items.models import Item
        org = request.organization
        form = ItemQuickCreateForm(request.POST, organization=org)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = org
            item.item_type = Item.ItemType.SALE
            item.save()
            return JsonResponse({
                "pk": str(item.pk),
                "name": item.name,
                "code": item.code,
                "unit_price": str(item.unit_price),
                "itbis_rate": item.itbis_rate,
                "unit": item.unit,
            })
        return JsonResponse(
            {"errors": {field: [str(e) for e in errs]
                        for field, errs in form.errors.items()}},
            status=422,
        )
