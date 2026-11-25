from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from accounts.forms import RecyclingProfileForm
from accounts.matching import get_recommended_partners
from accounts.models import (
    Collection,
    EducationalInstitution,
    PaperListing,
    RecyclingProfile,
    UserRole,
    VerificationStatus,
)
from accounts.views import edit_partner_profile, partner_dashboard

User = get_user_model()


class TestRecyclerProfileFR06(TestCase):
    """
    Test suite for FR-06: Recycler Profile Management.
    - Verified partner profile creation and dashboard access.
    - Profile update via RecyclingProfileForm.
    - Access control: institutions and unverified partners cannot access partner profile views.
    """

    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()

        # Verified recycling partner user and profile
        self.partner_user = User.objects.create_user(
            email="partner_fr06@test.com",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Green Pulp Recyclers",
            contact_name="Farhan Ahmed",
            phone="+8801711223344",
            is_active=True,
        )
        self.partner_profile = RecyclingProfile.objects.create(
            user=self.partner_user,
            accepted_paper_types=[
                PaperListing.PaperCategory.OFFICE,
                PaperListing.PaperCategory.CARDBOARD,
            ],
            service_area="Dhaka, Gazipur",
            capacity_kg_per_month=Decimal("5000.00"),
            collection_available=True,
        )

        # Verified institution user
        self.institution_user = User.objects.create_user(
            email="institution_fr06@test.com",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Dhaka City College",
            is_active=True,
        )
        self.institution = EducationalInstitution.objects.create(user=self.institution_user)

        # Unverified partner user (verification pending)
        self.unverified_partner_user = User.objects.create_user(
            email="unverified_fr06@test.com",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.PENDING,
            organization_name="Pending Recyclers Co",
            is_active=True,
        )
        self.unverified_partner_profile = RecyclingProfile.objects.create(
            user=self.unverified_partner_user,
            accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Dhaka",
            capacity_kg_per_month=Decimal("2000.00"),
            collection_available=True,
        )

    def test_create_verified_partner_user_and_profile(self):
        """Verify created partner user and profile attributes."""
        self.assertEqual(self.partner_user.role, UserRole.RECYCLING_PARTNER)
        self.assertEqual(self.partner_user.verification_status, VerificationStatus.VERIFIED)
        self.assertTrue(self.partner_user.is_verified_organization)
        self.assertEqual(self.partner_profile.user, self.partner_user)
        self.assertEqual(
            self.partner_profile.accepted_paper_types,
            [PaperListing.PaperCategory.OFFICE, PaperListing.PaperCategory.CARDBOARD],
        )
        self.assertEqual(self.partner_profile.service_area, "Dhaka, Gazipur")
        self.assertEqual(self.partner_profile.capacity_kg_per_month, Decimal("5000.00"))
        self.assertTrue(self.partner_profile.collection_available)

    def test_partner_can_access_partner_dashboard_and_see_profile_data(self):
        """Partner can access partner_dashboard and view their profile data."""
        self.client.force_login(self.partner_user)
        response = self.client.get(reverse("accounts:partner_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("profile", response.context)
        self.assertEqual(response.context["profile"], self.partner_profile)

        # Verify profile data in rendered content
        self.assertContains(response, "Green Pulp Recyclers")
        self.assertContains(response, "Farhan Ahmed")
        self.assertContains(response, "Dhaka, Gazipur")
        self.assertContains(response, "5000.00 kg")
        self.assertContains(response, "Office paper")
        self.assertContains(response, "Cardboard")
        self.assertContains(response, "Accepting Collections")

    def test_partner_can_update_recycling_profile_form(self):
        """
        Partner can update RecyclingProfileForm with accepted_paper_types,
        service_area, capacity_kg_per_month, and collection_available.
        """
        self.client.force_login(self.partner_user)

        # 1. Test direct form validation and saving
        form_data = {
            "accepted_paper_types": [
                PaperListing.PaperCategory.NEWS,
                PaperListing.PaperCategory.BOOKS,
            ],
            "service_area": "Chittagong, Cox's Bazar",
            "capacity_kg_per_month": "7500.50",
            "collection_available": False,
        }
        form = RecyclingProfileForm(data=form_data, instance=self.partner_profile)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.partner_profile.refresh_from_db()
        self.assertEqual(
            self.partner_profile.accepted_paper_types,
            [PaperListing.PaperCategory.NEWS, PaperListing.PaperCategory.BOOKS],
        )
        self.assertEqual(self.partner_profile.service_area, "Chittagong, Cox's Bazar")
        self.assertEqual(self.partner_profile.capacity_kg_per_month, Decimal("7500.50"))
        self.assertFalse(self.partner_profile.collection_available)

        # 2. Test updating via the partner profile view POST
        update_data = {
            "accepted_paper_types": [PaperListing.PaperCategory.OFFICE],
            "service_area": "Sylhet Metropolitan",
            "capacity_kg_per_month": "12000.00",
            "collection_available": "on",
        }
        post_response = self.client.post(reverse("accounts:partner_profile"), update_data)
        self.assertRedirects(post_response, reverse("accounts:partner_dashboard"))

        self.partner_profile.refresh_from_db()
        self.assertEqual(self.partner_profile.accepted_paper_types, [PaperListing.PaperCategory.OFFICE])
        self.assertEqual(self.partner_profile.service_area, "Sylhet Metropolitan")
        self.assertEqual(self.partner_profile.capacity_kg_per_month, Decimal("12000.00"))
        self.assertTrue(self.partner_profile.collection_available)

    def test_institution_user_cannot_access_partner_profile_views(self):
        """Institution user cannot access partner profile views (PermissionDenied / 403)."""
        # Test HTTP 403 via test client
        self.client.force_login(self.institution_user)

        dash_response = self.client.get(reverse("accounts:partner_dashboard"))
        self.assertEqual(dash_response.status_code, 403)

        profile_get = self.client.get(reverse("accounts:partner_profile"))
        self.assertEqual(profile_get.status_code, 403)

        profile_post = self.client.post(
            reverse("accounts:partner_profile"),
            {"service_area": "Test Area"},
        )
        self.assertEqual(profile_post.status_code, 403)

        # Test direct view call raises PermissionDenied
        req = self.factory.get(reverse("accounts:partner_dashboard"))
        req.user = self.institution_user
        with self.assertRaises(PermissionDenied):
            partner_dashboard(req)

        req_profile = self.factory.get(reverse("accounts:partner_profile"))
        req_profile.user = self.institution_user
        with self.assertRaises(PermissionDenied):
            edit_partner_profile(req_profile)

    def test_unverified_partner_cannot_access_partner_profile_views(self):
        """Unverified partner cannot access partner profile views (PermissionDenied / 403)."""
        # Test HTTP 403 via test client
        self.client.force_login(self.unverified_partner_user)

        dash_response = self.client.get(reverse("accounts:partner_dashboard"))
        self.assertEqual(dash_response.status_code, 403)

        profile_get = self.client.get(reverse("accounts:partner_profile"))
        self.assertEqual(profile_get.status_code, 403)

        profile_post = self.client.post(
            reverse("accounts:partner_profile"),
            {"service_area": "Test Area"},
        )
        self.assertEqual(profile_post.status_code, 403)

        # Test direct view call raises PermissionDenied
        req = self.factory.get(reverse("accounts:partner_dashboard"))
        req.user = self.unverified_partner_user
        with self.assertRaises(PermissionDenied):
            partner_dashboard(req)

        req_profile = self.factory.get(reverse("accounts:partner_profile"))
        req_profile.user = self.unverified_partner_user
        with self.assertRaises(PermissionDenied):
            edit_partner_profile(req_profile)


class TestRecyclerMatchingAndSelectionFR08(TestCase):
    """
    Test suite for FR-08: Recycler Matching and Selection.
    - Matching engine ranking and explainability reasons.
    - Listing recommendations view for institution user.
    - Selection of recommended partner creating collection and updating listing status.
    - Constraint enforcement: rejecting duplicate active collection requests.
    - Authorization: non-owner institution cannot select partner for other's listing.
    """

    def setUp(self):
        self.client = Client()

        # Verified institution user and institution
        self.inst_user = User.objects.create_user(
            email="inst_fr08@test.com",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Apex International School",
            is_active=True,
        )
        self.institution = EducationalInstitution.objects.create(user=self.inst_user)

        # Available PaperListing
        self.listing = PaperListing.objects.create(
            institution=self.institution,
            paper_type=PaperListing.PaperCategory.OFFICE,
            quantity_kg=Decimal("1000.00"),
            pickup_address="42 Green Road",
            pickup_city="Dhaka",
            pickup_country="Bangladesh",
            status=PaperListing.Status.AVAILABLE,
        )

        # Partner 1: Matches listing paper_type and location
        self.matching_partner_user = User.objects.create_user(
            email="matching_p1@test.com",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Dhaka Paper Recyclers",
            contact_name="Tariq Islam",
            phone="+8801811223344",
            is_active=True,
        )
        self.matching_partner = RecyclingProfile.objects.create(
            user=self.matching_partner_user,
            accepted_paper_types=[
                PaperListing.PaperCategory.OFFICE,
                PaperListing.PaperCategory.CARDBOARD,
            ],
            service_area="Dhaka Division",
            capacity_kg_per_month=Decimal("5000.00"),
            collection_available=True,
        )

        # Partner 2: Does not accept listing paper_type
        self.non_matching_partner_user = User.objects.create_user(
            email="non_matching_p2@test.com",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Sylhet Carton Works",
            contact_name="Jamil Hossain",
            phone="+8801911223344",
            is_active=True,
        )
        self.non_matching_partner = RecyclingProfile.objects.create(
            user=self.non_matching_partner_user,
            accepted_paper_types=[PaperListing.PaperCategory.CARDBOARD],
            service_area="Sylhet",
            capacity_kg_per_month=Decimal("3000.00"),
            collection_available=True,
        )

        # Another verified institution user (non-owner)
        self.other_inst_user = User.objects.create_user(
            email="other_inst@test.com",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Metropolitan University",
            is_active=True,
        )
        self.other_institution = EducationalInstitution.objects.create(user=self.other_inst_user)

    def test_get_recommended_partners_matching_score_and_explainability(self):
        """
        get_recommended_partners returns matching partner with higher score
        and transparent explainability reasons.
        """
        recommendations = get_recommended_partners(self.listing)
        partner_ids = [r["partner"].pk for r in recommendations]

        # Matching partner must be recommended
        self.assertIn(self.matching_partner.pk, partner_ids)

        p1_rec = next(r for r in recommendations if r["partner"].pk == self.matching_partner.pk)
        p2_rec = next((r for r in recommendations if r["partner"].pk == self.non_matching_partner.pk), None)

        # Partner 1 score: Category (40) + Capacity (30) + Exact City (30) = 100 clamped to 98
        self.assertEqual(p1_rec["match_score"], 98)

        # Check explainability reasons for matching partner
        self.assertIn("✓ Accepts Office paper", p1_rec["match_reasons"])
        self.assertIn("✓ Capacity (5000.00 kg/mo) covers listing", p1_rec["match_reasons"])
        self.assertIn("✓ Services Dhaka", p1_rec["match_reasons"])
        self.assertIn("✓ Verified recycling partner", p1_rec["match_reasons"])

        # If non-matching partner is returned (e.g. general service area threshold), matching partner has strictly higher score
        if p2_rec:
            self.assertGreater(p1_rec["match_score"], p2_rec["match_score"])

        # Matching partner should be top-ranked
        self.assertEqual(recommendations[0]["partner"].pk, self.matching_partner.pk)

    def test_institution_user_can_view_listing_recommendations(self):
        """Institution user can view listing_recommendations."""
        self.client.force_login(self.inst_user)
        url = reverse("accounts:listing_recommendations", kwargs={"listing_id": self.listing.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("recommendations", response.context)
        self.assertIn("listing", response.context)
        self.assertEqual(response.context["listing"], self.listing)

        # Verify matching partner details appear in the page
        self.assertContains(response, "Dhaka Paper Recyclers")
        self.assertContains(response, "✓ Accepts Office paper")
        self.assertContains(response, "Eligibility-Based Recommendations")
        self.assertContains(response, "Eligibility Score:")
        self.assertContains(response, "Rule-based ordering")

    def test_institution_user_can_select_recommended_partner(self):
        """
        Institution user can select recommended partner via POST to select_recommended_partner:
        - Creates Collection with status='requested'.
        - Updates listing.status to 'reserved'.
        """
        self.client.force_login(self.inst_user)
        url = reverse("accounts:select_recommended_partner", kwargs={"listing_id": self.listing.pk})
        response = self.client.post(url, {
            "partner_id": self.matching_partner.pk,
            "notes": "Please arrange truck pickup on Wednesday at 10 AM.",
        })
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))

        # 1. Collection created with status='requested'
        collection = Collection.objects.get(listing=self.listing)
        self.assertEqual(collection.partner, self.matching_partner)
        self.assertEqual(collection.status, Collection.Status.REQUESTED)
        self.assertEqual(collection.status, "requested")
        self.assertEqual(collection.notes, "Please arrange truck pickup on Wednesday at 10 AM.")

        # 2. Listing status updated to 'reserved'
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, PaperListing.Status.RESERVED)
        self.assertEqual(self.listing.status, "reserved")

    def test_selecting_partner_again_is_rejected_one_active_collection_constraint(self):
        """
        Selecting partner again for a listing with an active collection is rejected.
        Also verifies the one_active_collection_per_listing constraint.
        """
        self.client.force_login(self.inst_user)

        # Create active collection
        Collection.objects.create(
            listing=self.listing,
            partner=self.matching_partner,
            status=Collection.Status.REQUESTED,
        )
        self.listing.status = PaperListing.Status.RESERVED
        self.listing.save()

        # Attempt to select a partner again via view POST
        url = reverse("accounts:select_recommended_partner", kwargs={"listing_id": self.listing.pk})
        response = self.client.post(url, {
            "partner_id": self.matching_partner.pk,
            "notes": "Attempting second request.",
        })
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))

        # Verify only 1 collection exists
        self.assertEqual(Collection.objects.filter(listing=self.listing).count(), 1)

        # Verify database-level UniqueConstraint prevents a second active collection
        with self.assertRaises(IntegrityError):
            Collection.objects.create(
                listing=self.listing,
                partner=self.non_matching_partner,
                status=Collection.Status.REQUESTED,
            )

    def test_non_owner_institution_cannot_select_partner_for_another_institutions_listing(self):
        """Non-owner institution cannot view or select partner for another institution's listing."""
        self.client.force_login(self.other_inst_user)

        # GET recommendations on other institution's listing returns 404
        rec_url = reverse("accounts:listing_recommendations", kwargs={"listing_id": self.listing.pk})
        rec_response = self.client.get(rec_url)
        self.assertEqual(rec_response.status_code, 404)

        # POST select partner on other institution's listing returns 404
        select_url = reverse("accounts:select_recommended_partner", kwargs={"listing_id": self.listing.pk})
        select_response = self.client.post(select_url, {
            "partner_id": self.matching_partner.pk,
            "notes": "Unauthorized attempt",
        })
        self.assertEqual(select_response.status_code, 404)

        # Listing remains unchanged with no collections created
        self.assertEqual(Collection.objects.filter(listing=self.listing).count(), 0)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, PaperListing.Status.AVAILABLE)


class RecyclingProfileFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="partner_form@test.com",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            organization_name="Green Pulp Recyclers",
        )
        self.profile = RecyclingProfile.objects.create(
            user=self.user,
            accepted_paper_types=[PaperListing.PaperCategory.OFFICE, PaperListing.PaperCategory.CARDBOARD],
            service_area="Dhaka, Gazipur",
            capacity_kg_per_month=Decimal("5000.00"),
            collection_available=True,
        )

    def test_form_initialization_from_instance(self):
        form = RecyclingProfileForm(instance=self.profile)
        self.assertEqual(
            form.initial["accepted_paper_types"],
            [PaperListing.PaperCategory.OFFICE, PaperListing.PaperCategory.CARDBOARD],
        )

    def test_clean_accepted_paper_types_valid(self):
        form_data = {
            "accepted_paper_types": [
                PaperListing.PaperCategory.OFFICE,
                PaperListing.PaperCategory.BOOKS,
            ],
            "service_area": "Chittagong",
            "capacity_kg_per_month": "8000.00",
            "collection_available": True,
        }
        form = RecyclingProfileForm(data=form_data, instance=self.profile)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["accepted_paper_types"],
            [PaperListing.PaperCategory.OFFICE, PaperListing.PaperCategory.BOOKS],
        )

    def test_clean_accepted_paper_types_invalid_choice_rejected(self):
        form_data = {
            "accepted_paper_types": ["invalid_category_slug"],
            "service_area": "Chittagong",
            "capacity_kg_per_month": "8000.00",
            "collection_available": True,
        }
        form = RecyclingProfileForm(data=form_data, instance=self.profile)
        self.assertFalse(form.is_valid())
        self.assertIn("accepted_paper_types", form.errors)

    def test_form_save_updates_profile(self):
        form_data = {
            "accepted_paper_types": [PaperListing.PaperCategory.NEWS],
            "service_area": "Sylhet",
            "capacity_kg_per_month": "12000.50",
            "collection_available": False,
        }
        form = RecyclingProfileForm(data=form_data, instance=self.profile)
        self.assertTrue(form.is_valid())
        updated = form.save(commit=True)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.accepted_paper_types, [PaperListing.PaperCategory.NEWS])
        self.assertEqual(self.profile.service_area, "Sylhet")
        self.assertEqual(self.profile.capacity_kg_per_month, Decimal("12000.50"))
        self.assertFalse(self.profile.collection_available)


