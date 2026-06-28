import re
from decimal import Decimal

from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Field

from apps.core.layout import optional_fields, optional_field_wraps
from apps.core.widgets import TomSelect, ItbisSelect, DateInput, AutosizeTextarea
from apps.core.forms import DocumentLineItemFormMixin
from apps.items.models import Item as _Item
from apps.sales.models import PaymentTerm
from .models import (
    Supplier,
    PurchaseDocument,
    PurchaseDocumentItem,
    SupplierPayment,
)

_PHONE_RE = re.compile(r"^\+?[\d\s.\-()+]{7,20}$")


# ── SupplierForm ──────────────────────────────────────────────────────────────


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            "name",
            "id_type",
            "rnc_cedula",
            "email",
            "phone",
            "contact_name",
            "address",
            "city",
            "payment_term",
            "credit_limit",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
            "id_type": TomSelect(placeholder="Tipo de ID…"),
            "payment_term": TomSelect(placeholder="Condición de pago…"),
        }

    change_reason = forms.CharField(
        required=False,
        label=_("Motivo del cambio"),
        widget=forms.TextInput(
            attrs={"placeholder": _("Corrección de datos, actualización…")}
        ),
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        if organization:
            self.fields["payment_term"].queryset = PaymentTerm.objects.filter(
                Q(organization__isnull=True) | Q(organization=organization)
            ).order_by("days_due", "name")
        self.fields["rnc_cedula"].widget.attrs.update(
            {
                "placeholder": _("9 dígitos (RNC) · 11 (Cédula)"),
                "hx-get": reverse_lazy("sales:rnc_lookup"),
                "hx-trigger": "blur changed",
                "hx-target": "#rnc-lookup-result",
                "hx-include": "closest form",
                "hx-indicator": "#rnc-lookup-spinner",
            }
        )
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            HTML(
                f'<p class="text-muted small text-uppercase mb-2 mt-1">{_("General")}</p>'
            ),
            Row(
                Column("id_type", css_class="col-md-5"),
                Column("rnc_cedula", css_class="col-md-7"),
            ),
            HTML(
                '<div class="d-flex align-items-center gap-2 mb-2" style="min-height:1.6rem">'
                '<span id="rnc-lookup-spinner" class="htmx-indicator spinner-border spinner-border-sm text-secondary" role="status"></span>'
                '<div id="rnc-lookup-result"></div>'
                "</div>"
            ),
            "name",
            HTML(
                f'<hr class="my-3"><p class="text-muted small text-uppercase mb-2">{_("Dirección")}</p>'
            ),
            "address",
            Row(
                Column("city", css_class="col-md-6"),
            ),
            HTML(
                f'<hr class="my-3"><p class="text-muted small text-uppercase mb-2">{_("Contacto")}</p>'
            ),
            Row(
                Column("email", css_class="col-md-6"),
                Column("phone", css_class="col-md-6"),
            ),
            "contact_name",
            HTML(
                f'<hr class="my-3"><p class="text-muted small text-uppercase mb-2">{_("Compras")}</p>'
            ),
            "payment_term",
            "credit_limit",
            "notes",
            "change_reason",
        )

    def clean(self):
        cleaned_data = super().clean()
        id_type = cleaned_data.get("id_type")
        rnc_cedula = (cleaned_data.get("rnc_cedula") or "").strip()

        if rnc_cedula:
            normalized = re.sub(r"[\s\-]", "", rnc_cedula)

            if id_type == Supplier.IdType.RNC:
                if not re.fullmatch(r"\d{9}", normalized):
                    self.add_error(
                        "rnc_cedula",
                        _("El RNC debe tener exactamente 9 dígitos numéricos."),
                    )
                else:
                    cleaned_data["rnc_cedula"] = normalized

            elif id_type == Supplier.IdType.CEDULA:
                if not re.fullmatch(r"\d{11}", normalized):
                    self.add_error(
                        "rnc_cedula",
                        _("La Cédula debe tener exactamente 11 dígitos numéricos."),
                    )
                else:
                    cleaned_data["rnc_cedula"] = normalized

            normalized = cleaned_data.get("rnc_cedula") or ""
            if self._organization and normalized and "rnc_cedula" not in self.errors:
                qs = Supplier.objects.filter(
                    organization=self._organization,
                    rnc_cedula=normalized,
                    deleted_at__isnull=True,
                )
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                existing = qs.first()
                if existing:
                    self._id_duplicate_msg = str(
                        _("Este RNC/cédula ya está asignado al proveedor «%(name)s».")
                        % {"name": existing.name}
                    )
                    self.add_error("rnc_cedula", self._id_duplicate_msg)

        return cleaned_data

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if phone and not _PHONE_RE.match(phone):
            raise forms.ValidationError(
                _("Número de teléfono inválido (7–20 dígitos).")
            )
        return phone


