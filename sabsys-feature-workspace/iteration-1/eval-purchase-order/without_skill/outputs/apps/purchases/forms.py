"""
apps/purchases/forms.py
"""
from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field, Submit

from .models import PurchaseOrder, Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            "name", "rnc", "email", "phone",
            "contact_name", "address", "notes", "is_active",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "address": forms.TextInput(),
        }

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column(Field("name"), css_class="col-md-8"),
                Column(Field("rnc"), css_class="col-md-4"),
            ),
            Row(
                Column(Field("email"), css_class="col-md-6"),
                Column(Field("phone"), css_class="col-md-6"),
            ),
            Row(
                Column(Field("contact_name"), css_class="col-md-6"),
                Column(Field("address"), css_class="col-md-6"),
            ),
            Field("notes"),
            Field("is_active"),
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization and not instance.pk:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "issue_date", "expected_date", "notes"]
        widgets = {
            "issue_date": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "expected_date": forms.DateInput(
                attrs={"type": "date"}, format="%Y-%m-%d"
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["supplier"].queryset = Supplier.objects.for_org(organization).filter(
                is_active=True
            )
        self.fields["expected_date"].required = False

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column(Field("supplier"), css_class="col-md-6"),
                Column(Field("issue_date"), css_class="col-md-3"),
                Column(Field("expected_date"), css_class="col-md-3"),
            ),
            Field("notes"),
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.organization and not instance.pk:
            instance.organization = self.organization
        if commit:
            instance.save()
        return instance
