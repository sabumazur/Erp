"""
Dedicated HTMX/JSON endpoints that replace the full page-level data dumps
(_customer_defaults_json, _sale_items_json).

Usage — swap these into your templates instead of injecting window.CUSTOMER_DEFAULTS
and window.ITEM_CATALOG on page load:

  Customer defaults (triggered by customer <select> change):
    hx-get="{% url 'invoices:customer_defaults' %}?customer_id=<id>"

  Item catalog search (triggered by item search input):
    hx-get="{% url 'invoices:item_catalog' %}?q=<query>"
"""
import json

from django.core.cache import cache
from django.http import JsonResponse
from django.views import View

from apps.accounts.views import ERPBaseViewMixin
from ..models import Customer
from ._helpers import _org


class CustomerDefaultsView(ERPBaseViewMixin, View):
    """
    Returns billing defaults for a single customer as JSON.
    Replaces the full window.CUSTOMER_DEFAULTS dump on form pages.
    """
    required_module = "invoices"

    def get(self, request):
        customer_id = request.GET.get("customer_id", "").strip()
        if not customer_id:
            return JsonResponse({})
        try:
            c = Customer.objects.select_related("payment_term").get(
                pk=customer_id, organization=_org(request)
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


class ItemCatalogView(ERPBaseViewMixin, View):
    """
    Returns active SALE/BOTH items for the current org, optionally filtered by
    query string ?q=<search>. Returns JSON array.
    Replaces the full window.ITEM_CATALOG dump on form pages.
    """
    required_module = "invoices"

    def get(self, request):
        from apps.items.models import Item
        from django.db.models import Q

        q = request.GET.get("q", "").strip()
        org = _org(request)

        # Cache the full unfiltered catalog per org — the most common hit is
        # the form page loading the complete list on startup (q="").
        # Search queries are not cached to avoid a key-per-term explosion.
        cache_key = f"item_catalog:{org.pk}"
        if not q:
            cached = cache.get(cache_key)
            if cached is not None:
                return JsonResponse(cached, safe=False)

        qs = Item.objects.filter(
            organization=org,
            is_active=True,
            item_type__in=[Item.ItemType.SALE, Item.ItemType.BOTH],
        ).order_by("name")

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))

        qs = qs[:50]

        result = [
            {
                "pk": str(item.pk),
                "code": item.code,
                "name": item.name,
                "unit": item.get_unit_display(),
                "unit_price": str(item.unit_price),
                "itbis_rate": item.itbis_rate,
            }
            for item in qs
        ]

        if not q:
            cache.set(cache_key, result, timeout=300)

        return JsonResponse(result, safe=False)
