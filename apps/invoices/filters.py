import django_filters
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Invoice, Customer, CustomerDepartment, NCFType, Payment, PaymentMethod, PaymentTerm


class InvoiceFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=[
            (s.value, s.label) for s in Invoice.Status
            if s in (
                Invoice.Status.DRAFT, Invoice.Status.CONFIRMED,
                Invoice.Status.SENT, Invoice.Status.PAID,
                Invoice.Status.OVERDUE, Invoice.Status.CANCELLED,
            )
        ],
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
        queryset=Customer.objects.none(),
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


class QuotationFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=[
            (s.value, s.label) for s in Invoice.Status
            if s in (
                Invoice.Status.DRAFT, Invoice.Status.CONFIRMED, Invoice.Status.SENT,
                Invoice.Status.ACCEPTED, Invoice.Status.REJECTED,
                Invoice.Status.EXPIRED, Invoice.Status.CONVERTED,
            )
        ],
        empty_label=_("Todos los estados"),
        label=_("Estado"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.none(),
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
    doc_number = django_filters.CharFilter(
        lookup_expr="icontains",
        label=_("Número"),
        widget=forms.TextInput(attrs={
            "placeholder": "COT-…",
            "class": "form-control form-control-sm",
        }),
    )

    class Meta:
        model = Invoice
        fields = ["status", "customer", "issue_date_after", "issue_date_before", "doc_number"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.filters["customer"].queryset = Customer.objects.filter(
                organization=organization
            )


class SaleOrderFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=[
            (s.value, s.label) for s in Invoice.Status
            if s in (
                Invoice.Status.DRAFT, Invoice.Status.CONFIRMED,
                Invoice.Status.DELIVERED, Invoice.Status.INVOICED,
                Invoice.Status.CANCELLED,
            )
        ],
        empty_label=_("Todos los estados"),
        label=_("Estado"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.none(),
        label=_("Cliente"),
        empty_label=_("Todos los clientes"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    delivery_date_after = django_filters.DateFilter(
        field_name="delivery_date",
        lookup_expr="gte",
        label=_("Entrega desde"),
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
    )
    delivery_date_before = django_filters.DateFilter(
        field_name="delivery_date",
        lookup_expr="lte",
        label=_("Entrega hasta"),
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
    )
    department = django_filters.ModelChoiceFilter(
        queryset=CustomerDepartment.objects.none(),
        label=_("Departamento"),
        empty_label=_("Todos los departamentos"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    doc_number = django_filters.CharFilter(
        lookup_expr="icontains",
        label=_("Número"),
        widget=forms.TextInput(attrs={
            "placeholder": "OV-…",
            "class": "form-control form-control-sm",
        }),
    )

    class Meta:
        model = Invoice
        fields = ["status", "customer", "department",
                  "delivery_date_after", "delivery_date_before", "doc_number"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.filters["customer"].queryset = Customer.objects.filter(
                organization=organization
            )
            self.filters["department"].queryset = CustomerDepartment.objects.filter(
                organization=organization,
                is_active=True,
                deleted_at__isnull=True,
            ).select_related("customer").order_by("customer__name", "name")


class PaymentFilter(django_filters.FilterSet):
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.none(),
        label=_("Cliente"),
        empty_label=_("Todos los clientes"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    date_after = django_filters.DateFilter(
        field_name="date",
        lookup_expr="gte",
        label=_("Desde"),
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
    )
    date_before = django_filters.DateFilter(
        field_name="date",
        lookup_expr="lte",
        label=_("Hasta"),
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control form-control-sm"}),
    )
    method = django_filters.ChoiceFilter(
        choices=[("", _("Todos los métodos"))] + PaymentMethod.choices,
        empty_label=None,
        label=_("Método"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    reference = django_filters.CharFilter(
        lookup_expr="icontains",
        label=_("Referencia"),
        widget=forms.TextInput(attrs={
            "placeholder": _("Cheque, transferencia…"),
            "class": "form-control form-control-sm",
        }),
    )

    class Meta:
        model = Payment
        fields = ["customer", "date_after", "date_before", "method", "reference"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.filters["customer"].queryset = Customer.objects.filter(
                organization=organization
            ).order_by("name")


class CustomerFilter(django_filters.FilterSet):
    default_ncf_type = django_filters.ChoiceFilter(
        choices=[("", _("Todos los tipos NCF"))] + NCFType.choices,
        empty_label=None,
        label=_("Tipo NCF"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )

    class Meta:
        model = Customer
        fields = ["default_ncf_type"]


class PaymentTermFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="search_filter",
        label=_("Buscar"),
        widget=forms.TextInput(attrs={
            "placeholder": _("Nombre…"),
            "class": "form-control form-control-sm",
        }),
    )

    class Meta:
        model = PaymentTerm
        fields = ["q"]

    def search_filter(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(name__icontains=value)
