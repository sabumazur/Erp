from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, HTML, Row, Column, Field
from allauth.account.forms import SignupForm, ChangePasswordForm
from apps.core.models import Module
from .models import User, Organization, Membership, Team

_PASSWORD_HELP = (
    "Usa 8 o más caracteres con una combinación de letras, números y símbolos."
)


class CustomSignupForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("password1", "password2"):
            if field_name in self.fields:
                self.fields[field_name].widget.attrs["autocomplete"] = "new-password"
        if "password1" in self.fields:
            self.fields["password1"].help_text = ""


class CustomChangePasswordForm(ChangePasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "password1" in self.fields:
            self.fields["password1"].help_text = _PASSWORD_HELP


class InvitationForm(forms.Form):
    email = forms.EmailField(
        label=_("Correo electrónico"),
        widget=forms.EmailInput(attrs={"placeholder": "colega@ejemplo.com"}),
    )
    role = forms.ChoiceField(
        label=_("Rol"),
        choices=Membership.Role.choices,
        initial=Membership.Role.MEMBER,
    )

    def clean_email(self):
        return self.cleaned_data["email"].lower()


class StaffCreateOrganizationForm(forms.ModelForm):
    owner_email = forms.EmailField(
        label=_("Correo del propietario"),
        help_text=_("Se enviará una invitación de propietario a esta dirección."),
        widget=forms.EmailInput(attrs={"placeholder": "propietario@empresa.com"}),
    )

    class Meta:
        model = Organization
        fields = [
            "name",
            "tax_id",
            "email",
            "phone",
            "website",
            "address",
            "city",
            "state",
            "zip_code",
            "country",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs["autofocus"] = True
        for field_name, field in self.fields.items():
            if field_name not in ("name", "owner_email"):
                field.required = False
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            "name",
            HTML(
                f'<hr class="my-3"><p class="text-muted small text-uppercase mb-3">{_("Contacto")}</p>'
            ),
            Row(
                Column("tax_id", css_class="col-md-6"),
                Column("email", css_class="col-md-6"),
            ),
            Row(
                Column("phone", css_class="col-md-6"),
                Column("website", css_class="col-md-6"),
            ),
            HTML(
                f'<hr class="my-3"><p class="text-muted small text-uppercase mb-3">{_("Dirección")}</p>'
            ),
            "address",
            Row(
                Column("city", css_class="col-md-5"),
                Column("state", css_class="col-md-4"),
                Column("zip_code", css_class="col-md-3"),
            ),
            "country",
            HTML(
                f'<hr class="my-3"><p class="text-muted small text-uppercase mb-3">{_("Propietario")}</p>'
            ),
            "owner_email",
        )

    def clean_owner_email(self):
        return self.cleaned_data["owner_email"].lower()


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "name",
            "logo",
            "tax_id",
            "email",
            "phone",
            "website",
            "address",
            "city",
            "state",
            "zip_code",
            "country",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "logo":
                field.required = True
                field.error_messages["required"] = _("Por favor, complete este campo.")
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            "name",
            HTML(
                f'<hr class="my-3"><p class="text-muted small text-uppercase mb-3">{_("Contacto")}</p>'
            ),
            Row(
                Column("tax_id", css_class="col-md-6"),
                Column("email", css_class="col-md-6"),
            ),
            Row(
                Column("phone", css_class="col-md-6"),
                Column("website", css_class="col-md-6"),
            ),
            HTML(
                f'<hr class="my-3"><p class="text-muted small text-uppercase mb-3">{_("Dirección")}</p>'
            ),
            "address",
            Row(
                Column("city", css_class="col-md-5"),
                Column("state", css_class="col-md-4"),
                Column("zip_code", css_class="col-md-3"),
            ),
            "country",
        )


class TeamForm(forms.ModelForm):
    modules = forms.ModelMultipleChoiceField(
        queryset=Module.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Acceso a módulos"),
        help_text=_("Dejar vacío para conceder acceso a todos los módulos."),
    )

    class Meta:
        model = Team
        fields = ["name", "description", "modules"]
        labels = {
            "name": _("Nombre"),
            "description": _("Descripción"),
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
            "description": forms.Textarea(attrs={"rows": 1, "class": "form-control form-control-sm"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "avatar", "signature"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("first_name", css_class="col-md-6"),
                Column("last_name", css_class="col-md-6"),
            ),
            Field("signature"),
        )