class MatchingEngineTest(TestCase):
    def setUp(self):
        self.inst_user = User.objects.create_user(
            email="inst_match@test.com",
            password="password",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            is_active=True,
        )
        self.institution = EducationalInstitution.objects.create(user=self.inst_user)
        self.listing = PaperListing.objects.create(
            institution=self.institution,
            paper_type=PaperListing.PaperCategory.OFFICE,
            quantity_kg=Decimal("1000.00"),
            pickup_address="123 Campus Rd",
            pickup_city="Dhaka",
            pickup_country="Bangladesh",
            status=PaperListing.Status.AVAILABLE,
        )

        # Partner 1: Perfect match (Category, Capacity, Exact Location)
        self.user1 = User.objects.create_user(
            email="p1@test.com",
            password="password",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            is_active=True,
            organization_name="Dhaka Paper Mills",
        )
        self.profile1 = RecyclingProfile.objects.create(
            user=self.user1,
            accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Dhaka Division",
            capacity_kg_per_month=Decimal("5000.00"),
            collection_available=True,
        )

        # Partner 2: General location match, capacity match, category match
        self.user2 = User.objects.create_user(
            email="p2@test.com",
            password="password",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            is_active=True,
            organization_name="National Recyclers",
        )
        self.profile2 = RecyclingProfile.objects.create(
            user=self.user2,
            accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Nationwide across all regions",
            capacity_kg_per_month=Decimal("2000.00"),
            collection_available=True,
        )

        # Partner 3: Flexible capacity (None), unverified -> should be excluded
        self.user3 = User.objects.create_user(
            email="p3@test.com",
            password="password",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.PENDING,
            is_active=True,
            organization_name="Pending Recyclers",
        )
        self.profile3 = RecyclingProfile.objects.create(
            user=self.user3,
            accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Dhaka",
            capacity_kg_per_month=None,
            collection_available=True,
        )

        # Partner 4: Collection paused -> should be excluded
        self.user4 = User.objects.create_user(
            email="p4@test.com",
            password="password",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            is_active=True,
            organization_name="Paused Recyclers",
        )
        self.profile4 = RecyclingProfile.objects.create(
            user=self.user4,
            accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Dhaka",
            capacity_kg_per_month=Decimal("10000.00"),
            collection_available=False,
        )

        # Partner 5: Does not accept category and no location match -> below threshold, excluded
        self.user5 = User.objects.create_user(
            email="p5@test.com",
            password="password",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            is_active=True,
            organization_name="No Match Recyclers",
        )
        self.profile5 = RecyclingProfile.objects.create(
            user=self.user5,
            accepted_paper_types=[PaperListing.PaperCategory.CARDBOARD],
            service_area="",
            capacity_kg_per_month=Decimal("500.00"),
            collection_available=True,
        )

    def test_recommended_partners_filtering_and_ranking(self):
        recommendations = get_recommended_partners(self.listing)
        partner_ids = [r["partner"].pk for r in recommendations]

        # P1 and P2 should be included
        self.assertIn(self.profile1.pk, partner_ids)
        self.assertIn(self.profile2.pk, partner_ids)

        # P3 (unverified), P4 (collection paused), P5 (below threshold) excluded
        self.assertNotIn(self.profile3.pk, partner_ids)
        self.assertNotIn(self.profile4.pk, partner_ids)
        self.assertNotIn(self.profile5.pk, partner_ids)

        # P1 score: Category (40) + Capacity (30) + Exact City (30) = 100 -> clamped to 98
        p1_rec = next(r for r in recommendations if r["partner"].pk == self.profile1.pk)
        self.assertEqual(p1_rec["match_score"], 98)
        self.assertIn("✓ Accepts Office paper", p1_rec["match_reasons"])
        self.assertIn("✓ Capacity (5000.00 kg/mo) covers listing", p1_rec["match_reasons"])
        self.assertIn("✓ Services Dhaka", p1_rec["match_reasons"])
        self.assertIn("✓ Verified recycling partner", p1_rec["match_reasons"])

        # P2 score: Category (40) + Capacity (30) + General Location (15) = 85
        p2_rec = next(r for r in recommendations if r["partner"].pk == self.profile2.pk)
        self.assertEqual(p2_rec["match_score"], 85)

        # Sorted descending
        self.assertEqual(recommendations[0]["partner"].pk, self.profile1.pk)

    def test_flexible_capacity_reason(self):
        self.profile1.capacity_kg_per_month = None
        self.profile1.save()

        recommendations = get_recommended_partners(self.listing)
        p1_rec = next(r for r in recommendations if r["partner"].pk == self.profile1.pk)
        self.assertIn("✓ Capacity (Flexible kg/mo) covers listing", p1_rec["match_reasons"])


class PartnerViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="partner_views@test.com",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Green Eco Hub",
            is_active=True,
        )
        self.profile = RecyclingProfile.objects.create(
            user=self.user,
            accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Dhaka",
            capacity_kg_per_month=Decimal("4000.00"),
            collection_available=True,
        )

    def test_partner_dashboard_context(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:partner_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("profile", response.context)
        self.assertIn("incoming_collections", response.context)
        self.assertEqual(response.context["total_requests"], 0)
        self.assertEqual(response.context["pending_requests"], 0)

    def test_edit_partner_profile_get_and_post(self):
        self.client.force_login(self.user)
        get_response = self.client.get(reverse("accounts:partner_profile"))
        self.assertEqual(get_response.status_code, 200)

        post_data = {
            "accepted_paper_types": [PaperListing.PaperCategory.OFFICE, PaperListing.PaperCategory.CARDBOARD],
            "service_area": "Dhaka, Savar",
            "capacity_kg_per_month": "7500.00",
            "collection_available": True,
        }
        post_response = self.client.post(reverse("accounts:partner_profile"), post_data)
        self.assertRedirects(post_response, reverse("accounts:partner_dashboard"))

        self.profile.refresh_from_db()
        self.assertIn(PaperListing.PaperCategory.CARDBOARD, self.profile.accepted_paper_types)
        self.assertEqual(self.profile.service_area, "Dhaka, Savar")
        self.assertEqual(self.profile.capacity_kg_per_month, Decimal("7500.00"))


class RecommendationViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.inst_user = User.objects.create_user(
            email="inst_views@test.com",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Apex University",
            is_active=True,
        )
        self.institution = EducationalInstitution.objects.create(user=self.inst_user)

        self.partner_user = User.objects.create_user(
            email="partner_match_view@test.com",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Pulp Solutions Ltd",
            is_active=True,
        )
        self.partner_profile = RecyclingProfile.objects.create(
            user=self.partner_user,
            accepted_paper_types=[PaperListing.PaperCategory.BOOKS],
            service_area="Khulna",
            capacity_kg_per_month=Decimal("3000.00"),
            collection_available=True,
        )

        self.listing = PaperListing.objects.create(
            institution=self.institution,
            paper_type=PaperListing.PaperCategory.BOOKS,
            quantity_kg=Decimal("800.00"),
            pickup_address="50 Lake Rd",
            pickup_city="Khulna",
            pickup_country="Bangladesh",
            status=PaperListing.Status.AVAILABLE,
        )

    def test_listing_recommendations_view(self):
        self.client.force_login(self.inst_user)
        url = reverse("accounts:listing_recommendations", kwargs={"listing_id": self.listing.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("recommendations", response.context)
        self.assertEqual(len(response.context["recommendations"]), 1)
        self.assertEqual(response.context["recommendations"][0]["partner"].pk, self.partner_profile.pk)

    def test_listing_recommendations_not_available(self):
        self.client.force_login(self.inst_user)
        self.listing.status = PaperListing.Status.DRAFT
        self.listing.save()

        url = reverse("accounts:listing_recommendations", kwargs={"listing_id": self.listing.pk})
        response = self.client.get(url)
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))

    def test_select_recommended_partner_creates_collection(self):
        self.client.force_login(self.inst_user)
        url = reverse("accounts:select_recommended_partner", kwargs={"listing_id": self.listing.pk})
        response = self.client.post(url, {
            "partner_id": self.partner_profile.pk,
            "notes": "Please bring a truck before 4 PM.",
        })
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))

        # Verify collection created
        collection = Collection.objects.get(listing=self.listing)
        self.assertEqual(collection.partner, self.partner_profile)
        self.assertEqual(collection.status, Collection.Status.REQUESTED)
        self.assertEqual(collection.notes, "Please bring a truck before 4 PM.")

        # Verify listing status updated to RESERVED
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.status, PaperListing.Status.RESERVED)

    def test_select_recommended_partner_prevents_duplicate_active_collection(self):
        self.client.force_login(self.inst_user)
        # Create an existing active collection
        Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.REQUESTED,
        )

        url = reverse("accounts:select_recommended_partner", kwargs={"listing_id": self.listing.pk})
        response = self.client.post(url, {
            "partner_id": self.partner_profile.pk,
        })
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))
        # Listing should not have a second collection created
        self.assertEqual(Collection.objects.filter(listing=self.listing).count(), 1)


class TemplateIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Institution
        self.inst_user = User.objects.create_user(
            email="inst_ui@test.com",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Greenfield High School",
            contact_name="Sarah Jenkins",
            is_active=True,
        )
        self.institution = EducationalInstitution.objects.create(user=self.inst_user)

        # Partner
        self.partner_user = User.objects.create_user(
            email="partner_ui@test.com",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="EcoCycle Ltd",
            contact_name="Mark Robinson",
            phone="+8801700000000",
            is_active=True,
        )
        self.partner_profile = RecyclingProfile.objects.create(
            user=self.partner_user,
            accepted_paper_types=[PaperListing.PaperCategory.OFFICE, PaperListing.PaperCategory.CARDBOARD],
            service_area="Dhaka, Gazipur",
            capacity_kg_per_month=Decimal("5000.00"),
            collection_available=True,
        )

        # Available listing without collection
        self.listing = PaperListing.objects.create(
            institution=self.institution,
            paper_type=PaperListing.PaperCategory.OFFICE,
            quantity_kg=Decimal("1200.00"),
            pickup_address="12 Campus Way",
            pickup_city="Dhaka",
            pickup_country="Bangladesh",
            status=PaperListing.Status.AVAILABLE,
        )

    def test_partner_dashboard_template_elements(self):
        self.client.force_login(self.partner_user)
        response = self.client.get(reverse("accounts:partner_dashboard"))
        self.assertEqual(response.status_code, 200)

        # 1. Header elements
        self.assertContains(response, "EcoCycle Ltd")
        self.assertContains(response, "Mark Robinson")
        self.assertContains(response, reverse("accounts:partner_profile"))
        self.assertContains(response, "Edit Profile &amp; Capacity")

        # 2. KPI row (3 cards)
        self.assertContains(response, "Accepting Collections")
        self.assertContains(response, "bg-success")
        self.assertContains(response, "5000.00 kg")
        self.assertContains(response, "Accepted Categories")
        self.assertContains(response, "2")  # 2 accepted categories count

        # 3. Profile details card
        self.assertContains(response, "Office paper")
        self.assertContains(response, "Cardboard")
        self.assertContains(response, "Dhaka, Gazipur")

        # 4. Incoming requests empty state
        self.assertContains(response, "No incoming collection requests yet")

        # Now test when paused and flexible capacity
        self.partner_profile.collection_available = False
        self.partner_profile.capacity_kg_per_month = None
        self.partner_profile.save()

        response_paused = self.client.get(reverse("accounts:partner_dashboard"))
        self.assertContains(response_paused, "Paused")
        self.assertContains(response_paused, "bg-secondary")
        self.assertContains(response_paused, "Flexible kg")

    def test_partner_dashboard_incoming_requests_table(self):
        Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.REQUESTED,
            notes="Please pickup on Monday morning.",
        )
        self.client.force_login(self.partner_user)
        response = self.client.get(reverse("accounts:partner_dashboard"))
        self.assertEqual(response.status_code, 200)

        # Table headers: Listing, Institution, Quantity, Pickup City, Requested At, Status
        self.assertContains(response, "Listing")
        self.assertContains(response, "Institution")
        self.assertContains(response, "Quantity")
        self.assertContains(response, "Pickup City")
        self.assertContains(response, "Requested At")
        self.assertContains(response, "Status")

        # Row content
        self.assertContains(response, "Greenfield High School")
        self.assertContains(response, "1200.00 kg")
        self.assertContains(response, "Dhaka")

    def test_partner_profile_form_template_elements(self):
        self.client.force_login(self.partner_user)
        response = self.client.get(reverse("accounts:partner_profile"))
        self.assertEqual(response.status_code, 200)

        # Redesigned profile form surface
        self.assertContains(response, "recycler-profile-settings")
        self.assertContains(response, 'class="card border-0 shadow-sm"')

        # Fieldset 1: Operating Status
        self.assertContains(response, "Operating Status")
        self.assertContains(response, "collection_available")

        # Fieldset 2: Capacity & Service Area
        self.assertContains(response, "Capacity &amp; Service Area")
        self.assertContains(response, "capacity_kg_per_month")
        self.assertContains(response, "service_area")

        # Fieldset 3: Accepted Paper Categories
        self.assertContains(response, "Accepted Paper Categories")
        self.assertContains(response, "Office paper")
        self.assertContains(response, "Cardboard")

        # Actions: Cancel and Save
        self.assertContains(response, reverse("accounts:partner_dashboard"))
        self.assertContains(response, "Cancel")
        self.assertContains(response, "Save")

    def test_listing_recommendations_template_elements(self):
        self.client.force_login(self.inst_user)
        rec_url = reverse("accounts:listing_recommendations", kwargs={"listing_id": self.listing.pk})
        response = self.client.get(rec_url)
        self.assertEqual(response.status_code, 200)

        # Back link
        self.assertContains(response, reverse("accounts:institution_dashboard"))

        # Header
        self.assertContains(response, "Recommended Recyclers for Listing")

        # Summary bar
        self.assertContains(response, "Office paper")
        self.assertContains(response, "1200.00 kg")
        self.assertContains(response, "Dhaka")

        # Recommended partner card
        self.assertContains(response, "EcoCycle Ltd")
        self.assertContains(response, "Mark Robinson")
        self.assertContains(response, "badge-saas badge-neutral")
        self.assertContains(response, "Eligibility-Based Recommendations")
        self.assertContains(response, "Eligibility Score:")
        self.assertContains(response, "Rule-based ordering")
        self.assertContains(response, "New to marketplace")
        self.assertContains(response, "No resolved pickup history; neutral fulfillment prior used")
        self.assertContains(response, "✓ Accepts Office paper")
        self.assertContains(response, "✓ Capacity (5000.00 kg/mo) covers listing")

        # Form POST action and button
        select_url = reverse("accounts:select_recommended_partner", kwargs={"listing_id": self.listing.pk})
        self.assertContains(response, f'action="{select_url}"')
        self.assertContains(response, 'name="partner_id"')
        self.assertContains(response, 'name="notes"')
        self.assertContains(response, "Select &amp; Request Pickup")

    def test_listing_recommendations_empty_alert(self):
        # Partner with empty service area and different category
        self.partner_profile.service_area = ""
        self.partner_profile.save()

        remote_listing = PaperListing.objects.create(
            institution=self.institution,
            paper_type=PaperListing.PaperCategory.OTHER,
            quantity_kg=Decimal("100.00"),
            pickup_address="99 Remote Rd",
            pickup_city="Sylhet",
            status=PaperListing.Status.AVAILABLE,
        )
        self.client.force_login(self.inst_user)
        rec_url = reverse("accounts:listing_recommendations", kwargs={"listing_id": remote_listing.pk})
        response = self.client.get(rec_url)
        self.assertEqual(response.status_code, 200)

        # Helpful alert when no recommendations
        self.assertContains(response, "No Active Recyclers Available")
        self.assertContains(response, reverse("accounts:institution_dashboard"))

    def test_institution_dashboard_find_recycler_and_active_collection_badge(self):
        self.client.force_login(self.inst_user)
        dashboard_url = reverse("accounts:institution_dashboard")

        # 1. Listing without collection: has 'Find Recycler' button
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, 200)
        rec_url = reverse("accounts:listing_recommendations", kwargs={"listing_id": self.listing.pk})
        self.assertContains(response, f'href="{rec_url}"')
        self.assertContains(response, "Find Recycler")
        self.assertContains(response, "btn-saas btn-primary btn-sm")

        # 2. Listing with active collection: shows 'Collection Requested' badge
        Collection.objects.create(
            listing=self.listing,
            partner=self.partner_profile,
            status=Collection.Status.REQUESTED,
        )
        self.listing.status = PaperListing.Status.RESERVED
        self.listing.save()

        response_with_collection = self.client.get(dashboard_url)
        self.assertContains(response_with_collection, "Requested")
        self.assertNotContains(response_with_collection, f'href="{rec_url}"')


