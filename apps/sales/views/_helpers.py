import json

from django.db.models import Count, Prefetch, Q

from ..models import Customer, CustomerDepartment


# Escape characters that could break out of a <script> block.
# json.dumps() does NOT escape < > & by default, so a value like
# "</script><script>alert(1)" would close the tag and execute arbitrary JS.
_JSON_HTML_ESCAPES = str.maketrans({
    ord("<"): "\\u003C",
    ord(">"): "\\u003E",
    ord("&"): "\\u0026",
})


def _html_safe_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).translate(_JSON_HTML_ESCAPES)


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
        organization=request.organization,
    ).select_related("payment_term")
    return _html_safe_json(
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
        }
    )
