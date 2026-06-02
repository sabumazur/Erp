from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Field

from .models import Module
from .widgets import ItbisSelect


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
            "is_active":   _("Módulo activo"),
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {
            "slug": _("Identificador único del módulo (ej. sales, inventory)."),
            "icon": _("Clase Bootstrap Icons (ej. bi-grid, bi-bag-fill)."),
            "is_active": _("Disponible para asignarse a equipos y mostrarse en navegación."),
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
            Field("is_active", template="components/forms/boolean_status_card.html"),
        )


class DocumentLineItemFormMixin(forms.ModelForm):
    """Shared widget configuration for document line item forms (sales and purchases)."""

    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "step": "1",
                "min": "1",
                "class": "form-control form-control-sm text-end",
                "x-model": "qty",
                "x-on:input": "recalc()",
            }
        ),
    )

    def get_item_types(self):
        raise NotImplementedError("Subclasses must return a list of ItemType values.")

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization

        # Lazy import avoids circular dependency (items imports from core)
        from django.db.models import Q
        from apps.items.models import Item as _Item

        self.fields["item"].widget = forms.HiddenInput()
        self.fields["item"].required = False
        if organization is not None:
            item_filter = Q(is_active=True, item_type__in=self.get_item_types())
            if self.instance.pk and self.instance.item_id:
                item_filter |= Q(pk=self.instance.item_id)
            self.fields["item"].queryset = _Item.objects.filter(
                item_filter, organization=organization
            )
        else:
            self.fields["item"].queryset = _Item.objects.none()

        self.fields["description"].widget = forms.TextInput(
            attrs={"class": "form-control form-control-sm"}
        )
        # Re-apply string attrs after Django's IntegerField.__init__ may have
        # overwritten min/step with numeric values from min_value.
        self.fields["quantity"].widget.attrs.update(
            {"step": "1", "min": "1"}
        )
        # Re-stringify step/min in case Django's IntegerField set them as ints,
        # then layer in the shared Alpine + CSS attrs.
        up_attrs = self.fields["unit_price"].widget.attrs
        if "min" in up_attrs:
            up_attrs["min"] = str(up_attrs["min"])
        if "step" in up_attrs:
            up_attrs["step"] = str(up_attrs["step"])
        up_attrs.update(
            {
                "class": "form-control form-control-sm text-end",
                "x-model": "price",
                "x-on:input": "recalc()",
            }
        )
        self.fields["itbis_rate"].widget.attrs.update(
            {
                "class": "form-select form-select-sm",
                "x-model": "rate",
                "x-on:change": "recalc()",
            }
        )

        self.initial.setdefault("quantity", 1)
        self.initial.setdefault("unit_price", 0)
        self.initial.setdefault("itbis_rate", "RATE_18")
