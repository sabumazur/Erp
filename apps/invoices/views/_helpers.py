import json

from django.db.models import Count, Prefetch, Q

from ..models import Customer, CustomerDepartment


def _org(request):
    return request.organization


def _active_filter_count(request) -> int:
    skip = {"q", "page", "sort", "csrfmiddlewaretoken"}
    return sum(1 for k, v in request.GET.items() if k not in skip and v.strip())


def _customers_with_depts(organization):
    active_depts = CustomerDepartment.objects.filter(
        deleted_at__isnull=True, is_active=True
    ).only("id", "customer_id", "name").order_by("name")
    return (
        Customer.objects.filter(organization=organization)
        .prefetch_related(Prefetch("departments", queryset=active_depts, to_attr="active_depts"))
        .annotate(
            dept_count=Count(
                "departments", filter=Q(departments__deleted_at__isnull=True)
            )
        )
        .order_by("name")
    )


def _customer_defaults_json(request) -> str:
    """
    Serialize each active customer's billing defaults for the current org.
    Injected as window.CUSTOMER_DEFAULTS so the form can update ncf_type and
    payment_condition automatically when the user changes the customer select.
    """
    qs = Customer.objects.filter(
        organization=_org(request),
    ).select_related("payment_term")
    return json.dumps(
        {
            str(c.pk): {
                "ncf_type": c.default_ncf_type,
                "payment_condition": (
                    "CREDIT"
                    if c.payment_term and c.payment_term.days_due > 0
                    else "CASH"
                ),
                "days_due": (
                    c.payment_term.days_due
                    if c.payment_term and c.payment_term.days_due > 0
                    else 0
                ),
            }
            for c in qs
        },
        ensure_ascii=False,
    )


def _sale_items_json(request) -> str:
    """
    Active SALE/BOTH items for the current org serialized as JSON.
    Injected into form pages as window.ITEM_CATALOG.
    """
    from apps.items.models import Item

    qs = Item.objects.filter(
        organization=_org(request),
        is_active=True,
        item_type__in=[Item.ItemType.SALE, Item.ItemType.BOTH],
    ).order_by("name")
    return json.dumps(
        [
            {
                "pk": str(item.pk),
                "code": item.code,
                "name": item.name,
                "unit_price": str(item.unit_price),
                "itbis_rate": item.itbis_rate,
            }
            for item in qs
        ],
        ensure_ascii=False,
    )