class RecyclerDiscoveryFR08Tests(TestCase):
    def setUp(self):
        self.client = Client()
        self.institution_user = User.objects.create_user(
            email="fr08-institution@test.com",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Northside College",
            is_active=True,
        )
        self.institution = EducationalInstitution.objects.create(user=self.institution_user)
        self.listing = PaperListing.objects.create(
            institution=self.institution,
            paper_type=PaperListing.PaperCategory.OFFICE,
            quantity_kg=Decimal("1000.00"),
            pickup_address="1 Campus Road",
            pickup_city="Dhaka",
            pickup_country="Bangladesh",
            status=PaperListing.Status.AVAILABLE,
        )
        self.partner_user = User.objects.create_user(
            email="fr08-partner@test.com",
            password="testpassword123",
            role=UserRole.RECYCLING_PARTNER,
            verification_status=VerificationStatus.VERIFIED,
            organization_name="Dhaka Paper Works",
            is_active=True,
        )
        self.partner = RecyclingProfile.objects.create(
            user=self.partner_user,
            accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Dhaka, Gazipur",
            maximum_capacity=Decimal("1500.00"),
            current_allocated_load=Decimal("100.00"),
            capacity_unit=RecyclingProfile.CapacityUnit.KILOGRAM,
            capacity_period=RecyclingProfile.CapacityPeriod.MONTH,
        )

    def test_verified_partner_can_create_profile_and_update_capacity(self):
        self.partner.delete()
        self.client.force_login(self.partner_user)
        response = self.client.get(reverse("accounts:partner_profile_create"))
        self.assertEqual(response.status_code, 200)
        profile = RecyclingProfile.objects.get(user=self.partner_user)

        response = self.client.post(reverse("accounts:partner_profile"), {
            "organization_name": "Dhaka Paper Works",
            "contact_name": "Amin",
            "phone": "01700000000",
            "accepted_paper_types": [PaperListing.PaperCategory.OFFICE],
            "service_area": "Dhaka",
            "maximum_capacity": "2500.00",
            "current_allocated_load": "500.00",
            "capacity_unit": RecyclingProfile.CapacityUnit.KILOGRAM,
            "capacity_period": RecyclingProfile.CapacityPeriod.WEEK,
            "collection_available": "on",
        })
        self.assertRedirects(response, reverse("accounts:partner_dashboard"))
        profile.refresh_from_db()
        self.assertEqual(profile.maximum_capacity, Decimal("2500.00"))
        self.assertEqual(profile.current_allocated_load, Decimal("500.00"))
        self.assertEqual(profile.available_capacity, Decimal("2000.00"))
        self.assertEqual(profile.capacity_period, RecyclingProfile.CapacityPeriod.WEEK)

    def test_institution_cannot_edit_partner_profile(self):
        self.client.force_login(self.institution_user)
        response = self.client.post(reverse("accounts:partner_profile"), {
            "service_area": "Unauthorized change",
        })
        self.assertEqual(response.status_code, 403)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.service_area, "Dhaka, Gazipur")

    def test_directory_filters_category_area_and_remaining_capacity(self):
        wrong_category_user = User.objects.create_user(
            email="fr08-wrong-category@test.com", password="testpassword123",
            role=UserRole.RECYCLING_PARTNER, verification_status=VerificationStatus.VERIFIED,
            organization_name="Dhaka Cardboard", is_active=True,
        )
        RecyclingProfile.objects.create(
            user=wrong_category_user, accepted_paper_types=[PaperListing.PaperCategory.CARDBOARD],
            service_area="Dhaka", maximum_capacity=Decimal("5000"),
        )
        insufficient_user = User.objects.create_user(
            email="fr08-low-capacity@test.com", password="testpassword123",
            role=UserRole.RECYCLING_PARTNER, verification_status=VerificationStatus.VERIFIED,
            organization_name="Dhaka Small Recycler", is_active=True,
        )
        RecyclingProfile.objects.create(
            user=insufficient_user, accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Dhaka", maximum_capacity=Decimal("900"),
        )

        self.client.force_login(self.institution_user)
        response = self.client.get(reverse("accounts:partner_directory"), {
            "paper_type": PaperListing.PaperCategory.OFFICE,
            "service_area": "Dhaka",
            "quantity_kg": "1200",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p.pk for p in response.context["partners"]], [self.partner.pk])

    def test_selection_rejects_category_area_and_capacity_mismatches(self):
        self.client.force_login(self.institution_user)
        url = reverse("accounts:select_recommended_partner", args=[self.listing.pk])
        for changes in (
            {"accepted_paper_types": [PaperListing.PaperCategory.CARDBOARD]},
            {"accepted_paper_types": [PaperListing.PaperCategory.OFFICE], "service_area": "Sylhet"},
            {"accepted_paper_types": [PaperListing.PaperCategory.OFFICE], "service_area": "Dhaka", "maximum_capacity": Decimal("900"), "current_allocated_load": Decimal("0")},
        ):
            with self.subTest(changes=changes):
                self.partner.refresh_from_db()
                for field, value in changes.items():
                    setattr(self.partner, field, value)
                self.partner.save()
                response = self.client.post(url, {"partner_id": self.partner.pk})
                self.assertRedirects(response, reverse("accounts:listing_recommendations", args=[self.listing.pk]))
                self.assertFalse(Collection.objects.filter(listing=self.listing).exists())

    def test_selection_rejects_inactive_or_paused_partners(self):
        self.client.force_login(self.institution_user)
        url = reverse("accounts:select_recommended_partner", args=[self.listing.pk])
        for change in ({"is_active": False}, {"collection_available": False}):
            self.listing.refresh_from_db()
            self.listing.status = PaperListing.Status.AVAILABLE
            self.listing.save(update_fields=["status"])
            self.partner_user.is_active = True
            self.partner_user.save(update_fields=["is_active"])
            if "is_active" in change:
                self.partner_user.is_active = change["is_active"]
                self.partner_user.save(update_fields=["is_active"])
            else:
                self.partner.collection_available = change["collection_available"]
                self.partner.save(update_fields=["collection_available"])
            response = self.client.post(url, {"partner_id": self.partner.pk})
            self.assertRedirects(response, reverse("accounts:listing_recommendations", args=[self.listing.pk]))
            self.assertFalse(Collection.objects.filter(listing=self.listing).exists())
