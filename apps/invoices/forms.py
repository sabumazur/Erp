import re
from datetime import date, timedelta

from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Field

from django.urls import reverse_lazy

from .models import Customer, Invoice, InvoiceItem, Payment, NCFSequence
from .validators import validate_rnc, validate_cedula

_PHONE_RE = re.compile(r"^\+?[\d\s.\-()+]{7,20}$")


# ── Customer ──────────────────────────────────────────────────────────────────

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name", "id_type", "rnc_cedula",
            "email", "phone", "contact_name", "contact_number",
            "address", "city", "province", "country",
            "default_ncf_type", "default_payment_method", "payment_term", "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rnc_cedula"].help_text = ""
        self.fields["rnc_cedula"].widget.attrs.update({
            "placeholder": _("9 dígitos (RNC) · 11 (Cédula)"),
            "hx-get": reverse_lazy("invoices:rnc_lookup"),
            "hx-trigger": "blur",
            "hx-target": "#rnc-lookup-result",
            "hx-include": "closest form",
            "hx-indicator": "#rnc-lookup-spinner",
        })
        self.helper = FormHelper()

        self.helper.form_tag = False
        self.helper.layout = Layout(
            # ── General ──────────────────────────────────────────
            HTML(f'<p class="text-muted small text-uppercase mb-2 mt-1">{_("General")}</p>'),
            "name",
            Row(
                Column("id_type", css_class="col-md-5"),
                Column("rnc_cedula", css_class="col-md-7"),
            ),
            HTML(
                '<div class="d-flex align-items-center gap-2 mb-2" style="min-height:1.6rem">'
                '<span id="rnc-lookup-spinner" class="htmx-indicator spinner-border spinner-border-sm text-secondary" role="status"></span>'
                '<div id="rnc-lookup-result"></div>'
                '</div>'
            ),
            # ── Contacto ─────────────────────────────────────────
            HTML(f'<hr class="my-3"><p class="text-muted small text-uppercase mb-2">{_("Contacto")}</p>'),
            Row(
                Column("email", css_class="col-md-6"),
                Column("phone", css_class="col-md-6"),
            ),
            Row(
                Column("contact_name", css_class="col-md-6"),
                Column("contact_number", css_class="col-md-6"),
            ),
            # ── Dirección ────────────────────────────────────────
            HTML(f'<hr class="my-3"><p class="text-muted small text-uppercase mb-2">{_("Dirección")}</p>'),
            "address",
            Row(
                Column("city", css_class="col-md-4"),
                Column("province", css_class="col-md-4"),
                Column("country", css_class="col-md-4"),
            ),
            # ── Facturación ──────────────────────────────────────
            HTML(f'<hr class="my-3"><p class="text-muted small text-uppercase mb-2">{_("Facturación")}</p>'),
            "default_ncf_type",
            Row(
                Column("default_payment_method", css_class="col-md-6"),
                Column("payment_term", css_class="col-md-6"),
            ),
            "notes",
        )

    def clean(self):
        cleaned_data = super().clean()
        id_type = cleaned_data.get("id_type")
        rnc_cedula = (cleaned_data.get("rnc_cedula") or "").strip()

        if rnc_cedula:
            normalized = re.sub(r"[\s\-]", "", rnc_cedula)

            if id_type == Customer.IdType.RNC:
                if not re.fullmatch(r"\d{9}", normalized):
                    self.add_error(
                        "rnc_cedula",
                        _("El RNC debe tener exactamente 9 dígitos numéricos."),
                    )
                else:
                    ok, msg = validate_rnc(normalized)
                    if not ok:
                        self.add_error("rnc_cedula", msg)
                    else:
                        cleaned_data["rnc_cedula"] = normalized

            elif id_type == Customer.IdType.CEDULA:
                if not re.fullmatch(r"\d{11}", normalized):
                    self.add_error(
                        "rnc_cedula",
                        _("La Cédula debe tener exactamente 11 dígitos numéricos."),
                    )
                else:
                    ok, msg = validate_cedula(normalized)
                    if not ok:
                        self.add_error("rnc_cedula", msg)
                    else:
                        cleaned_data["rnc_cedula"] = normalized

            elif id_type in (Customer.IdType.PASAPORTE, Customer.IdType.EXTERIOR):
                if not re.fullmatch(r"[A-Za-z0-9\-]{4,20}", rnc_cedula):
                    self.add_error(
                        "rnc_cedula",
                        _("Identificación inválida (4–20 caracteres alfanuméricos)."),
                    )

        return cleaned_data

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if phone and not _PHONE_RE.match(phone):
            raise forms.ValidationError(_("Número de teléfono inválido (7–20 dígitos, puede incluir +, espacios, guiones y paréntesis)."))
        return phone

    def clean_contact_number(self):
        number = (self.cleaned_data.get("contact_number") or "").strip()
        if number and not _PHONE_RE.match(number):
            raise forms.ValidationError(_("Número de teléfono inválido (7–20 dígitos, puede incluir +, espacios, guiones y paréntesis)."))
        return number


