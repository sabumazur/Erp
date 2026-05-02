import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import Item


class ItemFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="search_filter",
        label=_("Buscar"),
    )
    item_type = django_filters.ChoiceFilter(
        choices=[("", _("Todos los tipos"))] + list(Item.ItemType.choices),
        empty_label=None,
        label=_("Tipo"),
    )
    itbis_rate = django_filters.ChoiceFilter(
        choices=[("", _("Todos"))] + list(Item.ITBISRate.choices),
        empty_label=None,
        label=_("ITBIS"),
    )
    is_active = django_filters.ChoiceFilter(
        choices=[
            ("",      _("Activos e inactivos")),
            ("true",  _("Solo activos")),
            ("false", _("Solo inactivos")),
        ],
        method="active_filter",
        empty_label=None,
        label=_("Estado"),
    )

    class Meta:
        model = Item
        fields = ["q", "item_type", "itbis_rate", "is_active"]

    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(code__icontains=value)
            | Q(description__icontains=value)
        )

    def active_filter(self, queryset, name, value):
        if value == "true":
            return queryset.filter(is_active=True)
        if value == "false":
            return queryset.filter(is_active=False)
        return queryset
