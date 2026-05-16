import django_filters
from django.utils.translation import gettext_lazy as _

from apps.core.search import fts_search

from .models import Supplier


class SupplierFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="search_filter",
        label=_("Buscar"),
    )
    status = django_filters.ChoiceFilter(
        choices=[("", _("Todos los estados"))] + list(Supplier.Status.choices),
        empty_label=None,
        label=_("Estado"),
    )

    class Meta:
        model = Supplier
        fields = ["q", "status"]

    def search_filter(self, queryset, name, value):
        return fts_search(
            queryset,
            value,
            fts_fields=["name"],
            trgm_fields=["rnc"],
        )
