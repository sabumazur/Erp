from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field

from .models import Module


class ModuleForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = Module
        fields = ["slug", "name", "icon", "description", "is_active"]
        labels = {
            "slug":        _("Slug"),
            "name":        _("Nombre"),
            "icon":        _("Ícono"),
            "description": _("Descripción"),
            "is_active":   _("Activo"),
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {
            "slug": _("Identificador único del módulo (ej. invoices, inventory)."),
            "icon": _("Clase Bootstrap Icons (ej. bi-grid, bi-bag-fill)."),
        }
        error_messages = {
            "slug": {
                "required": _("El slug es obligatorio."),
                "unique":   _("Ya existe un módulo con este slug."),
            },
            "name": {"required": _("El nombre es obligatorio.")},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("slug", css_class="col-md-4"),
                Column("name", css_class="col-md-8"),
            ),
            Row(
                Column("icon", css_class="col-md-4"),
            ),
            "description",
            Field("is_active"),
        )
