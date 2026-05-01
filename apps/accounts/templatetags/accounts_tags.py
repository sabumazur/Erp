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


@register.filter
def startswith(value, arg):
    """
    Returns True if the string value starts with arg.

    Usage:
        {% if request.path|startswith:"/invoices/" %} ... {% endif %}
    """
    return str(value).startswith(str(arg))
