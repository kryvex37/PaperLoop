from django import forms
from django.core.exceptions import ValidationError

from .models import PaperListing


class PaperListingForm(forms.ModelForm):
    class Meta:
        model = PaperListing
        fields = (
            "paper_type",
            "category_details",
            "quantity_kg",
            "description",
            "pickup_address",
            "pickup_city",
            "pickup_country",
            "available_from",
            "available_until",
            "photo",
        )
        labels = {
            "paper_type": "Paper category",
            "category_details": "Additional paper details",
            "quantity_kg": "Estimated quantity (kg)",
            "description": "Notes",
            "pickup_address": "Pickup address",
            "pickup_city": "City or town",
            "pickup_country": "Country",
            "available_from": "Preferred collection period starts",
            "available_until": "Preferred collection period ends",
            "photo": "Photo (optional)",
        }
        help_texts = {
            "quantity_kg": "Enter your best estimate in kilograms. It can be updated before a collection is arranged.",
            "available_from": "Leave blank if you do not have a preferred start date yet.",
            "available_until": "Leave blank if you do not have a preferred end date yet.",
            "photo": "Upload one supporting image, up to 5 MB. Images are visible only to your institution account.",
        }
        widgets = {
            "quantity_kg": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "pickup_address": forms.Textarea(attrs={"rows": 2}),
            "available_from": forms.DateInput(attrs={"type": "date"}),
            "available_until": forms.DateInput(attrs={"type": "date"}),
            "photo": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
        self.fields["pickup_city"].required = True
        self.fields["pickup_country"].required = True
        if not (self.instance and self.instance.pk and self.instance.pickup_country):
            self.initial.setdefault("pickup_country", "Bangladesh")
        self.fields["category_details"].required = False
        self.fields["category_details"].help_text = "For example, describe the paper type when you select Other."

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo and getattr(photo, "size", 0) > 5 * 1024 * 1024:
            raise ValidationError("Choose an image that is 5 MB or smaller.")
        return photo

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("available_from")
        end = cleaned_data.get("available_until")
        if start and end and end < start:
            self.add_error("available_until", "The collection period end must be on or after its start.")
        if cleaned_data.get("paper_type") == PaperListing.PaperCategory.OTHER and not cleaned_data.get("category_details", "").strip():
            self.add_error("category_details", "Describe the paper category when you select Other.")

        pickup_address = (cleaned_data.get("pickup_address") or "").strip()
        pickup_city = (cleaned_data.get("pickup_city") or "").strip()
        pickup_country = (cleaned_data.get("pickup_country") or "").strip() or "Bangladesh"
        cleaned_data["pickup_country"] = pickup_country
        if not pickup_address or not pickup_city:
            raise ValidationError(
                "Please select a campus or street location using the Bangladesh Location Finder (search, Division → District → Upazila, or map pin)."
            )
        return cleaned_data
