import re
from decimal import Decimal

from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML

from apps.items.models import Item as _Item
from apps.sales.models import PaymentTerm
from .models import (
    Supplier,
    SupplierDepartment,
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
            "id_number",
            "email",
            "phone",
            "contact_name",
            "address",
            "city",
            "default_ncf_type",
            "payment_term",
            "credit_limit",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    change_reason = forms.CharField(
        required=False,
        label=_("Motivo del cambio"),
        widget=forms.TextInput(attrs={"placeholder": _("Corrección de datos, actualización…")}),
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        if organization:
            self.fields["payment_term"].queryset = PaymentTerm.objects.filter(
                Q(organization__isnull=True) | Q(organization=organization)
            ).order_by("days_due", "name")
        self.fields["id_number"].widget.attrs.update({"placeholder": _("9 dígitos (RNC) · 11 (Cédula)")})
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            HTML(f'<p class="text-muted small text-uppercase mb-2 mt-1">{_("General")}</p>'),
            "name",
            Row(
                Column("id_type", css_class="col-md-5"),
                Column("id_number", css_class="col-md-7"),
            ),
            HTML(f'<hr class="my-3"><p class="text-muted small text-uppercase mb-2">{_("Contacto")}</p>'),
            Row(
                Column("email", css_class="col-md-6"),
                Column("phone", css_class="col-md-6"),
            ),
            "contact_name",
            "address",
            Row(
                Column("city", css_class="col-md-6"),
            ),
            HTML(f'<hr class="my-3"><p class="text-muted small text-uppercase mb-2">{_("Compras")}</p>'),
            Row(
                Column("default_ncf_type", css_class="col-md-6"),
                Column("payment_term", css_class="col-md-6"),
            ),
            "credit_limit",
            "notes",
            "change_reason",
        )

    def clean(self):
        cleaned_data = super().clean()
        id_type = cleaned_data.get("id_type")
        id_number = (cleaned_data.get("id_number") or "").strip()

        if id_number:
            from apps.sales.validators import validate_rnc, validate_cedula
            normalized = re.sub(r"[\s\-]", "", id_number)

            if id_type == Supplier.IdType.RNC:
                if not re.fullmatch(r"\d{9}", normalized):
                    self.add_error("id_number", _("El RNC debe tener exactamente 9 dígitos numéricos."))
                else:
                    ok, msg = validate_rnc(normalized)
                    if not ok:
                        self.add_error("id_number", msg)
                    else:
                        cleaned_data["id_number"] = normalized

            elif id_type == Supplier.IdType.CEDULA:
                if not re.fullmatch(r"\d{11}", normalized):
                    self.add_error("id_number", _("La Cédula debe tener exactamente 11 dígitos numéricos."))
                else:
                    ok, msg = validate_cedula(normalized)
                    if not ok:
                        self.add_error("id_number", msg)
                    else:
                        cleaned_data["id_number"] = normalized

            elif id_type in (Supplier.IdType.PASAPORTE, Supplier.IdType.EXTERIOR):
                if not re.fullmatch(r"[A-Za-z0-9\-]{4,20}", id_number):
                    self.add_error("id_number", _("Identificación inválida (4–20 caracteres alfanuméricos)."))

            normalized = cleaned_data.get("id_number") or ""
            if self._organization and normalized and "id_number" not in self.errors:
                qs = Supplier.objects.filter(
                    organization=self._organization,
                    id_number=normalized,
                    deleted_at__isnull=True,
                )
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                existing = qs.first()
                if existing:
                    self._id_duplicate_msg = str(
                        _("Este RNC/cédula ya está asignado al proveedor «%(name)s».") % {"name": existing.name}
                    )
                    self.add_error("id_number", self._id_duplicate_msg)

        return cleaned_data

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if phone and not _PHONE_RE.match(phone):
            raise forms.ValidationError(_("Número de teléfono inválido (7–20 dígitos)."))
        return phone


# ── SupplierQuickCreateForm ───────────────────────────────────────────────────


class SupplierQuickCreateForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "id_type", "id_number"]

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        self.fields["name"].widget.attrs["autofocus"] = True
        self.fields["id_number"].widget.attrs["placeholder"] = _("9 dígitos (RNC) · 11 (Cédula)")

    def clean(self):
        cleaned_data = super().clean()
        id_type = cleaned_data.get("id_type")
        id_number = (cleaned_data.get("id_number") or "").strip()

        if id_number:
            from apps.sales.validators import validate_rnc, validate_cedula
            normalized = re.sub(r"[\s\-]", "", id_number)

            if id_type == Supplier.IdType.RNC:
                if not re.fullmatch(r"\d{9}", normalized):
                    self.add_error("id_number", _("El RNC debe tener exactamente 9 dígitos."))
                else:
                    ok, msg = validate_rnc(normalized)
                    if not ok:
                        self.add_error("id_number", msg)
                    else:
                        cleaned_data["id_number"] = normalized

            elif id_type == Supplier.IdType.CEDULA:
                if not re.fullmatch(r"\d{11}", normalized):
                    self.add_error("id_number", _("La Cédula debe tener exactamente 11 dígitos."))
                else:
                    ok, msg = validate_cedula(normalized)
                    if not ok:
                        self.add_error("id_number", msg)
                    else:
                        cleaned_data["id_number"] = normalized

        return cleaned_data