# ── Invoice ───────────────────────────────────────────────────────────────────

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "customer", "ncf_type",
            "issue_date", "due_date", "payment_condition",
            "notes", "terms",
        ]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "due_date":   forms.DateInput(attrs={"type": "date"}),
            "notes":      forms.TextInput(attrs={"placeholder": _("Notas internas…")}),
            "terms":      forms.TextInput(attrs={"placeholder": _("Términos y condiciones…")}),
        }

    def __init__(self, organization=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = (
                Customer.objects.filter(organization=organization)
            )

        # Only Factura de Crédito Fiscal is used — lock the field.
        # Django's disabled=True means the submitted value is ignored and the
        # model default (CREDITO_FISCAL) is always used instead.
        self.fields["ncf_type"].disabled = True

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("customer", css_class="col-md-8"),
                Column("ncf_type", css_class="col-md-4"),
            ),
            Row(
                Column("issue_date", css_class="col-md-4"),
                Column("due_date", css_class="col-md-4"),
                Column("payment_condition", css_class="col-md-4"),
            ),
            HTML('<hr class="my-3">'),
            Row(
                Column("notes", css_class="col-md-6"),
                Column("terms", css_class="col-md-6"),
            ),
        )


# ── Quotation ─────────────────────────────────────────────────────────────────

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "customer",
            "issue_date", "valid_until", "payment_condition",
            "notes", "terms",
        ]
        widgets = {
            "issue_date":  forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "notes":       forms.TextInput(attrs={"placeholder": _("Notas internas…")}),
            "terms":       forms.TextInput(attrs={"placeholder": _("Términos y condiciones…")}),
        }

    def __init__(self, organization=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = (
                Customer.objects.filter(organization=organization)
            )

        # Default valid_until = today + 30 days for new quotations
        if not self.instance.pk:
            self.fields["valid_until"].initial = date.today() + timedelta(days=30)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("customer", css_class="col-md-8"),
                Column("payment_condition", css_class="col-md-4"),
            ),
            Row(
                Column("issue_date", css_class="col-md-4"),
                Column("valid_until", css_class="col-md-4"),
            ),
            HTML('<hr class="my-3">'),
            Row(
                Column("notes", css_class="col-md-6"),
                Column("terms", css_class="col-md-6"),
            ),
        )


# ── Sale Order ────────────────────────────────────────────────────────────────

class SaleOrderForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "customer",
            "issue_date", "delivery_date", "payment_condition",
            "notes",
        ]
        widgets = {
            "issue_date":    forms.DateInput(attrs={"type": "date"}),
            "delivery_date": forms.DateInput(attrs={"type": "date"}),
            "notes":         forms.TextInput(attrs={"placeholder": _("Notas internas…")}),
        }

    def __init__(self, organization=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = (
                Customer.objects.filter(organization=organization)
            )
        self.fields["delivery_date"].required = False

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("customer", css_class="col-md-8"),
                Column("payment_condition", css_class="col-md-4"),
            ),
            Row(
                Column("issue_date", css_class="col-md-4"),
                Column("delivery_date", css_class="col-md-4"),
            ),
            HTML('<hr class="my-3">'),
            "notes",
        )


# ── Deliver Sale Order ────────────────────────────────────────────────────────

