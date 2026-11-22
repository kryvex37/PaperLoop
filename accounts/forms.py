from decimal import Decimal
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import EducationalInstitution, PaperListing, PUBLIC_REGISTRATION_ROLES, RecyclingProfile, User, UserRole, VerificationStatus


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

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.role = self.cleaned_data["role"]
        user.organization_name = self.cleaned_data["organization_name"].strip()
        user.contact_name = self.cleaned_data["contact_name"].strip()
        user.phone = self.cleaned_data["phone"].strip()
        user.verification_status = VerificationStatus.PENDING
        user.is_active = True
        if commit:
            user.save()
            if user.role == UserRole.EDUCATIONAL_INSTITUTION:
                EducationalInstitution.objects.create(user=user)
            elif user.role == UserRole.RECYCLING_PARTNER:
                RecyclingProfile.objects.create(user=user)
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

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            if user.role == UserRole.EDUCATIONAL_INSTITUTION:
                EducationalInstitution.objects.get_or_create(user=user)
            elif user.role == UserRole.RECYCLING_PARTNER:
                RecyclingProfile.objects.get_or_create(user=user)
        return user


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class RecyclingProfileForm(forms.ModelForm):
    organization_name = forms.CharField(max_length=180, label="Company / organization name", required=False)
    contact_name = forms.CharField(max_length=120, label="Primary contact", required=False)
    phone = forms.CharField(max_length=32, label="Contact phone", required=False)
    accepted_paper_types = forms.MultipleChoiceField(
        choices=PaperListing.PaperCategory.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Accepted paper categories",
    )
    service_area = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        label="Service area / operational locations",
        help_text="Specify cities, towns, or districts where you provide paper pickup.",
    )
    maximum_capacity = forms.DecimalField(
        min_value=0,
        required=False,
        label="Maximum processing / collection capacity",
        widget=forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
    )
    # Backwards-compatible alias used by existing monthly-capacity submissions.
    capacity_kg_per_month = forms.DecimalField(
        min_value=0, required=False, label="Monthly capacity (kg)",
        widget=forms.HiddenInput(),
    )
    capacity_unit = forms.ChoiceField(choices=RecyclingProfile.CapacityUnit.choices, required=False)
    capacity_period = forms.ChoiceField(choices=RecyclingProfile.CapacityPeriod.choices, required=False)
    current_allocated_load = forms.DecimalField(
        min_value=0, required=False, label="Currently allocated load",
        widget=forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
    )
    collection_available = forms.BooleanField(
        required=False,
        label="Accepting collection requests",
        help_text="Uncheck to pause incoming collection requests.",
    )
    latitude = forms.FloatField(required=False, min_value=-90, max_value=90,
                                 help_text="Optional decimal latitude for accurate pickup matching.")
    longitude = forms.FloatField(required=False, min_value=-180, max_value=180,
                                 help_text="Optional decimal longitude for accurate pickup matching.")

    class Meta:
        model = RecyclingProfile
        fields = (
            "accepted_paper_types",
            "service_area",
            "maximum_capacity",
            "capacity_kg_per_month",
            "current_allocated_load",
            "capacity_unit",
            "capacity_period",
            "collection_available",
            "latitude",
            "longitude",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and getattr(self.instance, "accepted_paper_types", None) is not None:
            self.initial["accepted_paper_types"] = self.instance.accepted_paper_types or []
        if self.instance and self.instance.pk:
            self.initial.setdefault("organization_name", self.instance.user.organization_name)
            self.initial.setdefault("contact_name", self.instance.user.contact_name)
            self.initial.setdefault("phone", self.instance.user.phone)
            self.initial.setdefault("maximum_capacity", self.instance.maximum_capacity if self.instance.maximum_capacity is not None else self.instance.capacity_kg_per_month)
            self.initial.setdefault("capacity_kg_per_month", self.instance.capacity_kg_per_month)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                pass
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean_accepted_paper_types(self):
        data = self.cleaned_data.get("accepted_paper_types") or []
        valid_slugs = {choice[0] for choice in PaperListing.PaperCategory.choices}
        return [slug for slug in data if slug in valid_slugs]

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("capacity_unit"):
            cleaned["capacity_unit"] = self.instance.capacity_unit or RecyclingProfile.CapacityUnit.KILOGRAM
        if not cleaned.get("capacity_period"):
            cleaned["capacity_period"] = self.instance.capacity_period or RecyclingProfile.CapacityPeriod.MONTH
        if cleaned.get("maximum_capacity") is None:
            cleaned["maximum_capacity"] = (
                cleaned.get("capacity_kg_per_month")
                if cleaned.get("capacity_kg_per_month") is not None
                else self.instance.maximum_capacity or self.instance.capacity_kg_per_month
            )
        maximum = cleaned.get("maximum_capacity")
        allocated = cleaned.get("current_allocated_load") or 0
        if maximum is not None and allocated > maximum:
            self.add_error("current_allocated_load", "Allocated load cannot exceed maximum capacity.")
        if not (cleaned.get("organization_name") or getattr(getattr(self.instance, "user", None), "organization_name", "")).strip():
            self.add_error("organization_name", "Enter your company or organization name.")
        return cleaned

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.accepted_paper_types = self.cleaned_data.get("accepted_paper_types", [])
        profile.current_allocated_load = self.cleaned_data.get("current_allocated_load") or 0
        if profile.capacity_unit == RecyclingProfile.CapacityUnit.KILOGRAM and profile.capacity_period == RecyclingProfile.CapacityPeriod.MONTH:
            profile.capacity_kg_per_month = profile.maximum_capacity
        else:
            profile.capacity_kg_per_month = None
        if commit:
            profile.save()
            user = profile.user
            user.organization_name = (self.cleaned_data.get("organization_name") or user.organization_name).strip()
            user.contact_name = (self.cleaned_data.get("contact_name") or user.contact_name).strip()
            user.phone = (self.cleaned_data.get("phone") or user.phone).strip()
            user.save(update_fields=("organization_name", "contact_name", "phone"))
        return profile


class EducationalInstitutionProfileForm(forms.ModelForm):
    latitude = forms.FloatField(required=False, min_value=-90, max_value=90)
    longitude = forms.FloatField(required=False, min_value=-180, max_value=180)
    student_count = forms.IntegerField(min_value=1, required=True)

    class Meta:
        model = EducationalInstitution
        fields = ("institution_type", "address", "city", "country", "student_count", "latitude", "longitude")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student_count"].help_text = "Approximate enrolled students; used only for paper-volume forecasts."
        self.fields["latitude"].help_text = "Decimal latitude for pickup clustering."
        self.fields["longitude"].help_text = "Decimal longitude for pickup clustering."
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class PartnerDirectoryFilterForm(forms.Form):
    search = forms.CharField(required=False, max_length=100, label="Partner name")
    paper_type = forms.ChoiceField(
        required=False,
        choices=[("", "Any paper category"), *PaperListing.PaperCategory.choices],
        label="Accepted paper category",
    )
    service_area = forms.CharField(required=False, max_length=100, label="Service area")
    quantity_kg = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        label="Minimum available capacity (kg)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"


class CollectionAcceptForm(forms.Form):
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control", "placeholder": "Optional acceptance notes (e.g. preparation or logistics instructions)..."}),
        required=False,
        label="Acceptance notes",
    )


class CollectionRejectForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control", "placeholder": "State the reason for rejecting this collection request..."}),
        required=True,
        label="Rejection reason",
    )


class CollectionScheduleForm(forms.Form):
    scheduled_for = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
        required=True,
        label="Scheduled pickup date and time",
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control", "placeholder": "Optional instructions for pickup crew or institution..."}),
        required=False,
        label="Pickup notes",
    )

    def clean_scheduled_for(self):
        scheduled_for = self.cleaned_data.get("scheduled_for")
        if scheduled_for and scheduled_for < timezone.now():
            raise forms.ValidationError("Scheduled pickup time cannot be in the past.")
        return scheduled_for


class CollectionCompleteForm(forms.Form):
    final_collected_quantity_kg = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
        required=True,
        label="Final collected quantity (kg)",
        widget=forms.NumberInput(attrs={"step": "0.01", "class": "form-control", "placeholder": "Enter measured weight in kilograms"}),
        help_text="Enter the final verified weight of paper waste collected from the institution.",
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "class": "form-control", "placeholder": "Optional notes regarding paper condition, weighing, or receipt..."}),
        required=False,
        label="Completion notes",
    )


