import django_filters
from django.utils.translation import gettext_lazy as _

from apps.core.widgets import TomSelect
from .models import Module


class ModuleFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search_filter", label=_("Buscar"))
    is_active = django_filters.ChoiceFilter(
        choices=[
            ("",      _("Activos e inactivos")),
            ("true",  _("Solo activos")),
            ("false", _("Solo inactivos")),
        ],
        method="active_filter",
        empty_label=None,
        label=_("Estado"),
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los estados")),
    )

    class Meta:
        model = Module
        fields = ["q", "is_active"]

    def search_filter(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(name__icontains=value) | queryset.filter(slug__icontains=value)

    def active_filter(self, queryset, name, value):
        if value == "true":
            return queryset.filter(is_active=True)
        if value == "false":
            return queryset.filter(is_active=False)
        return queryset
