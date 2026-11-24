from datetime import date
from decimal import Decimal
from io import BytesIO
import tempfile

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse

from accounts.models import (
    Collection,
    EducationalInstitution,
    PaperListing,
    RecyclingProfile,
    UserRole,
    VerificationStatus,
)
from accounts.listing_forms import PaperListingForm

User = get_user_model()


class InstitutionListingWorkflowFR03FR05Tests(TransactionTestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.settings_override.enable()
        self.client = Client()
        self.institution_user = User.objects.create_user(
            email="listing-school@example.test",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Paper Loop School",
        )
        self.institution = EducationalInstitution.objects.create(
            user=self.institution_user,
            city="Dhaka",
            country="Bangladesh",
        )
        self.other_user = User.objects.create_user(
            email="other-school@example.test",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Other School",
        )
        self.other_institution = EducationalInstitution.objects.create(user=self.other_user)
        self.partner_user = User.objects.create_user(
            email="listing-partner@example.test",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Paper Recycler",
        )
        self.partner = RecyclingProfile.objects.create(user=self.partner_user)
        self.client.force_login(self.institution_user)

    def tearDown(self):
        self.settings_override.disable()
        self.media_dir.cleanup()

    def listing_data(self, **overrides):
        data = {
            "paper_type": PaperListing.PaperCategory.OFFICE,
            "category_details": "",
            "quantity_kg": "425.50",
            "description": "Sorted paper in boxes",
            "pickup_address": "12 Green Road",
            "pickup_city": "Dhaka",
            "pickup_country": "Bangladesh",
            "available_from": "",
            "available_until": "",
        }
        data.update(overrides)
        return data

    def make_png(self):
        buffer = BytesIO()
        Image.new("RGB", (2, 2), color="green").save(buffer, format="PNG")
        return SimpleUploadedFile("paper.png", buffer.getvalue(), content_type="image/png")

    def make_listing(self, **overrides):
        values = {
            "institution": self.institution,
            "paper_type": PaperListing.PaperCategory.OFFICE,
            "quantity_kg": Decimal("425.50"),
            "pickup_address": "12 Green Road",
            "pickup_city": "Dhaka",
            "pickup_country": "Bangladesh",
            "status": PaperListing.Status.AVAILABLE,
        }
        values.update(overrides)
        return PaperListing.objects.create(**values)

    def test_create_publish_and_save_draft(self):
        response = self.client.post(
            reverse("accounts:listing_create"),
            self.listing_data(listing_action="publish"),
        )
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))
        published = PaperListing.objects.get(institution=self.institution)
        self.assertEqual(published.status, PaperListing.Status.AVAILABLE)
        self.assertEqual(published.quantity_kg, Decimal("425.50"))
        self.assertEqual(published.pickup_country, "Bangladesh")

        draft_response = self.client.post(
            reverse("accounts:listing_create"),
            self.listing_data(
                listing_action="draft",
                paper_type=PaperListing.PaperCategory.BOOKS,
            ),
        )
        self.assertRedirects(draft_response, reverse("accounts:institution_dashboard"))
        draft = PaperListing.objects.get(paper_type=PaperListing.PaperCategory.BOOKS)
        self.assertEqual(draft.status, PaperListing.Status.DRAFT)
        dashboard = self.client.get(reverse("accounts:institution_dashboard"))
        self.assertContains(dashboard, "Drafts")
        self.assertContains(dashboard, reverse("accounts:listing_edit", args=[draft.pk]))

    def test_draft_can_be_edited_and_published(self):
        draft = self.make_listing(status=PaperListing.Status.DRAFT)
        response = self.client.post(
            reverse("accounts:listing_edit", args=[draft.pk]),
            self.listing_data(listing_action="publish", quantity_kg="600"),
        )
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))
        draft.refresh_from_db()
        self.assertEqual(draft.status, PaperListing.Status.AVAILABLE)
        self.assertEqual(draft.quantity_kg, Decimal("600"))

    def test_other_category_requires_details_and_quantity_must_be_positive(self):
        invalid_other = self.client.post(
            reverse("accounts:listing_create"),
            self.listing_data(paper_type=PaperListing.PaperCategory.OTHER),
        )
        self.assertEqual(invalid_other.status_code, 200)
        self.assertContains(invalid_other, "Describe the paper category")
        self.assertFalse(PaperListing.objects.exists())

        invalid_quantity = self.client.post(
            reverse("accounts:listing_create"),
            self.listing_data(quantity_kg="0"),
        )
        self.assertEqual(invalid_quantity.status_code, 200)
        self.assertFalse(PaperListing.objects.exists())

    def test_collection_dates_must_be_ordered_when_both_are_set(self):
        response = self.client.post(
            reverse("accounts:listing_create"),
            self.listing_data(available_from="2026-06-20", available_until="2026-06-19"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The collection period end must be on or after its start.")
        self.assertFalse(PaperListing.objects.exists())

    def test_location_fields_are_required(self):
        response = self.client.post(
            reverse("accounts:listing_create"),
            self.listing_data(pickup_city="", pickup_country=""),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertFalse(PaperListing.objects.exists())

    def test_photo_upload_is_owner_only_and_served_as_private_image(self):
        response = self.client.post(
            reverse("accounts:listing_create"),
            {**self.listing_data(), "photo": self.make_png()},
        )
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))
        listing = PaperListing.objects.get(institution=self.institution)
        photo_url = reverse("accounts:listing_photo", args=[listing.pk])

        photo_response = self.client.get(photo_url)
        self.assertEqual(photo_response.status_code, 200)
        self.assertEqual(photo_response["Content-Type"], "image/png")
        self.assertIn("private", photo_response["Cache-Control"])
        self.assertIn("no-store", photo_response["Cache-Control"])
        self.assertEqual(photo_response["X-Content-Type-Options"], "nosniff")
        photo_response.close()

        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(photo_url).status_code, 404)
        self.client.force_login(self.partner_user)
        self.assertEqual(self.client.get(photo_url).status_code, 403)

    def test_photo_limit_accepts_five_megabytes_and_rejects_larger_files(self):
        form = PaperListingForm()
        exact_limit = SimpleUploadedFile("exact.png", b"x" * (5 * 1024 * 1024))
        form.cleaned_data = {"photo": exact_limit}
        self.assertIs(form.clean_photo(), exact_limit)

        oversized = SimpleUploadedFile("large.png", b"x" * (5 * 1024 * 1024 + 1))
        form.cleaned_data = {"photo": oversized}
        with self.assertRaises(ValidationError):
            form.clean_photo()

    def test_unverified_institution_cannot_manage_listings(self):
        pending_user = User.objects.create_user(
            email="pending-listing-school@example.test",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.PENDING,
            organization_name="Pending School",
        )
        EducationalInstitution.objects.create(user=pending_user)
        self.client.force_login(pending_user)

        self.assertEqual(self.client.get(reverse("accounts:institution_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:listing_create")).status_code, 403)

    def test_wrong_institution_cannot_edit_or_withdraw_listing(self):
        listing = self.make_listing()
        self.client.force_login(self.other_user)
        self.assertEqual(
            self.client.get(reverse("accounts:listing_edit", args=[listing.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("accounts:listing_cancel", args=[listing.pk])).status_code,
            404,
        )
        listing.refresh_from_db()
        self.assertEqual(listing.status, PaperListing.Status.AVAILABLE)

    def test_rejected_non_cancelled_collection_locks_edit_and_withdrawal_but_allows_reselection(self):
        listing = self.make_listing()
        Collection.objects.create(
            listing=listing,
            partner=self.partner,
            status=Collection.Status.REJECTED,
        )

        edit_response = self.client.get(reverse("accounts:listing_edit", args=[listing.pk]))
        self.assertRedirects(edit_response, reverse("accounts:institution_dashboard"))
        edit_post = self.client.post(
            reverse("accounts:listing_edit", args=[listing.pk]),
            self.listing_data(listing_action="save", quantity_kg="999"),
        )
        self.assertRedirects(edit_post, reverse("accounts:institution_dashboard"))
        withdraw_response = self.client.post(reverse("accounts:listing_cancel", args=[listing.pk]))
        self.assertRedirects(withdraw_response, reverse("accounts:institution_dashboard"))
        listing.refresh_from_db()
        self.assertEqual(listing.status, PaperListing.Status.AVAILABLE)

        dashboard = self.client.get(reverse("accounts:institution_dashboard"))
        self.assertContains(dashboard, "Editing and withdrawal are locked after collection activity.")
        self.assertContains(dashboard, reverse("accounts:listing_recommendations", args=[listing.pk]))
        self.assertNotContains(dashboard, reverse("accounts:listing_edit", args=[listing.pk]))

    def test_cancelled_collection_does_not_lock_edit_or_withdrawal(self):
        listing = self.make_listing()
        Collection.objects.create(
            listing=listing,
            partner=self.partner,
            status=Collection.Status.CANCELLED,
        )

        edit_response = self.client.post(
            reverse("accounts:listing_edit", args=[listing.pk]),
            self.listing_data(listing_action="save", quantity_kg="500"),
        )
        self.assertRedirects(edit_response, reverse("accounts:institution_dashboard"))
        listing.refresh_from_db()
        self.assertEqual(listing.quantity_kg, Decimal("500"))

        withdraw_response = self.client.post(reverse("accounts:listing_cancel", args=[listing.pk]))
        self.assertRedirects(withdraw_response, reverse("accounts:institution_dashboard"))
        listing.refresh_from_db()
        self.assertEqual(listing.status, PaperListing.Status.CANCELLED)

    def test_collection_request_locks_listing_edits(self):
        listing = self.make_listing(status=PaperListing.Status.RESERVED)
        Collection.objects.create(
            listing=listing,
            partner=self.partner,
            status=Collection.Status.REQUESTED,
        )

        response = self.client.post(
            reverse("accounts:listing_edit", args=[listing.pk]),
            self.listing_data(listing_action="save", quantity_kg="900"),
        )
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))
        listing.refresh_from_db()
        self.assertEqual(listing.quantity_kg, Decimal("425.50"))

    def test_withdrawal_is_soft_and_listing_stays_on_dashboard(self):
        listing = self.make_listing()
        response = self.client.post(reverse("accounts:listing_cancel", args=[listing.pk]))
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))
        listing.refresh_from_db()
        self.assertEqual(listing.status, PaperListing.Status.CANCELLED)
        self.assertTrue(PaperListing.objects.filter(pk=listing.pk).exists())
        self.assertContains(self.client.get(reverse("accounts:institution_dashboard")), "Withdrawn")

    def test_dashboard_shows_listing_table_and_create_action(self):
        listing = self.make_listing(available_from=date(2026, 6, 1), available_until=date(2026, 6, 7))
        response = self.client.get(reverse("accounts:institution_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your paper listings")
        self.assertContains(response, "425.50 kg")
        self.assertContains(response, "Dhaka, Bangladesh")
        self.assertContains(response, "Find Recycler")
        self.assertContains(response, reverse("accounts:listing_edit", args=[listing.pk]))
        self.assertContains(response, reverse("accounts:listing_create"))
