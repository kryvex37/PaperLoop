from io import BytesIO
from tempfile import TemporaryDirectory
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.listing_forms import PaperListingForm
from accounts.models import (
    EducationalInstitution,
    PaperListing,
    RecyclingProfile,
    UserRole,
    VerificationStatus,
)


User = get_user_model()


class RegistrationIntegrationTests(TestCase):
    def registration_data(self, role, email):
        return {
            "role": role,
            "organization_name": "Integration Test Organization",
            "contact_name": "Test Contact",
            "email": email,
            "phone": "+8801700000000",
            "password1": "R3cycling!PaperLoop-Test",
            "password2": "R3cycling!PaperLoop-Test",
        }

    def test_registration_creates_pending_account_and_matching_profile_for_each_role(self):
        cases = (
            (UserRole.EDUCATIONAL_INSTITUTION, "registration-institution@example.test", EducationalInstitution),
            (UserRole.RECYCLING_PARTNER, "registration-partner@example.test", RecyclingProfile),
        )
        for role, email, profile_model in cases:
            with self.subTest(role=role):
                response = self.client.post(
                    reverse("accounts:register"), self.registration_data(role, email)
                )
                self.assertRedirects(response, reverse("accounts:login"))
                user = User.objects.get(email=email)
                self.assertEqual(user.verification_status, VerificationStatus.PENDING)
                self.assertTrue(user.check_password("R3cycling!PaperLoop-Test"))
                self.assertTrue(profile_model.objects.filter(user=user).exists())

    def test_duplicate_registration_is_rejected_without_creating_another_account(self):
        User.objects.create_user(
            email="duplicate@example.test", password="R3cycling!PaperLoop-Test",
            role=UserRole.EDUCATIONAL_INSTITUTION,
        )
        response = self.client.post(
            reverse("accounts:register"),
            self.registration_data(UserRole.EDUCATIONAL_INSTITUTION, "DUPLICATE@example.test"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.filter(email__iexact="duplicate@example.test").count(), 1)


class AdminVerificationIntegrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="step9-admin@example.test", password="R3cycling!PaperLoop-Test"
        )
        self.client = Client()
        self.client.force_login(self.admin)
        self.changelist_url = reverse("admin:accounts_user_changelist")

    def run_action(self, action, user):
        return self.client.post(self.changelist_url, {
            "action": action,
            "_selected_action": [str(user.pk)],
        })

    def test_admin_can_verify_reject_and_suspend_organization_accounts(self):
        verified = User.objects.create_user(
            email="verify-me@example.test", password="R3cycling!PaperLoop-Test",
            role=UserRole.EDUCATIONAL_INSTITUTION,
        )
        rejected = User.objects.create_user(
            email="reject-me@example.test", password="R3cycling!PaperLoop-Test",
            role=UserRole.RECYCLING_PARTNER,
        )
        suspended = User.objects.create_user(
            email="suspend-me@example.test", password="R3cycling!PaperLoop-Test",
            role=UserRole.EDUCATIONAL_INSTITUTION,
        )

        response = self.run_action("verify_organizations", verified)
        self.assertEqual(response.status_code, 302)
        verified.refresh_from_db()
        self.assertEqual(verified.verification_status, VerificationStatus.VERIFIED)
        self.assertEqual(verified.verified_by, self.admin)
        self.assertIsNotNone(verified.verified_at)

        response = self.run_action("reject_organizations", rejected)
        self.assertEqual(response.status_code, 302)
        rejected.refresh_from_db()
        self.assertEqual(rejected.verification_status, VerificationStatus.REJECTED)

        response = self.run_action("suspend_organizations", suspended)
        self.assertEqual(response.status_code, 302)
        suspended.refresh_from_db()
        self.assertEqual(suspended.verification_status, VerificationStatus.SUSPENDED)
        self.assertFalse(suspended.is_active)


class InstitutionListingIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="step9-institution@example.test", password="R3cycling!PaperLoop-Test",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Step 9 Institute",
        )
        self.institution = EducationalInstitution.objects.create(user=self.user)
        self.client = Client()
        self.client.force_login(self.user)

    def listing_data(self, **overrides):
        data = {
            "paper_type": PaperListing.PaperCategory.OFFICE,
            "category_details": "",
            "quantity_kg": "125.50",
            "description": "Sorted paper for pickup",
            "pickup_address": "12 College Road",
            "pickup_city": "Dhaka",
            "pickup_country": "Bangladesh",
            "available_from": (timezone.localdate() + timedelta(days=1)).isoformat(),
            "available_until": (timezone.localdate() + timedelta(days=7)).isoformat(),
        }
        data.update(overrides)
        return data

    def test_institution_can_create_edit_and_withdraw_its_listing(self):
        response = self.client.post(reverse("accounts:listing_create"), self.listing_data())
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))
        listing = PaperListing.objects.get(institution=self.institution)
        self.assertEqual(listing.status, PaperListing.Status.AVAILABLE)
        self.assertEqual(listing.quantity_kg, Decimal("125.50"))

        response = self.client.post(
            reverse("accounts:listing_edit", args=[listing.pk]),
            self.listing_data(quantity_kg="200.00"),
        )
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))
        listing.refresh_from_db()
        self.assertEqual(listing.quantity_kg, Decimal("200.00"))

        response = self.client.post(reverse("accounts:listing_cancel", args=[listing.pk]))
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))
        listing.refresh_from_db()
        self.assertEqual(listing.status, PaperListing.Status.CANCELLED)

    def test_other_category_needs_details_and_dates_must_be_ordered(self):
        reversed_start = timezone.localdate() + timedelta(days=10)
        reversed_end = timezone.localdate() + timedelta(days=2)
        form = PaperListingForm(data=self.listing_data(
            paper_type=PaperListing.PaperCategory.OTHER,
            category_details="",
            available_from=reversed_start.isoformat(),
            available_until=reversed_end.isoformat(),
        ))
        self.assertFalse(form.is_valid())
        self.assertIn("category_details", form.errors)
        self.assertIn("available_until", form.errors)


class MediaStorageIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="step9-photo-owner@example.test", password="R3cycling!PaperLoop-Test",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Photo Owner Institute",
        )
        self.institution = EducationalInstitution.objects.create(user=self.user)

    @staticmethod
    def make_image_upload():
        buffer = BytesIO()
        Image.new("RGB", (3, 3), color=(20, 120, 40)).save(buffer, format="PNG")
        return SimpleUploadedFile("paper-evidence.png", buffer.getvalue(), content_type="image/png")

    def test_photo_is_stored_and_served_only_to_owning_institution(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            client = Client()
            client.force_login(self.user)
            response = client.post(reverse("accounts:listing_create"), {
                "paper_type": PaperListing.PaperCategory.OFFICE,
                "category_details": "",
                "quantity_kg": "55.00",
                "description": "Photo storage integration fixture",
                "pickup_address": "12 College Road",
                "pickup_city": "Dhaka",
                "pickup_country": "Bangladesh",
                "available_from": "",
                "available_until": "",
                "photo": self.make_image_upload(),
            })
            self.assertRedirects(response, reverse("accounts:institution_dashboard"))
            listing = PaperListing.objects.get(institution=self.institution)
            self.assertTrue(listing.photo.storage.exists(listing.photo.name))

            photo_url = reverse("accounts:listing_photo", args=[listing.pk])
            other_user = User.objects.create_user(
                email="step9-photo-other@example.test", password="R3cycling!PaperLoop-Test",
                role=UserRole.EDUCATIONAL_INSTITUTION,
                verification_status=VerificationStatus.VERIFIED,
                organization_name="Other Institute",
            )
            other_client = Client()
            other_client.force_login(other_user)
            self.assertEqual(other_client.get(photo_url).status_code, 404)

            anonymous_client = Client()
            self.assertEqual(anonymous_client.get(photo_url).status_code, 302)

            owner_response = client.get(photo_url)
            try:
                self.assertEqual(owner_response.status_code, 200)
                self.assertEqual(owner_response["Content-Type"], "image/png")
                cache_control = owner_response["Cache-Control"]
                self.assertIn("private", cache_control)
                self.assertIn("no-store", cache_control)
            finally:
                owner_response.close()
