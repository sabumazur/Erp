import django_filters
from django import forms
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.widgets import TomSelect
from .models import SalesDocument, Customer, CustomerDepartment, NCFType, Payment, PaymentMethod, PaymentTerm


class InvoiceFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=[
            (s.value, s.label) for s in SalesDocument.Status
            if s in (
                SalesDocument.Status.DRAFT, SalesDocument.Status.CONFIRMED,
                SalesDocument.Status.SENT, SalesDocument.Status.PAID,
                SalesDocument.Status.OVERDUE, SalesDocument.Status.CANCELLED,
            )
        ],
        empty_label=_("Todos los estados"),
        label=_("Estado"),
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los estados")),
    )
    ncf_type = django_filters.ChoiceFilter(
        choices=[("", _("Todos los tipos"))] + NCFType.choices,
        label=_("Tipo NCF"),
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los tipos")),
        empty_label=None,
    )
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.none(),
        label=_("Cliente"),
        empty_label=_("Todos los clientes"),
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los clientes")),
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
        model = SalesDocument
        fields = ["status", "ncf_type", "customer", "issue_date_after", "issue_date_before", "encf"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.filters["customer"].queryset = Customer.objects.filter(
                organization=organization
            )

    def clean(self):
        data = super().clean()
        after = data.get("issue_date_after")
        before = data.get("issue_date_before")
        if after and before and after > before:
            raise forms.ValidationError(
                _("La fecha inicial no puede ser mayor que la fecha final.")
            )
        return data


class QuotationFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=[
            (s.value, s.label) for s in SalesDocument.Status
            if s in (
                SalesDocument.Status.DRAFT, SalesDocument.Status.CONFIRMED, SalesDocument.Status.SENT,
                SalesDocument.Status.ACCEPTED, SalesDocument.Status.REJECTED,
                SalesDocument.Status.EXPIRED, SalesDocument.Status.CONVERTED,
            )
        ],
        empty_label=_("Todos los estados"),
        label=_("Estado"),
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los estados")),
    )
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.none(),
        label=_("Cliente"),
        empty_label=_("Todos los clientes"),
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los clientes")),
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
        method="search_by_ref",
        label=_("Número / cliente"),
        widget=forms.TextInput(attrs={
            "placeholder": "COT-… o cliente",
            "class": "form-control form-control-sm",
        }),
    )

    class Meta:
        model = SalesDocument
        fields = ["status", "customer", "issue_date_after", "issue_date_before", "doc_number"]

    def search_by_ref(self, queryset, name, value):
        """
        Fix Q5: use TrigramSimilarity on doc_number (backed by GIN trgm index)
        combined with icontains on customer__name for FK traversal.
        Falls back to icontains for very short terms (< 3 chars).
        """
        if not value:
            return queryset
        if len(value) < 3:
            return queryset.filter(
                Q(doc_number__icontains=value) | Q(customer__name__icontains=value)
            )
        return (
            queryset
            .annotate(sim_doc=TrigramSimilarity("doc_number", value))
            .filter(Q(sim_doc__gte=0.1) | Q(customer__name__icontains=value))
            .order_by("-sim_doc")
        )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.filters["customer"].queryset = Customer.objects.filter(
                organization=organization
            )

    def clean(self):
        data = super().clean()
        after = data.get("issue_date_after")
        before = data.get("issue_date_before")
        if after and before and after > before:
            raise forms.ValidationError(
                _("La fecha inicial no puede ser mayor que la fecha final.")
            )
        return data


class SaleOrderFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=[
            (s.value, s.label) for s in SalesDocument.Status
            if s in (
                SalesDocument.Status.DRAFT, SalesDocument.Status.INVOICED,
                SalesDocument.Status.CANCELLED,
            )
        ],
        empty_label=_("Todos los estados"),
        label=_("Estado"),
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los estados")),
    )
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.none(),
        label=_("Cliente"),
        empty_label=_("Todos los clientes"),
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los clientes")),
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
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los departamentos")),
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
        model = SalesDocument
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

    def clean(self):
        data = super().clean()
        after = data.get("delivery_date_after")
        before = data.get("delivery_date_before")
        if after and before and after > before:
            raise forms.ValidationError(
                _("La fecha inicial no puede ser mayor que la fecha final.")
            )
        return data


class PaymentFilter(django_filters.FilterSet):
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.none(),
        label=_("Cliente"),
        empty_label=_("Todos los clientes"),
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los clientes")),
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
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los métodos")),
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

    def clean(self):
        data = super().clean()
        after = data.get("date_after")
        before = data.get("date_before")
        if after and before and after > before:
            raise forms.ValidationError(
                _("La fecha inicial no puede ser mayor que la fecha final.")
            )
        return data


class CustomerFilter(django_filters.FilterSet):
    default_ncf_type = django_filters.ChoiceFilter(
        choices=[("", _("Todos los tipos NCF"))] + NCFType.choices,
        empty_label=None,
        label=_("Tipo NCF"),
        widget=TomSelect(attrs={"class": "form-select form-select-sm"}, placeholder=_("Todos los tipos NCF")),
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
