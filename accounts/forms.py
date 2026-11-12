from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError

from .models import PUBLIC_REGISTRATION_ROLES, User, UserRole


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label="Work email", max_length=254)
    role = forms.ChoiceField(
        label="I am registering as",
        choices=[(role.value, role.label) for role in PUBLIC_REGISTRATION_ROLES],
    )
    organization_name = forms.CharField(label="Organization name", max_length=180)
    contact_name = forms.CharField(label="Contact person", max_length=120)
    phone = forms.CharField(label="Phone number", max_length=32)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "role",
            "organization_name",
            "contact_name",
            "email",
            "phone",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = css_class

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean_role(self):
        role = self.cleaned_data["role"]
        allowed_roles = {choice.value for choice in PUBLIC_REGISTRATION_ROLES}
        if role not in allowed_roles:
            raise ValidationError("Choose a valid organization type.")
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.role = self.cleaned_data["role"]
        user.organization_name = self.cleaned_data["organization_name"].strip()
        user.contact_name = self.cleaned_data["contact_name"].strip()
        user.phone = self.cleaned_data["phone"].strip()
        if commit:
            user.save()
        return user


class AdminUserCreationForm(UserCreationForm):
    """Django admin account form compatible with PaperLoop's email user model."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "organization_name", "contact_name", "phone", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = css_class


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
