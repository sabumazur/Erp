from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column

from .models import Supplier


class SupplierForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = Supplier
        fields = ["name", "rnc", "phone", "email", "status"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Nombre del proveedor")}),
            "rnc": forms.TextInput(attrs={"placeholder": _("Ej. 101234567")}),
            "phone": forms.TextInput(attrs={"placeholder": _("Ej. 809-555-1234")}),
            "email": forms.EmailInput(attrs={"placeholder": _("proveedor@ejemplo.com")}),
        }
        error_messages = {
            "name": {"required": _("El nombre es obligatorio.")},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False  # modal renders its own <form>
        self.helper.layout = Layout(
            "name",
            Row(
                Column("rnc", css_class="col-md-6"),
                Column("phone", css_class="col-md-6"),
            ),
            "email",
            "status",
        )