# ── SupplierDepartmentForm ────────────────────────────────────────────────────


class SupplierDepartmentForm(forms.ModelForm):
    class Meta:
        model = SupplierDepartment
        fields = ["name", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout("name", "is_active")


# ── PurchaseOrderForm ─────────────────────────────────────────────────────────


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseDocument
        fields = [
            "supplier",
            "issue_date",
            "expected_date",
            "currency",
            "exchange_rate",
            "notes",
        ]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "expected_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        if organization:
            self.fields["supplier"].queryset = Supplier.objects.filter(
                organization=organization, is_active=True
            ).order_by("name")
        self.helper = FormHelper()
        self.helper.form_tag = False


# ── SupplierInvoiceForm ───────────────────────────────────────────────────────


class SupplierInvoiceForm(forms.ModelForm):
    class Meta:
        model = PurchaseDocument
        fields = [
            "supplier",
            "supplier_ncf",
            "supplier_ncf_type",
            "issue_date",
            "due_date",
            "currency",
            "exchange_rate",
            "notes",
        ]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        if organization:
            self.fields["supplier"].queryset = Supplier.objects.filter(
                organization=organization, is_active=True
            ).order_by("name")
        self.helper = FormHelper()
        self.helper.form_tag = False


# ── PurchaseDocumentItem Formset ──────────────────────────────────────────────


class PurchaseDocumentItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseDocumentItem
        fields = ["item", "description", "quantity", "unit_price", "itbis_rate"]
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": _("Descripción del artículo")}),
            "quantity": forms.NumberInput(attrs={"step": "0.0001", "min": "0.0001"}),
            "unit_price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        if organization:
            self.fields["item"].queryset = _Item.objects.filter(
                organization=organization,
                is_active=True,
                item_type__in=[_Item.ItemType.PURCHASE, _Item.ItemType.BOTH],
            ).order_by("name")
        self.fields["item"].required = False
        self.fields["item"].widget.attrs.update({"class": "form-select"})


PurchaseDocumentItemFormSet = inlineformset_factory(
    PurchaseDocument,
    PurchaseDocumentItem,
    form=PurchaseDocumentItemForm,
    fields=["item", "description", "quantity", "unit_price", "itbis_rate"],
    extra=1,
    can_delete=True,
    min_num=0,
)

PurchaseDocumentItemFormSetCreate = inlineformset_factory(
    PurchaseDocument,
    PurchaseDocumentItem,
    form=PurchaseDocumentItemForm,
    fields=["item", "description", "quantity", "unit_price", "itbis_rate"],
    extra=3,
    can_delete=False,
    min_num=0,
)


# ── SupplierPaymentForm ───────────────────────────────────────────────────────


class SupplierPaymentHeaderForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ["supplier", "date", "method", "reference", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        if organization:
            self.fields["supplier"].queryset = Supplier.objects.filter(
                organization=organization, is_active=True
            ).order_by("name")
        self.helper = FormHelper()
        self.helper.form_tag = False