# ── SupplierQuickCreateForm ───────────────────────────────────────────────────


class SupplierQuickCreateForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "id_type", "rnc_cedula"]
        widgets = {
            "id_type": TomSelect(placeholder="Tipo de ID…"),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        self.fields["name"].widget.attrs["autofocus"] = True
        self.fields["rnc_cedula"].widget.attrs["placeholder"] = _(
            "9 dígitos (RNC) · 11 (Cédula)"
        )

    def clean(self):
        cleaned_data = super().clean()
        id_type = cleaned_data.get("id_type")
        rnc_cedula = (cleaned_data.get("rnc_cedula") or "").strip()

        if rnc_cedula:
            normalized = re.sub(r"[\s\-]", "", rnc_cedula)

            if id_type == Supplier.IdType.RNC:
                if not re.fullmatch(r"\d{9}", normalized):
                    self.add_error(
                        "rnc_cedula", _("El RNC debe tener exactamente 9 dígitos.")
                    )
                else:
                    cleaned_data["rnc_cedula"] = normalized

            elif id_type == Supplier.IdType.CEDULA:
                if not re.fullmatch(r"\d{11}", normalized):
                    self.add_error(
                        "rnc_cedula", _("La Cédula debe tener exactamente 11 dígitos.")
                    )
                else:
                    cleaned_data["rnc_cedula"] = normalized

        return cleaned_data


class PurchaseItemQuickCreateForm(forms.ModelForm):
    """Minimal purchase item creation form used by the purchase document picker."""

    unit_price = forms.IntegerField(
        min_value=1,
        label=_("precio de costo"),
        widget=forms.NumberInput(attrs={"step": "1", "min": "1"}),
    )

    class Meta:
        model = _Item
        fields = ["name", "unit", "unit_price", "itbis_rate"]
        widgets = {
            "unit": TomSelect(placeholder="Unidad…"),
            "itbis_rate": ItbisSelect(),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        self.fields["unit_price"].widget.attrs["placeholder"] = "0.00"

    def save(self, commit=True):
        item = super().save(commit=False)
        item.cost_price = self.cleaned_data["unit_price"]
        item.unit_price = Decimal("0.00")
        if commit:
            item.save()
            self.save_m2m()
        return item


# ── PurchaseOrderForm ─────────────────────────────────────────────────────────


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseDocument
        fields = [
            "supplier",
            "issue_date",
            "expected_date",
            "notes",
        ]
        widgets = {
            "issue_date": DateInput(),
            "expected_date": DateInput(),
            "notes": AutosizeTextarea(
                attrs={
                    "placeholder": _("Instrucciones, términos de entrega o referencias internas…")
                }
            ),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        if organization:
            self.fields["supplier"].queryset = Supplier.objects.filter(
                organization=organization, is_active=True
            ).order_by("name")
        self.fields["supplier"].widget = forms.HiddenInput(attrs={"id": "id_supplier"})
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column(
                    HTML(
                        '<label class="form-label requiredField">'
                        + str(_("Proveedor"))
                        + '<span class="asteriskField">*</span></label>'
                        '<div class="input-group mb-1">'
                        '<span class="form-control supplier-display-text" id="supplier-display-text"'
                        ' role="button" tabindex="0"'
                        ' style="cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"'
                        ' onclick="openSupplierPicker()"'
                        ' onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();openSupplierPicker();}">'
                        "{% if form.instance.supplier %}{{ form.instance.supplier.name }}{% else %}"
                        '<span class=\\"text-muted fst-italic\\">Sin proveedor seleccionado</span>'
                        "{% endif %}"
                        "</span>"
                        '<button type="button" class="btn btn-outline-secondary" onclick="openSupplierPicker()">'
                        '<i class="bi bi-search"></i>'
                        "</button>"
                        "</div>"
                        "{% if form.supplier.errors %}"
                        '<div class="text-danger small">{{ form.supplier.errors.0 }}</div>'
                        "{% endif %}"
                    ),
                    Field("supplier"),
                    css_class="col-md-6",
                ),
                Column("issue_date", css_class="col-md-3"),
                Column("expected_date", css_class="col-md-3"),
            ),
            optional_field_wraps(("notes", _("Añadir notas"))),
        )


# ── SupplierInvoiceForm ───────────────────────────────────────────────────────


class SupplierInvoiceForm(forms.ModelForm):
    class Meta:
        model = PurchaseDocument
        fields = [
            "supplier",
            "supplier_ncf",
            "issue_date",
            "due_date",
            "currency",
            "exchange_rate",
            "notes",
        ]
        widgets = {
            "issue_date": DateInput(),
            "due_date": DateInput(),
            "notes": AutosizeTextarea(attrs={"placeholder": _("Instrucciones o referencias internas…")}),
            "currency": TomSelect(placeholder="Moneda…"),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        if organization:
            self.fields["supplier"].queryset = Supplier.objects.filter(
                organization=organization, is_active=True
            ).order_by("name")
        self.fields["supplier"].widget = forms.HiddenInput(attrs={"id": "id_supplier"})
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column(
                    HTML(
                        '<label class="form-label requiredField">'
                        + str(_("Proveedor"))
                        + '<span class="asteriskField">*</span></label>'
                        '<div class="input-group mb-1">'
                        '<span class="form-control supplier-display-text" id="supplier-display-text"'
                        ' role="button" tabindex="0"'
                        ' style="cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"'
                        ' onclick="openSupplierPicker()"'
                        ' onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();openSupplierPicker();}">'
                        "{% if form.instance.supplier %}{{ form.instance.supplier.name }}{% else %}"
                        '<span class=\\"text-muted fst-italic\\">Sin proveedor seleccionado</span>'
                        "{% endif %}"
                        "</span>"
                        '<button type="button" class="btn btn-outline-secondary" onclick="openSupplierPicker()">'
                        '<i class="bi bi-search"></i>'
                        "</button>"
                        "</div>"
                        "{% if form.supplier.errors %}"
                        '<div class="text-danger small">{{ form.supplier.errors.0 }}</div>'
                        "{% endif %}"
                    ),
                    Field("supplier"),
                    css_class="col-md-8",
                ),
                Column("supplier_ncf", css_class="col-md-4"),
            ),
            Row(
                Column("issue_date", css_class="col-md-4"),
                Column("due_date", css_class="col-md-4"),
            ),
            optional_field_wraps(("notes", _("Añadir notas"))),
        )