class SaleOrderDeliverForm(forms.Form):
    """Simple form for capturing the delivery signature."""
    signed_by = forms.CharField(
        max_length=150,
        label=_("Recibido por"),
        help_text=_("Nombre completo de la persona que recibe la entrega."),
        widget=forms.TextInput(attrs={"placeholder": _("Nombre y apellido")}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout("signed_by")


# ── Consolidation ─────────────────────────────────────────────────────────────

class ConsolidateForm(forms.Form):
    """
    Parameters for consolidating sale orders into a single invoice.
    """
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.none(),
        label=_("Cliente"),
        widget=forms.Select(attrs={
            "hx-get": "",          # set in view via hx-get attr on the form
            "hx-trigger": "change",
            "hx-target": "#consolidate-preview",
            "hx-include": "closest form",
        }),
    )
    period_start = forms.DateField(
        label=_("Desde"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    period_end = forms.DateField(
        label=_("Hasta"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    ncf_type = forms.ChoiceField(
        label=_("Tipo de comprobante"),
        choices=[(k, v) for k, v in Invoice._meta.get_field("ncf_type").choices],
    )

    def __init__(self, organization=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = Customer.objects.filter(
                organization=organization
            )
        # Default period = previous calendar month
        today = date.today()
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        self.fields["period_start"].initial = last_month_start
        self.fields["period_end"].initial = last_month_end

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            "customer",
            Row(
                Column("period_start", css_class="col-md-4"),
                Column("period_end",   css_class="col-md-4"),
                Column("ncf_type",     css_class="col-md-4"),
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("period_start")
        end   = cleaned_data.get("period_end")
        if start and end and start > end:
            raise forms.ValidationError(_("La fecha de inicio debe ser anterior a la fecha de fin."))
        return cleaned_data


# ── InvoiceItem formset ───────────────────────────────────────────────────────

class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ["item", "description", "quantity", "unit_price", "itbis_rate"]
        widgets = {
            "item": forms.HiddenInput(),
            "description": forms.TextInput(attrs={
                "class": "form-control form-control-sm",
            }),
            "quantity":   forms.NumberInput(attrs={
                "step": "0.0001", "min": "0.0001",
                "class": "form-control form-control-sm text-end",
                "x-model": "qty",
                "x-on:input": "recalc()",
            }),
            "unit_price": forms.NumberInput(attrs={
                "step": "0.01", "min": "0",
                "class": "form-control form-control-sm text-end",
                "x-model": "price",
                "x-on:input": "recalc()",
            }),
            "itbis_rate": forms.Select(attrs={
                "class": "form-select form-select-sm",
                "x-model": "rate",
                "x-on:change": "recalc()",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].required = False


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# ── Payment ───────────────────────────────────────────────────────────────────

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "date", "method", "reference", "notes"]
        widgets = {
            "date":  forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("amount", css_class="col-md-4"),
                Column("date", css_class="col-md-4"),
                Column("method", css_class="col-md-4"),
            ),
            "reference",
            "notes",
        )


# ── Credit / Debit Note ───────────────────────────────────────────────────────

class CreditNoteForm(forms.ModelForm):
    """
    Simplified form for creating a Nota de Crédito (34) or Nota de Débito (33)
    that references an existing confirmed invoice.
    """
    class Meta:
        model = Invoice
        fields = ["ncf_type", "issue_date", "due_date", "notes", "terms"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "due_date":   forms.DateInput(attrs={"type": "date"}),
            "notes":      forms.Textarea(attrs={"rows": 3}),
            "terms":      forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict to note types only
        self.fields["ncf_type"].choices = [
            (33, _("33 – Nota de Débito")),
            (34, _("34 – Nota de Crédito")),
        ]
        self.helper = FormHelper()
        self.helper.form_tag = False


# ── NCFSequence ───────────────────────────────────────────────────────────────

class NCFSequenceForm(forms.ModelForm):
    class Meta:
        model = NCFSequence
        fields = ["ncf_type", "series", "current_seq", "max_seq", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("ncf_type", css_class="col-md-4"),
                Column("series", css_class="col-md-2"),
                Column("is_active", css_class="col-md-2 pt-4"),
            ),
            Row(
                Column("current_seq", css_class="col-md-4"),
                Column("max_seq", css_class="col-md-4"),
            ),
        )
