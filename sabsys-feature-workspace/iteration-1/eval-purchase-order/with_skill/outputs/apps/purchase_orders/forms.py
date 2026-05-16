from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper

from .models import PurchaseOrder, Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            "name",
            "tax_id",
            "email",
            "phone",
            "contact_name",
            "address",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "address": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = [
            "supplier",
            "issue_date",
            "expected_date",
            "notes",
        ]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "expected_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        if organization is not None:
            self.fields["supplier"].queryset = Supplier.objects.for_org(organization)
        self.fields["supplier"].label = _("Proveedor")
        self.fields["issue_date"].label = _("Fecha de emisión")
        self.fields["expected_date"].label = _("Fecha esperada de entrega")
        self.fields["notes"].label = _("Notas")
