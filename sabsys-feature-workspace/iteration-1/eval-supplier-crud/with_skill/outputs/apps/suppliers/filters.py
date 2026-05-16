import django_filters
from django.utils.translation import gettext_lazy as _
from .models import Supplier


class SupplierFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search", label="")
    status = django_filters.ChoiceFilter(
        choices=Supplier.Status.choices,
        label=_("Estado"),
        empty_label=_("Todos los estados"),
    )

    def search(self, queryset, name, value):
        from apps.core.search import fts_search
        return fts_search(queryset, value, fts_fields=["name"], trgm_fields=["rnc", "email"])

    class Meta:
        model = Supplier
        fields = ["status"]
