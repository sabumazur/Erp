from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Field

from .models import Item


class ItemForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = Item
        fields = [
            "code", "name",
            "item_type", "unit",
            "unit_price", "cost_price", "itbis_rate",
            "is_active", "notes",
        ]
        widgets = {
            "notes":       forms.Textarea(attrs={"rows": 1}),
            "unit_price":  forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "cost_price":  forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            # item_type drives Alpine reactive state; x-model keeps them in sync
            "item_type":   forms.Select(attrs={"x-model": "itemType"}),
            # code input gets a dynamic placeholder driven by Alpine
            "code":        forms.TextInput(attrs={
                ":placeholder": "codePlaceholder",
            }),
        }
        error_messages = {
            "name":       {"required": _("El nombre es obligatorio.")},
            "item_type":  {"required": _("El tipo de artículo es obligatorio.")},
            "unit":       {"required": _("La unidad de medida es obligatoria.")},
            "unit_price": {"required": _("El precio de venta es obligatorio.")},
            "itbis_rate": {"required": _("La tasa ITBIS es obligatoria.")},
        }

    change_reason = forms.CharField(
        required=False,
        label=_("Motivo del cambio"),
        widget=forms.TextInput(attrs={
            "placeholder": _("Ej. Corrección de precio, ajuste de inventario…")
        }),
    )

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        super().__init__(*args, **kwargs)
        if self.organization is None and self.instance.pk:
            self.organization = self.instance.organization
        self.fields["cost_price"].required = False
        self.fields["item_type"].initial = Item.ItemType.SALE
        # Help text rendered via Alpine below the field instead of a static string
        self.fields["code"].help_text = ""

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            # ── Identity ──────────────────────────────────────────────────────
            Row(
                Column("code", css_class="col-md-3"),
                Column("name", css_class="col-md-9"),
            ),
            # Dynamic hint rendered by Alpine; hidden when item has a code already
            HTML(
                '<p class="text-muted small mt-n2 mb-3" x-show="!$el.closest(\'form\').querySelector(\'[name=code]\').value && autoCode">'
                '  <i class="bi bi-magic me-1"></i>'
                '  <span x-text="codeHint"></span>'
                '</p>'
            ),
            # ── Type, Unit, ITBIS ─────────────────────────────────────────────
            HTML('<hr class="my-3">'),
            Row(
                Column("item_type",  css_class="col-md-4"),
                Column("unit",       css_class="col-md-4"),
                Column("itbis_rate", css_class="col-md-4"),
            ),
            # ── Pricing ───────────────────────────────────────────────────────
            HTML('<hr class="my-3">'),
            Row(
                Column("unit_price", css_class="col-md-4"),
                Column("cost_price", css_class="col-md-4"),
            ),
            # ── Status & Notes ────────────────────────────────────────────────
            HTML('<hr class="my-3">'),
            Field("is_active"),
            "notes",
            "change_reason",
        )

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        if code and self.organization is not None:
            qs = Item.objects.filter(organization=self.organization, code=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    _("Ya existe un artículo con este código.")
                )
        return code
