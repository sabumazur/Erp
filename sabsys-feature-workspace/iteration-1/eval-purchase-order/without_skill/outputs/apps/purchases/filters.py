"""
apps/purchases/filters.py
"""
import django_filters
from django.utils.translation import gettext_lazy as _

from .models import PurchaseOrder, Supplier


class PurchaseOrderFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=PurchaseOrder.Status.choices,
        empty_label=_("Todos los estados"),
        label=_("Estado"),
    )
    supplier = django_filters.ModelChoiceFilter(
        queryset=Supplier.objects.none(),
        empty_label=_("Todos los proveedores"),
        label=_("Proveedor"),
    )

    class Meta:
        model = PurchaseOrder
        fields = ["status", "supplier"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.filters["supplier"].queryset = Supplier.objects.for_org(organization)


class SupplierFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter(
        label=_("Activo"),
        widget=django_filters.widgets.BooleanWidget(),
    )

    class Meta:
        model = Supplier
        fields = ["is_active"]
