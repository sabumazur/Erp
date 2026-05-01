import django_filters
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Invoice, Customer, NCFType


class InvoiceFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=Invoice.Status.choices,
        empty_label=_("Todos los estados"),
        label=_("Estado"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    ncf_type = django_filters.ChoiceFilter(
        choices=[("", _("Todos los tipos"))] + NCFType.choices,
        label=_("Tipo NCF"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
        empty_label=None,
    )
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.none(),   # overridden in __init__
        label=_("Cliente"),
        empty_label=_("Todos los clientes"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    issue_date_after = django_filters.DateFilter(
        field_name="issue_date",
        lookup_expr="gte",
        label=_("Desde"),
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
    )
    issue_date_before = django_filters.DateFilter(
        field_name="issue_date",
        lookup_expr="lte",
        label=_("Hasta"),
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
    )
    encf = django_filters.CharFilter(
        lookup_expr="icontains",
        label=_("e-NCF"),
        widget=forms.TextInput(attrs={
            "placeholder": "E31…",
            "class": "form-control form-control-sm",
        }),
    )

    class Meta:
        model = Invoice
        fields = ["status", "ncf_type", "customer", "issue_date_after", "issue_date_before", "encf"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.filters["customer"].queryset = Customer.objects.filter(
                organization=organization
            )
