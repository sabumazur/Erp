from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Field

from .models import Item


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            "code", "name", "description",
            "item_type", "unit",
            "unit_price", "cost_price", "itbis_rate",
            "is_active", "notes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes":       forms.Textarea(attrs={"rows": 2}),
            "unit_price":  forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "cost_price":  forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            # item_type drives Alpine reactive state; x-model keeps them in sync
            "item_type":   forms.Select(attrs={"x-model": "itemType"}),
            # code input gets a dynamic placeholder driven by Alpine
            "code":        forms.TextInput(attrs={
                ":placeholder": "codePlaceholder",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].help_text = ""
        self.fields["cost_price"].required = False
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
            "description",
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
        )
