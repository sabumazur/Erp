import django_filters
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import PurchaseOrder, Supplier


class SupplierFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="search",
        label="",
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Nombre, RNC…"),
                "class": "form-control form-control-sm",
            }
        ),
    )

    def search(self, queryset, name, value):
        from apps.core.search import fts_search

        return fts_search(queryset, value, fts_fields=["name"], trgm_fields=["tax_id"])

    class Meta:
        model = Supplier
        fields = ["q"]


class PurchaseOrderFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=[
            (s.value, s.label)
            for s in PurchaseOrder.Status
        ],
        empty_label=_("Todos los estados"),
        label=_("Estado"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    supplier = django_filters.ModelChoiceFilter(
        queryset=Supplier.objects.none(),
        label=_("Proveedor"),
        empty_label=_("Todos los proveedores"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    issue_date_after = django_filters.DateFilter(
        field_name="issue_date",
        lookup_expr="gte",
        label=_("Desde"),
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control form-control-sm"}
        ),
    )
    issue_date_before = django_filters.DateFilter(
        field_name="issue_date",
        lookup_expr="lte",
        label=_("Hasta"),
        widget=forms.DateInput(
            attrs={"type": "date", "class": "form-control form-control-sm"}
        ),
    )

    class Meta:
        model = PurchaseOrder
        fields = ["status", "supplier", "issue_date_after", "issue_date_before"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.filters["supplier"].queryset = Supplier.objects.filter(
                organization=organization
            ).order_by("name")
