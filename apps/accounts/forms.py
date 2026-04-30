from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, HTML, Row, Column
from allauth.account.forms import SignupForm, ChangePasswordForm
from apps.core.models import Module
from .models import User, Organization, Membership, Team

_PASSWORD_HELP = "Use 8 or more characters with a mix of letters, numbers & symbols."


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
        label="Email address",
        widget=forms.EmailInput(attrs={"placeholder": "colleague@example.com"}),
    )
    role = forms.ChoiceField(choices=Membership.Role.choices, initial=Membership.Role.MEMBER)

    def clean_email(self):
        return self.cleaned_data["email"].lower()


class CreateOrganizationForm(forms.Form):
    name = forms.CharField(
        max_length=255,
        label="Organization name",
        widget=forms.TextInput(attrs={"placeholder": "Acme Corp", "autofocus": True}),
    )


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "name", "logo",
            "tax_id", "email", "phone", "website",
            "address", "city", "state", "zip_code", "country",
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
            HTML('<hr class="my-3"><p class="text-muted small text-uppercase mb-3">Contact</p>'),
            Row(
                Column("tax_id", css_class="col-md-6"),
                Column("email", css_class="col-md-6"),
            ),
            Row(
                Column("phone", css_class="col-md-6"),
                Column("website", css_class="col-md-6"),
            ),
            HTML('<hr class="my-3"><p class="text-muted small text-uppercase mb-3">Address</p>'),
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
        help_text="Leave empty to grant access to all modules.",
    )

    class Meta:
        model = Team
        fields = ["name", "description", "modules"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "avatar"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("first_name", css_class="col-md-6"),
                Column("last_name", css_class="col-md-6"),
            ),
        )
