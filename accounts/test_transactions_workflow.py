from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.impact import calculate_impact_metrics
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


class TransactionsFR11FR12Tests(TestCase):
    """
    Test suite for Step 7:
    - FR-11: Transaction history management for completed recycling activities.
    - FR-12: Automatic generation of digital recycling records and impact summaries.
    """

    def setUp(self):
        self.client = Client()

        # Institution user
        self.inst_user = User.objects.create_user(
            email="school_fr11@test.org",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Greenwood High School",
            is_active=True,
        )
        self.institution = EducationalInstitution.objects.create(
            user=self.inst_user,
            city="Dhaka",
        )

        # Recycling Partner user
        self.partner_user = User.objects.create_user(
            email="partner_fr11@test.org",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="PulpCraft Recycling Ltd",
            is_active=True,
        )
        self.partner_profile = RecyclingProfile.objects.create(
            user=self.partner_user,
            accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Dhaka",
            capacity_kg_per_month=Decimal("5000.00"),
            collection_available=True,
        )

        # Other user (for authorization / access control check)
        self.other_user = User.objects.create_user(
            email="stranger@test.org",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Other Academy",
            is_active=True,
        )
        self.other_institution = EducationalInstitution.objects.create(
            user=self.other_user,
            city="Sylhet",
        )

        # Paper Listing
        self.listing = PaperListing.objects.create(
            institution=self.institution,
            paper_type=PaperListing.PaperCategory.OFFICE,
            quantity_kg=Decimal("1000.00"),
            pickup_address="Block C, Banani",
            pickup_city="Dhaka",
            status=PaperListing.Status.RESERVED,
        )

        # Collection in SCHEDULED status
        self.collection = Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.SCHEDULED,
            estimated_quantity_kg=Decimal("1000.00"),
            scheduled_for=timezone.now() + timezone.timedelta(days=1),
        )

    def test_impact_calculation_formula(self):
        """Test the scientific/EPA based environmental impact calculation."""
        impact = calculate_impact_metrics(Decimal("1000.00"))  # 1 metric ton
        self.assertEqual(impact["quantity_kg"], Decimal("1000.00"))
        self.assertEqual(impact["trees_saved"], Decimal("17.00"))
        self.assertEqual(impact["water_liters_saved"], Decimal("26000.0"))
        self.assertEqual(impact["energy_kwh_saved"], Decimal("4000.0"))
        self.assertEqual(impact["co2_avoided_kg"], Decimal("1500.0"))
        self.assertEqual(impact["landfill_m3_saved"], Decimal("3.000"))

    def test_completion_generates_transaction_and_impact(self):
        """FR-11 & FR-12: Completing collection creates auditable transaction record."""
        self.client.force_login(self.partner_user)
        response = self.client.post(
            reverse("accounts:partner_complete_collection", args=[self.collection.pk]),
            {"final_collected_quantity_kg": "950.00", "notes": "Verified at truck scale."},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        # Check transaction created
        txn = Transaction.objects.filter(collection=self.collection).first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.quantity_kg, Decimal("950.00"))
        self.assertTrue(txn.reference.startswith("TXN-"))

        # Check impact metrics property on transaction
        impact = txn.impact_metrics
        self.assertEqual(impact["quantity_kg"], Decimal("950.00"))
        self.assertEqual(impact["trees_saved"], round(Decimal("950.00") * Decimal("0.017"), 2))

    def test_institution_can_view_transaction_history(self):
        """FR-11: Institution can view their transaction history and cumulative metrics."""
        # Create a completed transaction
        Transaction.objects.create(
            collection=self.collection,
            quantity_kg=Decimal("1000.00"),
            reference="TXN-20261122-00001",
        )

        self.client.force_login(self.inst_user)
        response = self.client.get(reverse("accounts:transaction_history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TXN-20261122-00001")
        self.assertContains(response, "1000.00")
        self.assertContains(response, "Cumulative Environmental Outcomes")

    def test_partner_can_view_transaction_history(self):
        """FR-11: Partner can view their transaction history."""
        Transaction.objects.create(
            collection=self.collection,
            quantity_kg=Decimal("1000.00"),
            reference="TXN-20261122-00001",
        )

        self.client.force_login(self.partner_user)
        response = self.client.get(reverse("accounts:transaction_history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TXN-20261122-00001")
        self.assertContains(response, "Greenwood High School")

    def test_unrelated_user_cannot_view_digital_record(self):
        """Access control: Unrelated user gets 403 when trying to access digital record."""
        txn = Transaction.objects.create(
            collection=self.collection,
            quantity_kg=Decimal("1000.00"),
            reference="TXN-20261122-00001",
        )

        self.client.force_login(self.other_user)
        response = self.client.get(reverse("accounts:digital_record", args=[txn.pk]))
        self.assertEqual(response.status_code, 403)

    def test_digital_record_page_renders_impact_and_certificate(self):
        """FR-12: Digital record renders formal certification and impact indicators."""
        txn = Transaction.objects.create(
            collection=self.collection,
            quantity_kg=Decimal("1000.00"),
            reference="TXN-20261122-00001",
        )

        self.client.force_login(self.inst_user)
        response = self.client.get(reverse("accounts:digital_record", args=[txn.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Digital Recycling Record")
        self.assertContains(response, "Greenwood High School")
        self.assertContains(response, "PulpCraft Recycling Ltd")
        self.assertContains(response, "Trees Saved")
        self.assertContains(response, "Water Conserved")
        self.assertContains(response, "CO₂e Avoided")
