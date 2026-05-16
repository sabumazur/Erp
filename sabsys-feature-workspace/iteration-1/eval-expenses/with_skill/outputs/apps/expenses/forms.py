from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper

from .models import Expense, ExpenseCategory


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["category", "amount", "date", "description", "status", "approved_by"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None:
            self.fields["category"].queryset = ExpenseCategory.objects.for_org(organization)
        self.helper = FormHelper()
        self.helper.form_tag = False
