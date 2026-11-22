from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import (
    Collection,
    EducationalInstitution,
    PaperListing,
    RecyclingProfile,
    Transaction,
    UserRole,
    VerificationStatus,
)

User = get_user_model()


class CollectionWorkflowFR09FR10Tests(TestCase):
    """
    Comprehensive tests for:
    - FR-09: Collection Request submission, accept/reject, pickup scheduling, and status updates.
    - FR-10: Collection quantity tracking (estimated vs final collected quantity).
    """

    def setUp(self):
        self.client = Client()

        # Institution user
        self.inst_user = User.objects.create_user(
            email="school_fr09@example.test",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Green Valley Academy",
            is_active=True,
        )
        self.institution = EducationalInstitution.objects.create(
            user=self.inst_user,
            city="Dhaka",
        )

        # Recycling Partner user
        self.partner_user = User.objects.create_user(
            email="recycler_fr09@example.test",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="EcoClean Paper Recyclers",
            is_active=True,
        )
        self.partner_profile = RecyclingProfile.objects.create(
            user=self.partner_user,
            accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Dhaka, Gazipur",
            capacity_kg_per_month=Decimal("10000.00"),
            collection_available=True,
        )

        # Third-party institution user for permission tests
        self.other_user = User.objects.create_user(
            email="other_inst@example.test",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Other College",
            is_active=True,
        )
        self.other_institution = EducationalInstitution.objects.create(
            user=self.other_user,
            city="Chittagong",
        )

        # Paper Listing
        self.listing = PaperListing.objects.create(
            institution=self.institution,
            paper_type=PaperListing.PaperCategory.OFFICE,
            quantity_kg=Decimal("650.00"),
            pickup_address="Road 11, Banani",
            pickup_city="Dhaka",
            status=PaperListing.Status.AVAILABLE,
        )

    def test_request_submission_records_estimated_quantity(self):
        """FR-09 & FR-10: Submitting request records estimated quantity and reserves listing."""
        self.client.force_login(self.inst_user)
        response = self.client.post(
            reverse("accounts:select_recommended_partner", args=[self.listing.pk]),
            {"partner_id": self.partner_profile.pk, "notes": "Pickup from rear loading dock."},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, PaperListing.Status.RESERVED)

        collection = self.listing.collections.first()
        self.assertIsNotNone(collection)
        self.assertEqual(collection.partner, self.partner_profile)
        self.assertEqual(collection.status, Collection.Status.REQUESTED)
        self.assertEqual(collection.estimated_quantity_kg, Decimal("650.00"))
        self.assertEqual(collection.estimated_quantity, Decimal("650.00"))
        self.assertIsNone(collection.final_collected_quantity_kg)
        self.assertIn("rear loading dock", collection.notes)

    def test_partner_can_accept_collection_request(self):
        """FR-09: Partner can accept incoming collection request."""
        collection = Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.REQUESTED,
            estimated_quantity_kg=self.listing.quantity_kg,
        )
        self.listing.status = PaperListing.Status.RESERVED
        self.listing.save()

        self.client.force_login(self.partner_user)
        response = self.client.post(
            reverse("accounts:partner_accept_collection", args=[collection.pk]),
            {"notes": "Will assign truck #4"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        collection.refresh_from_db()
        self.assertEqual(collection.status, Collection.Status.ACCEPTED)
        self.assertIn("Will assign truck #4", collection.notes)

    def test_partner_can_reject_collection_request_and_release_listing(self):
        """FR-09: Rejecting request sets status to REJECTED and releases listing to AVAILABLE."""
        collection = Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.REQUESTED,
            estimated_quantity_kg=self.listing.quantity_kg,
        )
        self.listing.status = PaperListing.Status.RESERVED
        self.listing.save()

        self.client.force_login(self.partner_user)
        response = self.client.post(
            reverse("accounts:partner_reject_collection", args=[collection.pk]),
            {"rejection_reason": "Truck currently undergoing maintenance."},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        collection.refresh_from_db()
        self.assertEqual(collection.status, Collection.Status.REJECTED)
        self.assertEqual(collection.rejection_reason, "Truck currently undergoing maintenance.")

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, PaperListing.Status.AVAILABLE)

    def test_reject_requires_reason(self):
        """FR-09: Rejecting without reason fails validation."""
        collection = Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.REQUESTED,
            estimated_quantity_kg=self.listing.quantity_kg,
        )

        self.client.force_login(self.partner_user)
        response = self.client.post(
            reverse("accounts:partner_reject_collection", args=[collection.pk]),
            {"rejection_reason": ""},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        collection.refresh_from_db()
        self.assertEqual(collection.status, Collection.Status.REQUESTED)

    def test_partner_can_schedule_pickup(self):
        """FR-09: Partner can schedule pickup date and time."""
        collection = Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.ACCEPTED,
            estimated_quantity_kg=self.listing.quantity_kg,
        )
        pickup_time = timezone.now() + timedelta(days=2, hours=3)
        formatted_time = pickup_time.strftime("%Y-%m-%dT%H:%M")

        self.client.force_login(self.partner_user)
        response = self.client.post(
            reverse("accounts:partner_schedule_collection", args=[collection.pk]),
            {"scheduled_for": formatted_time, "notes": "Driver: Kabir (01700000000)"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        collection.refresh_from_db()
        self.assertEqual(collection.status, Collection.Status.SCHEDULED)
        self.assertIsNotNone(collection.scheduled_for)
        self.assertIn("Driver: Kabir", collection.notes)

    def test_scheduling_in_past_fails(self):
        """FR-09: Scheduling in the past is rejected."""
        collection = Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.ACCEPTED,
            estimated_quantity_kg=self.listing.quantity_kg,
        )
        past_time = timezone.now() - timedelta(days=1)
        formatted_time = past_time.strftime("%Y-%m-%dT%H:%M")

        self.client.force_login(self.partner_user)
        response = self.client.post(
            reverse("accounts:partner_schedule_collection", args=[collection.pk]),
            {"scheduled_for": formatted_time},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        collection.refresh_from_db()
        self.assertEqual(collection.status, Collection.Status.ACCEPTED)

    def test_complete_collection_records_final_quantity_and_creates_transaction(self):
        """FR-09 & FR-10: Completing collection records final quantity, updates listing to COMPLETED, and creates Transaction."""
        collection = Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.SCHEDULED,
            estimated_quantity_kg=Decimal("650.00"),
            scheduled_for=timezone.now() + timedelta(days=1),
        )
        self.listing.status = PaperListing.Status.RESERVED
        self.listing.save()

        self.client.force_login(self.partner_user)
        response = self.client.post(
            reverse("accounts:partner_complete_collection", args=[collection.pk]),
            {
                "final_collected_quantity_kg": "632.75",
                "notes": "Weighed on digital platform scale; good condition.",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        collection.refresh_from_db()
        self.assertEqual(collection.status, Collection.Status.COLLECTED)
        self.assertEqual(collection.final_collected_quantity_kg, Decimal("632.75"))
        self.assertEqual(collection.estimated_quantity, Decimal("650.00"))
        self.assertIsNotNone(collection.collected_at)
        self.assertIn("digital platform scale", collection.notes)

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, PaperListing.Status.COMPLETED)

        # Check Transaction record creation
        txn = Transaction.objects.filter(collection=collection).first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.quantity_kg, Decimal("632.75"))
        self.assertTrue(txn.reference.startswith("TXN-"))

    def test_final_quantity_must_be_positive(self):
        """FR-10: Final quantity must be greater than zero."""
        collection = Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.SCHEDULED,
            estimated_quantity_kg=Decimal("650.00"),
        )

        self.client.force_login(self.partner_user)
        response = self.client.post(
            reverse("accounts:partner_complete_collection", args=[collection.pk]),
            {"final_collected_quantity_kg": "0.00"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        collection.refresh_from_db()
        self.assertEqual(collection.status, Collection.Status.SCHEDULED)
        self.assertIsNone(collection.final_collected_quantity_kg)

    def test_institution_can_cancel_pending_request(self):
        """FR-09: Institution can cancel request while in REQUESTED status."""
        collection = Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.REQUESTED,
            estimated_quantity_kg=self.listing.quantity_kg,
        )
        self.listing.status = PaperListing.Status.RESERVED
        self.listing.save()

        self.client.force_login(self.inst_user)
        response = self.client.post(
            reverse("accounts:institution_cancel_collection", args=[collection.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        collection.refresh_from_db()
        self.assertEqual(collection.status, Collection.Status.CANCELLED)

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, PaperListing.Status.AVAILABLE)

    def test_institution_cannot_cancel_accepted_collection(self):
        """FR-09: Institution cannot cancel after partner has accepted."""
        collection = Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.ACCEPTED,
            estimated_quantity_kg=self.listing.quantity_kg,
        )

        self.client.force_login(self.inst_user)
        response = self.client.post(
            reverse("accounts:institution_cancel_collection", args=[collection.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        collection.refresh_from_db()
        self.assertEqual(collection.status, Collection.Status.ACCEPTED)

    def test_collection_detail_access_permissions(self):
        """Only participating institution, assigned partner, or staff can access detail page."""
        collection = Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.REQUESTED,
            estimated_quantity_kg=self.listing.quantity_kg,
        )

        # Owner institution can view
        self.client.force_login(self.inst_user)
        resp = self.client.get(reverse("accounts:collection_detail", args=[collection.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Collection #")
        self.assertContains(resp, "650.00")

        # Assigned partner can view
        self.client.force_login(self.partner_user)
        resp = self.client.get(reverse("accounts:collection_detail", args=[collection.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Accept Collection Request")

        # Unrelated third party is denied (403)
        self.client.force_login(self.other_user)
        resp = self.client.get(reverse("accounts:collection_detail", args=[collection.pk]))
        self.assertEqual(resp.status_code, 403)