# ── PurchaseDocumentItem Formset ──────────────────────────────────────────────


class PurchaseDocumentItemForm(DocumentLineItemFormMixin):
    unit_price = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(
            attrs={"step": "1", "min": "1"}
        ),
    )

    class Meta:
        model = PurchaseDocumentItem
        fields = ["item", "description", "quantity", "unit_price", "itbis_rate", "sort_order"]
        widgets = {
            "itbis_rate": ItbisSelect(),
            "sort_order": forms.HiddenInput(),
        }

    def get_item_types(self):
        return [_Item.ItemType.PURCHASE, _Item.ItemType.BOTH]


PurchaseDocumentItemFormSet = inlineformset_factory(
    PurchaseDocument,
    PurchaseDocumentItem,
    form=PurchaseDocumentItemForm,
    fields=["item", "description", "quantity", "unit_price", "itbis_rate", "sort_order"],
    extra=0,
    can_delete=True,
    min_num=0,
)

PurchaseDocumentItemFormSetCreate = inlineformset_factory(
    PurchaseDocument,
    PurchaseDocumentItem,
    form=PurchaseDocumentItemForm,
    fields=["item", "description", "quantity", "unit_price", "itbis_rate", "sort_order"],
    extra=1,
    can_delete=False,
    min_num=0,
)


# ── SupplierPaymentForm ───────────────────────────────────────────────────────


class SupplierPaymentHeaderForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ["supplier", "date", "method", "reference", "notes"]
        widgets = {
            "date": DateInput(),
            "notes": AutosizeTextarea(attrs={"placeholder": _("Instrucciones o referencias internas…")}),
            "method": TomSelect(placeholder="Método…"),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        if organization:
            self.fields["supplier"].queryset = Supplier.objects.filter(
                organization=organization, is_active=True
            ).order_by("name")
        self.fields["supplier"].widget = forms.HiddenInput(attrs={"id": "id_supplier"})
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column(
                    HTML(
                        '<label class="form-label requiredField">'
                        + str(_("Proveedor"))
                        + '<span class="asteriskField">*</span></label>'
                        '<div class="input-group mb-1">'
                        '<span class="form-control supplier-display-text" id="supplier-display-text"'
                        ' role="button" tabindex="0"'
                        ' style="cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"'
                        ' onclick="openSupplierPicker()"'
                        ' onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();openSupplierPicker();}">'
                        "{% if form.instance.supplier %}{{ form.instance.supplier.name }}{% else %}"
                        '<span class=\\"text-muted fst-italic\\">Sin proveedor seleccionado</span>'
                        "{% endif %}"
                        "</span>"
                        '<button type="button" class="btn btn-outline-secondary" onclick="openSupplierPicker()">'
                        '<i class="bi bi-search"></i>'
                        "</button>"
                        "</div>"
                        "{% if form.supplier.errors %}"
                        '<div class="text-danger small">{{ form.supplier.errors.0 }}</div>'
                        "{% endif %}"
                    ),
                    Field("supplier"),
                    css_class="col-md-5",
                ),
                Column("date", css_class="col-md-2"),
                Column("method", css_class="col-md-3"),
                Column("reference", css_class="col-md-2"),
            ),
            optional_field_wraps(("notes", _("Añadir notas"))),
        )
