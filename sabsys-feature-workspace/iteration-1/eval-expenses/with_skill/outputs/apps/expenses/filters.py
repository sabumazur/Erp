import django_filters
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Expense, ExpenseCategory


class ExpenseCategoryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search", label="")

    def search(self, queryset, name, value):
        from apps.core.search import fts_search
        return fts_search(queryset, value, fts_fields=["name"])

    class Meta:
        model = ExpenseCategory
        fields = []


class ExpenseFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search", label="")
    status = django_filters.ChoiceFilter(
        choices=[("", _("Todos los estados"))] + Expense.Status.choices,
        label=_("Estado"),
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    category = django_filters.ModelChoiceFilter(
        queryset=ExpenseCategory.objects.none(),
        label=_("Categoría"),
        empty_label=_("Todas las categorías"),
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

    def search(self, queryset, name, value):
        from apps.core.search import fts_search
        return fts_search(queryset, value, fts_fields=["description"])

    class Meta:
        model = Expense
        fields = ["status", "category"]
