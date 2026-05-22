from django import template
from apps.accounts.permissions import can_access_module as _can_access_module

register = template.Library()


@register.simple_tag
def can_access_module(membership, module_slug):
    """
    Returns True if the given membership has access to the module.

    Usage in templates:
        {% can_access_module membership "invoices" as has_invoices %}
        {% if has_invoices %} ... {% endif %}
    """
    return _can_access_module(membership, module_slug)


@register.simple_tag(takes_context=True)
def nav_active(context, *url_names):
    """Returns 'active' if current request matches any of the given URL names."""
    request = context.get("request")
    if not request:
        return ""
    match = request.resolver_match
    if not match:
        return ""
    current = f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name
    return "active" if current in url_names else ""


@register.filter
def startswith(value, arg):
    """
    Returns True if the string value starts with arg.

    Usage:
        {% if request.path|startswith:"/invoices/" %} ... {% endif %}
    """
    return str(value).startswith(str(arg))
