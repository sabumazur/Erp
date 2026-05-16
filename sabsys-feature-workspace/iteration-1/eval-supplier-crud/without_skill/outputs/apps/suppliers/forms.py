from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML

from .models import Supplier


class SupplierForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = Supplier
        fields = ["name", "rnc", "phone", "email", "status"]
        error_messages = {
            "name": {"required": _("El nombre es obligatorio.")},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rnc"].required = False
        self.fields["phone"].required = False
        self.fields["email"].required = False

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            "name",
            HTML('<hr class="my-3">'),
            Row(
                Column("rnc",   css_class="col-md-4"),
                Column("phone", css_class="col-md-4"),
                Column("email", css_class="col-md-4"),
            ),
            HTML('<hr class="my-3">'),
            "status",
        )
