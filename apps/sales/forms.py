import re
from datetime import date, timedelta

from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, HTML, Field

from django.urls import reverse_lazy

from apps.core.layout import optional_fields
from apps.core.widgets import TomSelect, ItbisSelect, DateInput, AutosizeTextarea
from apps.core.forms import DocumentLineItemFormMixin
from apps.items.models import Item as _Item
from .models import (
    Customer,
    CustomerDepartment,
    SalesDocument,
    SalesDocumentItem,
    Payment,
    NCFSequence,
    PaymentTerm,
)

_PHONE_RE = re.compile(r"^\+?[\d\s.\-()+]{7,20}$")


# ── Customer ──────────────────────────────────────────────────────────────────


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name",
            "id_type",
            "rnc_cedula",
            "email",
            "phone",
            "contact_name",
            "contact_number",
            "address",
            "city",
            "province",
            "country",
            "default_ncf_type",
            "payment_term",
            "credit_limit",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 1}),
            "id_type": TomSelect(placeholder="Tipo de ID…"),
            "default_ncf_type": TomSelect(placeholder="NCF predeterminado…"),
            "payment_term": TomSelect(placeholder="Condición de pago…"),
        }

    change_reason = forms.CharField(
        required=False,
        label=_("Motivo del cambio"),
        widget=forms.TextInput(attrs={
            "placeholder": _("Ej. Corrección de datos, actualización de crédito…")
        }),
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        if organization:
            self.fields["payment_term"].queryset = PaymentTerm.objects.filter(
                Q(organization__isnull=True) | Q(organization=organization)
            ).order_by("days_due", "name")
        self.fields["rnc_cedula"].help_text = ""
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
            # ── General ──────────────────────────────────────────
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
            # ── Contacto ─────────────────────────────────────────
            HTML(
                f'<hr class="my-3"><p class="text-muted small text-uppercase mb-2">{_("Contacto")}</p>'
            ),
            Row(
                Column("email", css_class="col-md-6"),
                Column("phone", css_class="col-md-6"),
            ),
            Row(
                Column("contact_name", css_class="col-md-6"),
                Column("contact_number", css_class="col-md-6"),
            ),
            # ── Dirección ────────────────────────────────────────
            HTML(
                f'<hr class="my-3"><p class="text-muted small text-uppercase mb-2">{_("Dirección")}</p>'
            ),
            "address",
            Row(
                Column("city", css_class="col-md-4"),
                Column("province", css_class="col-md-4"),
                Column("country", css_class="col-md-4"),
            ),
            # ── Facturación ──────────────────────────────────────
            HTML(
                f'<hr class="my-3"><p class="text-muted small text-uppercase mb-2">{_("Facturación")}</p>'
            ),
            Row(
                Column("default_ncf_type", css_class="col-md-6"),
                Column("payment_term", css_class="col-md-6"),
                Column("credit_limit", css_class="col-md-4"),
                Column("notes", css_class="col-md-12"),
            ),
            "change_reason",
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
                    cleaned_data["rnc_cedula"] = normalized

            elif id_type == Customer.IdType.CEDULA:
                if not re.fullmatch(r"\d{11}", normalized):
                    self.add_error(
                        "rnc_cedula",
                        _("La Cédula debe tener exactamente 11 dígitos numéricos."),
                    )
                else:
                    cleaned_data["rnc_cedula"] = normalized

        normalized = cleaned_data.get("rnc_cedula") or ""
        if self._organization and normalized and "rnc_cedula" not in self.errors:
            qs = Customer.objects.filter(
                organization=self._organization,
                rnc_cedula=normalized,
                deleted_at__isnull=True,
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            existing = qs.first()
            if existing:
                self._rnc_duplicate_msg = str(
                    _("Este RNC/cédula ya está asignado al cliente «%(name)s».")
                    % {"name": existing.name}
                )
                self.add_error("rnc_cedula", self._rnc_duplicate_msg)

        return cleaned_data

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if phone and not _PHONE_RE.match(phone):
            raise forms.ValidationError(
                _(
                    "Número de teléfono inválido (7–20 dígitos, puede incluir +, espacios, guiones y paréntesis)."
                )
            )
        return phone

    def clean_contact_number(self):
        number = (self.cleaned_data.get("contact_number") or "").strip()
        if number and not _PHONE_RE.match(number):
            raise forms.ValidationError(
                _(
                    "Número de teléfono inválido (7–20 dígitos, puede incluir +, espacios, guiones y paréntesis)."
                )
            )
        return number


# ── CustomerQuickCreateForm ───────────────────────────────────────────────────


class CustomerQuickCreateForm(forms.ModelForm):
    """Minimal form for creating a customer from within the picker modal."""

    class Meta:
        model = Customer
        fields = ["name", "id_type", "rnc_cedula"]
        widgets = {
            "id_type": TomSelect(placeholder="Tipo de ID…"),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organization = organization
        self.fields["name"].widget.attrs["autofocus"] = True
        self.fields["rnc_cedula"].widget.attrs["placeholder"] = _("9 dígitos (RNC) · 11 (Cédula)")

    def clean(self):
        cleaned_data = super().clean()
        id_type = cleaned_data.get("id_type")
        rnc_cedula = (cleaned_data.get("rnc_cedula") or "").strip()

        if rnc_cedula:
            normalized = re.sub(r"[\s\-]", "", rnc_cedula)

            if id_type == Customer.IdType.RNC:
                if not re.fullmatch(r"\d{9}", normalized):
                    self.add_error("rnc_cedula", _("El RNC debe tener exactamente 9 dígitos numéricos."))
                else:
                    cleaned_data["rnc_cedula"] = normalized

            elif id_type == Customer.IdType.CEDULA:
                if not re.fullmatch(r"\d{11}", normalized):
                    self.add_error("rnc_cedula", _("La Cédula debe tener exactamente 11 dígitos numéricos."))
                else:
                    cleaned_data["rnc_cedula"] = normalized

            # Uniqueness within org (only if no prior errors on this field)
            if self._organization and "rnc_cedula" not in self.errors and normalized:
                if Customer.objects.filter(
                    organization=self._organization,
                    rnc_cedula=normalized,
                    deleted_at__isnull=True,
                ).exists():
                    self.add_error("rnc_cedula", _("Ya existe un cliente con este RNC/cédula en la organización."))

        return cleaned_data


# ── ItemQuickCreateForm ───────────────────────────────────────────────────────


class ItemQuickCreateForm(forms.ModelForm):
    """Minimal form for creating a catalog item from within the item picker modal."""

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


# ── CustomerDepartment ────────────────────────────────────────────────────────


class CustomerDepartmentForm(forms.ModelForm):
    class Meta:
        model = CustomerDepartment
        fields = ["name", "contact_name", "phone", "address", "notes", "is_active"]
        labels = {
            "is_active": _("Departamento activo"),
        }
        help_texts = {
            "is_active": _("Se mostrará en documentos y consolidación."),
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            "name",
            Row(
                Column("contact_name", css_class="col-md-6"),
                Column("phone", css_class="col-md-6"),
            ),
            "address",
            "notes",
            Field("is_active", template="components/forms/boolean_status_card.html"),
        )

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if phone and not _PHONE_RE.match(phone):
            raise forms.ValidationError(
                _(
                    "Número de teléfono inválido (7–20 dígitos, puede incluir +, espacios, guiones y paréntesis)."
                )
            )
        return phone


# ── Invoice ───────────────────────────────────────────────────────────────────


class InvoiceForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = SalesDocument
        fields = [
            "customer",
            "ncf_type",
            "issue_date",
            "due_date",
            "payment_condition",
            "notes",
            "terms",
        ]
        widgets = {
            "issue_date": DateInput(),
            "due_date": DateInput(),
            "notes": AutosizeTextarea(attrs={"placeholder": _("Instrucciones o referencias internas…")}),
            "terms": AutosizeTextarea(attrs={"placeholder": _("Términos y condiciones…")}),
            "ncf_type": TomSelect(placeholder="Tipo NCF…"),
            "payment_condition": TomSelect(placeholder="Condición…"),
        }
        error_messages = {
            "customer": {"required": _("El cliente es obligatorio.")},
            "ncf_type": {"required": _("El tipo de comprobante es obligatorio.")},
            "issue_date": {"required": _("La fecha de emisión es obligatoria.")},
            "payment_condition": {
                "required": _("La condición de pago es obligatoria.")
            },
        }

    def __init__(self, organization=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = Customer.objects.filter(
                organization=organization
            )
        self.fields["customer"].widget = forms.HiddenInput(attrs={"id": "id_customer"})

        # Only Factura de Crédito Fiscal is used — lock the field.
        # Django's disabled=True means the submitted value is ignored and the
        # model default (CREDITO_FISCAL) is always used instead.
        # self.fields["ncf_type"].disabled = True

        self.helper = FormHelper()
        self.helper.form_tag = False
        # HTML() blocks below are rendered as Django templates by crispy-forms.
        # They rely on `form` being the context variable name (crispy's default).
        # `form.instance.customer` is populated on edit; blank on create.
        self.helper.layout = Layout(
            Row(
                Column(
                    HTML(
                        '<label class="form-label requiredField">'
                        + str(_("Cliente"))
                        + '<span class="asteriskField">*</span></label>'
                        '<div class="input-group mb-1">'
                        '<span class="form-control customer-display-text" id="customer-display-text"'
                        ' style="cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"'
                        ' onclick="openCustomerPicker()">'
                        '{% if form.instance.customer %}{{ form.instance.customer.name }}{% else %}'
                        '<span class=\\"text-muted fst-italic\\">Sin cliente seleccionado</span>'
                        '{% endif %}'
                        '</span>'
                        '<button type="button" class="btn btn-outline-secondary" onclick="openCustomerPicker()">'
                        '<i class="bi bi-search"></i>'
                        '</button>'
                        '</div>'
                        '{% if form.customer.errors %}'
                        '<div class="text-danger small">{{ form.customer.errors.0 }}</div>'
                        '{% endif %}'
                    ),
                    Field("customer"),
                    css_class="col-md-8",
                ),
                Column("ncf_type", css_class="col-md-4"),
            ),
            Row(
                Column("issue_date", css_class="col-md-4"),
                Column("due_date", css_class="col-md-4"),
                Column("payment_condition", css_class="col-md-4"),
            ),
            HTML('<hr class="my-3">'),
            optional_fields(("terms", _("Añadir términos")), ("notes", _("Añadir notas"))),
        )


# ── Quotation ─────────────────────────────────────────────────────────────────


class QuotationForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = SalesDocument
        fields = [
            "customer",
            "issue_date",
            "valid_until",
            "payment_condition",
            "notes",
            "terms",
        ]
        widgets = {
            "issue_date": DateInput(),
            "valid_until": DateInput(),
            "notes": AutosizeTextarea(attrs={"placeholder": _("Instrucciones o referencias internas…")}),
            "terms": AutosizeTextarea(attrs={"placeholder": _("Términos y condiciones de la cotización…")}),
            "payment_condition": TomSelect(placeholder="Condición…"),
        }
        error_messages = {
            "customer": {"required": _("El cliente es obligatorio.")},
            "issue_date": {"required": _("La fecha de emisión es obligatoria.")},
            "valid_until": {"required": _("La fecha de validez es obligatoria.")},
            "payment_condition": {
                "required": _("La condición de pago es obligatoria.")
            },
        }

    def __init__(self, organization=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = Customer.objects.filter(
                organization=organization
            )
        self.fields["customer"].widget = forms.HiddenInput(attrs={"id": "id_customer"})

        if self.instance._state.adding and not self.is_bound and "valid_until" not in self.initial:
            self.initial["valid_until"] = date.today()

        self.helper = FormHelper()
        self.helper.form_tag = False
        # HTML() blocks below are rendered as Django templates by crispy-forms.
        # They rely on `form` being the context variable name (crispy's default).
        # `form.instance.customer` is populated on edit; blank on create.
        self.helper.layout = Layout(
            Row(
                Column(
                    HTML(
                        '<label class="form-label requiredField">'
                        + str(_("Cliente"))
                        + '<span class="asteriskField">*</span></label>'
                        '<div class="input-group mb-1">'
                        '<span class="form-control customer-display-text" id="customer-display-text"'
                        ' style="cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"'
                        ' onclick="openCustomerPicker()">'
                        '{% if form.instance.customer %}{{ form.instance.customer.name }}{% else %}'
                        '<span class=\\"text-muted fst-italic\\">Sin cliente seleccionado</span>'
                        '{% endif %}'
                        '</span>'
                        '<button type="button" class="btn btn-outline-secondary" onclick="openCustomerPicker()">'
                        '<i class="bi bi-search"></i>'
                        '</button>'
                        '</div>'
                        '{% if form.customer.errors %}'
                        '<div class="text-danger small">{{ form.customer.errors.0 }}</div>'
                        '{% endif %}'
                    ),
                    Field("customer"),
                    css_class="col-md-8",
                ),
                Column("payment_condition", css_class="col-md-4"),
            ),
            Row(
                Column("issue_date", css_class="col-md-4"),
                Column("valid_until", css_class="col-md-4"),
            ),
            HTML('<hr class="my-3">'),
            optional_fields(("terms", _("Añadir términos")), ("notes", _("Añadir notas"))),
        )


# ── Sale Order ────────────────────────────────────────────────────────────────


class SaleOrderForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = SalesDocument
        fields = [
            "customer",
            "department",
            "issue_date",
            "delivery_date",
            "payment_condition",
            "notes",
        ]
        widgets = {
            "issue_date": DateInput(),
            "delivery_date": DateInput(),
            "notes": AutosizeTextarea(attrs={"placeholder": _("Instrucciones o referencias internas…")}),
            "department": TomSelect(placeholder="Departamento…"),
            "payment_condition": TomSelect(placeholder="Condición…"),
        }
        error_messages = {
            "customer": {"required": _("El cliente es obligatorio.")},
            "issue_date": {"required": _("La fecha de emisión es obligatoria.")},
            "payment_condition": {
                "required": _("La condición de pago es obligatoria.")
            },
        }

    def __init__(self, organization=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = Customer.objects.filter(
                organization=organization
            )
        self.fields["delivery_date"].required = False
        if self.instance._state.adding and not self.is_bound and "delivery_date" not in self.initial:
            self.initial["delivery_date"] = date.today()
        self.fields["department"].required = False
        self.fields["department"].empty_label = _("— Sin departamento —")

        # Resolve which customer is currently active so we can pre-populate options.
        # Priority: existing saved instance → POST data (re-render after error).
        customer_id = None
        if self.instance and self.instance.pk and self.instance.customer_id:
            customer_id = self.instance.customer_id
        elif self.data.get("customer"):
            customer_id = self.data.get("customer")

        if customer_id:
            self.fields["department"].queryset = CustomerDepartment.objects.filter(
                customer_id=customer_id,
                organization=organization,
                is_active=True,
                deleted_at__isnull=True,
            ).order_by("name")
        else:
            self.fields["department"].queryset = CustomerDepartment.objects.none()
        if self.fields["department"].queryset.exists():
            self.fields["department"].widget.attrs.pop("disabled", None)
        else:
            self.fields["department"].widget.attrs["disabled"] = "disabled"

        # The customer picker sets this hidden value. The sale order page reloads
        # department options explicitly because the picker changes the value in JS.
        self.fields["customer"].widget = forms.HiddenInput(attrs={
            "id": "id_customer",
        })

        self.helper = FormHelper()
        self.helper.form_tag = False
        # HTML() blocks below are rendered as Django templates by crispy-forms.
        # They rely on `form` being the context variable name (crispy's default).
        # `form.instance.customer` is populated on edit; blank on create.
        self.helper.layout = Layout(
            Row(
                Column(
                    HTML(
                        '<label class="form-label requiredField">'
                        + str(_("Cliente"))
                        + '<span class="asteriskField">*</span></label>'
                        '<div class="input-group mb-1">'
                        '<span class="form-control customer-display-text" id="customer-display-text"'
                        ' style="cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"'
                        ' onclick="openCustomerPicker()">'
                        '{% if form.instance.customer %}{{ form.instance.customer.name }}{% else %}'
                        '<span class=\\"text-muted fst-italic\\">Sin cliente seleccionado</span>'
                        '{% endif %}'
                        '</span>'
                        '<button type="button" class="btn btn-outline-secondary" onclick="openCustomerPicker()">'
                        '<i class="bi bi-search"></i>'
                        '</button>'
                        '</div>'
                        '{% if form.customer.errors %}'
                        '<div class="text-danger small">{{ form.customer.errors.0 }}</div>'
                        '{% endif %}'
                    ),
                    Field("customer"),
                    css_class="col-md-8",
                ),
                Column("payment_condition", css_class="col-md-4"),
            ),
            Row(
                Column("department", css_class="col-md-8"),
            ),
            Row(
                Column("issue_date", css_class="col-md-4"),
                Column("delivery_date", css_class="col-md-4"),
            ),
            HTML('<hr class="my-3">'),
            optional_fields(("notes", _("Añadir notas"))),
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
    Optionally filtered to a single customer department.
    """

    customer = forms.ModelChoiceField(
        queryset=Customer.objects.none(),
        label=_("Cliente"),
        widget=TomSelect(placeholder="Cliente…"),
    )
    department = forms.ModelChoiceField(
        queryset=CustomerDepartment.objects.none(),
        required=False,
        label=_("Departamento"),
        empty_label=_("— Todos los departamentos —"),
        help_text=_(
            "Opcional — deje vacío para consolidar todas las órdenes del cliente."
        ),
        widget=TomSelect(placeholder="Departamento…"),
    )
    period_start = forms.DateField(
        label=_("Desde"),
        widget=DateInput(),
    )
    period_end = forms.DateField(
        label=_("Hasta"),
        widget=DateInput(),
    )
    ncf_type = forms.ChoiceField(
        label=_("Tipo de comprobante"),
        choices=[(k, v) for k, v in SalesDocument._meta.get_field("ncf_type").choices],
        widget=TomSelect(placeholder="Tipo NCF…"),
    )

    def __init__(self, organization=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = Customer.objects.filter(
                organization=organization
            )

        # Populate department choices for the customer currently in POST data.
        # On a fresh GET there is no customer yet, so queryset stays empty.
        customer_id = self.data.get("customer") or None
        if customer_id:
            self.fields["department"].queryset = CustomerDepartment.objects.filter(
                customer_id=customer_id,
                organization=organization,
                is_active=True,
                deleted_at__isnull=True,
            ).order_by("name")

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
            "department",
            Row(
                Column("period_start", css_class="col-md-4"),
                Column("period_end", css_class="col-md-4"),
                Column("ncf_type", css_class="col-md-4"),
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("period_start")
        end = cleaned_data.get("period_end")
        if start and end and start > end:
            raise forms.ValidationError(
                _("La fecha de inicio debe ser anterior a la fecha de fin.")
            )
        # Ensure the chosen department actually belongs to the chosen customer.
        customer = cleaned_data.get("customer")
        department = cleaned_data.get("department")
        if department and customer and department.customer_id != customer.pk:
            raise forms.ValidationError(
                _("El departamento seleccionado no pertenece al cliente indicado.")
            )
        return cleaned_data


# ── PaymentTerm ───────────────────────────────────────────────────────────────


class PaymentTermForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = PaymentTerm
        fields = ["name", "description", "days_due"]
        labels = {
            "name":        _("Nombre"),
            "description": _("Descripción"),
            "days_due":    _("Días de vencimiento"),
        }
        widgets = {
            "description": forms.TextInput(attrs={"placeholder": _("Ej. Pago a 30 días")}),
        }
        help_texts = {
            "days_due": _("Número de días desde la emisión hasta el vencimiento."),
        }
        error_messages = {
            "name":     {"required": _("El nombre es obligatorio.")},
            "days_due": {"required": _("Los días de vencimiento son obligatorios.")},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("name",     css_class="col-md-8"),
                Column("days_due", css_class="col-md-4"),
            ),
            "description",
        )


# ── InvoiceItem formset ───────────────────────────────────────────────────────


class InvoiceItemForm(DocumentLineItemFormMixin):
    class Meta:
        model = SalesDocumentItem
        fields = ["item", "description", "quantity", "unit_price", "itbis_rate", "sort_order"]
        widgets = {
            "unit_price": forms.NumberInput(
                attrs={"step": "0.01", "min": "0"}
            ),
            "itbis_rate": ItbisSelect(),
            "sort_order": forms.HiddenInput(),
        }

    def get_item_types(self):
        return [_Item.ItemType.SALE, _Item.ItemType.BOTH]

    def clean_quantity(self):
        qty = self.cleaned_data.get("quantity")
        if qty is not None and qty < 1:
            raise forms.ValidationError(_("La cantidad debe ser mayor o igual a 1."))
        return qty

    def clean_sort_order(self):
        val = self.cleaned_data.get("sort_order")
        if val is None and self.instance and self.instance.pk:
            return self.instance.sort_order
        return val if val is not None else 0

    def clean_unit_price(self):
        price = self.cleaned_data.get("unit_price")
        if price is not None and price < 0:
            raise forms.ValidationError(_("El precio unitario no puede ser negativo."))
        return price


InvoiceItemFormSet = inlineformset_factory(
    SalesDocument,
    SalesDocumentItem,
    form=InvoiceItemForm,
    extra=0,
    can_delete=True,
    min_num=0,  # allow saving drafts with no items
    validate_min=False,
)

InvoiceItemFormSetCreate = inlineformset_factory(
    SalesDocument,
    SalesDocumentItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


# ── Payment ───────────────────────────────────────────────────────────────────


class PaymentHeaderForm(forms.ModelForm):
    """
    Full payment header form used in PaymentCreateView.
    Customer field triggers HTMX load of outstanding invoices.
    Amount is derived from the allocations — not a user input here.
    """

    use_required_attribute = False

    class Meta:
        model = Payment
        fields = ["customer", "date", "method", "reference", "notes"]
        widgets = {
            "date": DateInput(),
            "notes": AutosizeTextarea(attrs={"placeholder": _("Instrucciones o referencias internas…")}),
            "method": TomSelect(placeholder="Método…"),
        }
        error_messages = {
            "customer": {"required": _("El cliente es obligatorio.")},
            "date": {"required": _("La fecha es obligatoria.")},
            "method": {"required": _("El método de pago es obligatorio.")},
        }

    def __init__(self, organization=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["customer"].queryset = Customer.objects.filter(
                organization=organization
            ).order_by("name")
        self.fields["customer"].empty_label = _("— Seleccione un cliente —")
        self.fields["customer"].widget = forms.HiddenInput(
            attrs={
                "id": "id_customer",
                "hx-get": reverse_lazy("sales:payment_outstanding_invoices"),
                "hx-trigger": "change",
                "hx-target": "#allocation-tbody",
                "hx-swap": "innerHTML",
                "hx-include": "this",
            }
        )
        customer_id = None
        if self.instance and self.instance.pk and self.instance.customer_id:
            customer_id = self.instance.customer_id
        elif self.data.get("customer"):
            customer_id = self.data.get("customer")
        elif self.initial.get("customer"):
            customer_id = self.initial.get("customer")
        self.selected_customer = None
        if customer_id:
            self.selected_customer = self.fields["customer"].queryset.filter(
                pk=customer_id
            ).first()
        self.fields["reference"].widget.attrs["class"] = "form-control"
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column(
                    HTML(
                        '<label class="form-label requiredField">'
                        + str(_("Cliente"))
                        + '<span class="asteriskField">*</span></label>'
                        '<div class="input-group mb-1">'
                        '<span class="form-control customer-display-text" id="customer-display-text"'
                        ' style="cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"'
                        ' onclick="openCustomerPicker()">'
                        '{% if form.selected_customer %}{{ form.selected_customer.name }}'
                        '{% if form.selected_customer.rnc_cedula %} ({{ form.selected_customer.rnc_cedula }}){% endif %}'
                        '{% else %}<span class=\\"text-muted fst-italic\\">Sin cliente seleccionado</span>'
                        '{% endif %}'
                        '</span>'
                        '<button type="button" class="btn btn-outline-secondary" onclick="openCustomerPicker()">'
                        '<i class="bi bi-search"></i>'
                        '</button>'
                        '</div>'
                        '{% if form.customer.errors %}'
                        '<div class="text-danger small">{{ form.customer.errors.0 }}</div>'
                        '{% endif %}'
                    ),
                    Field("customer"),
                    css_class="col-md-5",
                ),
                Column("date", css_class="col-md-2"),
                Column("method", css_class="col-md-3"),
                Column("reference", css_class="col-md-2"),
            ),
            HTML('<hr class="my-3">'),
            optional_fields(("notes", _("Añadir notas"))),
        )


class PaymentForm(forms.ModelForm):
    """
    Header form for registering a payment receipt.
    Used for the quick single-invoice modal on invoice_detail.html.
    The full multi-invoice form lives in PaymentCreateView.
    """

    use_required_attribute = False

    class Meta:
        model = Payment
        fields = ["amount", "date", "method", "reference", "notes"]
        widgets = {
            "date": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 1}),
            "method": TomSelect(placeholder="Método…"),
        }
        error_messages = {
            "amount": {"required": _("El monto es obligatorio.")},
            "date": {"required": _("La fecha es obligatoria.")},
            "method": {"required": _("El método de pago es obligatorio.")},
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

    use_required_attribute = False

    class Meta:
        model = SalesDocument
        fields = ["ncf_type", "issue_date", "due_date", "notes", "terms"]
        widgets = {
            "issue_date": DateInput(),
            "due_date": DateInput(),
            "notes": AutosizeTextarea(attrs={"placeholder": _("Instrucciones o referencias internas…")}),
            "terms": AutosizeTextarea(attrs={"placeholder": _("Términos y condiciones…")}),
            "ncf_type": TomSelect(placeholder="Tipo NCF…"),
        }
        error_messages = {
            "ncf_type": {"required": _("El tipo de comprobante es obligatorio.")},
            "issue_date": {"required": _("La fecha de emisión es obligatoria.")},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict to note types only (both physical and electronic)
        self.fields["ncf_type"].choices = [
            (3, _("03 – Nota de Débito")),
            (4, _("04 – Nota de Crédito")),
            (33, _("33 – Nota de Débito (e-CF)")),
            (34, _("34 – Nota de Crédito (e-CF)")),
        ]
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("ncf_type", css_class="col-md-4"),
                Column("issue_date", css_class="col-md-4"),
                Column("due_date", css_class="col-md-4"),
            ),
            HTML('<hr class="my-3">'),
            optional_fields(("terms", _("Añadir términos")), ("notes", _("Añadir notas"))),
        )


# ── NCFSequence ───────────────────────────────────────────────────────────────


class NCFSequenceForm(forms.ModelForm):
    class Meta:
        model = NCFSequence
        fields = ["ncf_type", "series", "current_seq", "max_seq", "is_active"]
        labels = {
            "is_active": _("Secuencia activa"),
        }
        help_texts = {
            "is_active": _("Disponible para asignar comprobantes al confirmar facturas."),
        }
        widgets = {
            "ncf_type": TomSelect(placeholder="Tipo NCF…"),
            "series": TomSelect(placeholder="Serie…"),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is not None and not self.instance.pk:
            self.instance.organization = organization
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("series", css_class="col-md-5"),
                Column("ncf_type", css_class="col-md-7"),
            ),
            Row(
                Column("current_seq", css_class="col-md-4"),
                Column("max_seq", css_class="col-md-4"),
                Column(
                    Field("is_active", template="components/forms/boolean_status_card.html"),
                    css_class="col-md-4",
                ),
            ),
        )

    def clean(self):
        cleaned = super().clean()
        series = cleaned.get("series")
        ncf_type = cleaned.get("ncf_type")
        max_seq = cleaned.get("max_seq")

        if series and ncf_type:
            if (
                series == NCFSequence.Series.PHYSICAL
                and ncf_type not in NCFSequence.PHYSICAL_TYPES
            ):
                self.add_error(
                    "ncf_type",
                    _(
                        "Los comprobantes físicos (B) usan tipos 01–16. "
                        "Para tipos 31–47 seleccione serie E (electrónico)."
                    ),
                )
            elif (
                series == NCFSequence.Series.ELECTRONIC
                and ncf_type not in NCFSequence.ELECTRONIC_TYPES
            ):
                self.add_error(
                    "ncf_type",
                    _(
                        "Los comprobantes electrónicos (E) usan tipos 31–47. "
                        "Para tipos 01–16 seleccione serie B (físico)."
                    ),
                )

        if series and max_seq is not None:
            if series == NCFSequence.Series.PHYSICAL and max_seq > 99_999_999:
                self.add_error(
                    "max_seq",
                    _(
                        "Los comprobantes físicos admiten hasta 8 dígitos (máx. 99,999,999)."
                    ),
                )
            elif series == NCFSequence.Series.ELECTRONIC and max_seq > 9_999_999_999:
                self.add_error(
                    "max_seq",
                    _(
                        "Los comprobantes electrónicos admiten hasta 10 dígitos (máx. 9,999,999,999)."
                    ),
                )

        return cleaned
