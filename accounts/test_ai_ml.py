"""Django tests for deterministic pilot data and all three PyTorch models."""
import tempfile
from io import StringIO
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.matching import get_recommended_partners
from accounts.models import (EducationalInstitution, PaperListing, RecyclingProfile,
                             UserRole, VerificationStatus, WasteRecord)
from ml_engine.datasets.pilot import generate_pilot_data
from ml_engine.inference.aggregation import AggregationInference
from ml_engine.inference.forecast import PaperWasteForecastInference
from ml_engine.inference.partner_match import PartnerMatchInference
from ml_engine.services import forecast_institution, recommend_bulk_aggregations
from ml_engine.training.train_models import train_all_models

User = get_user_model()


class MLTrainingPipelineTests(SimpleTestCase):
    def test_generation_training_forward_pass_and_explanations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data_dir = root / "data"
            duplicate_dir = root / "data_duplicate"
            artifacts = root / "artifacts"
            counts = generate_pilot_data(data_dir, institutions=30, requests=360, months=12, seed=73)
            generate_pilot_data(duplicate_dir, institutions=30, requests=360, months=12, seed=73)
            self.assertEqual(counts["weekly_waste.csv"], 30 * len(pd.read_csv(data_dir / "weekly_waste.csv").week_start.unique()))
            self.assertGreater(counts["ranking_candidates.csv"], 1000)
            self.assertGreater(counts["aggregation_candidates.csv"], 20)
            pd.testing.assert_frame_equal(pd.read_csv(data_dir / "weekly_waste.csv"),
                                          pd.read_csv(duplicate_dir / "weekly_waste.csv"))

            metrics = train_all_models(data_dir, artifacts, seed=73, epochs=12)
            self.assertEqual(set(metrics), {"forecast", "ranker", "aggregation"})
            for key in metrics:
                self.assertLess(metrics[key]["training_loss_final"], metrics[key]["training_loss_initial"], key)
            for name in ("paper_waste_forecaster", "recycler_ranker", "aggregation_scorer"):
                self.assertTrue((artifacts / f"{name}.pt").is_file())
                self.assertTrue((artifacts / f"{name}.json").is_file())

            forecast = PaperWasteForecastInference(artifacts / "paper_waste_forecaster.pt").predict({
                "lag_1_kg": 420, "lag_2_kg": 400, "lag_4_kg": 380, "student_count": 8500,
                "share_office_paper": .3, "share_books_notebooks": .25,
                "share_newspapers_magazines": .15, "share_cardboard": .1, "share_mixed_paper": .2,
                "is_exam_period": 1, "is_semester_end": 1, "is_vacation": 0,
                "month_sin": .5, "month_cos": .86,
            })
            self.assertIsNotNone(forecast)
            self.assertLessEqual(0, forecast["lower_90_kg"])
            self.assertLess(forecast["lower_90_kg"], forecast["upper_90_kg"])

            rank = PartnerMatchInference(artifacts / "recycler_ranker.pt").predict([{
                "distance_km": 3.2, "capacity_utilization_ratio": .62, "paper_grade_match": 1,
                "historical_fulfillment_rate": .98, "average_rating": 4.7,
                "price_competitiveness": 1.1,
            }])
            self.assertEqual(len(rank), 1)
            self.assertTrue(rank[0]["factors"])
            self.assertTrue(all(isinstance(reason, str) for reason in rank[0]["factors"]))

            aggregation = AggregationInference(artifacts / "aggregation_scorer.pt").predict([{
                "institution_count": 3, "combined_weight_kg": 2100,
                "truck_capacity_utilization": .42, "radius_utilization": .25,
                "deadline_overlap_days": 3, "distance_savings_km": 8,
                "estimated_transport_cost_per_kg": .04,
            }])
            self.assertEqual(len(aggregation), 1)
            self.assertTrue(np.isfinite(aggregation[0]))

    def test_missing_checkpoints_fail_soft(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "not-trained.pt"
            self.assertIsNone(PaperWasteForecastInference(missing).predict({}))
            self.assertIsNone(PartnerMatchInference(missing).predict([{}]))
            self.assertIsNone(AggregationInference(missing).predict([{}]))


class BulkAggregationTests(SimpleTestCase):
    def test_constraints_cost_and_recycler_selection(self):
        requests = [
            {"request_id": "a", "institution_id": "i1", "latitude": 23.81, "longitude": 90.41,
             "ready_volume_kg": 300, "paper_type": "office_paper", "pickup_start": "2026-03-01", "pickup_deadline": "2026-03-08"},
            {"request_id": "b", "institution_id": "i2", "latitude": 23.812, "longitude": 90.412,
             "ready_volume_kg": 350, "paper_type": "office_paper", "pickup_start": "2026-03-02", "pickup_deadline": "2026-03-07"},
            {"request_id": "c", "institution_id": "i3", "latitude": 23.809, "longitude": 90.414,
             "ready_volume_kg": 400, "paper_type": "office_paper", "pickup_start": "2026-03-03", "pickup_deadline": "2026-03-06"},
        ]
        recyclers = [{"recycler_id": "r1", "latitude": 23.83, "longitude": 90.42,
                      "available_capacity_kg": 5000, "accepted_paper_types": ["office_paper"],
                      "transport_cost_per_km": 10}]
        result = recommend_bulk_aggregations(requests, recyclers, radius_km=5,
                                             truck_capacity_kg=2000, min_solo_dispatch_kg=800,
                                             model_path=Path("missing-aggregation-model.pt"))
        self.assertTrue(result)
        bundle = result[0]
        self.assertGreaterEqual(len(bundle["request_ids"]), 2)
        self.assertEqual(bundle["combined_weight_kg"], sum(row["ready_volume_kg"] for row in requests))
        self.assertGreater(bundle["distance_savings_km"], 0)
        self.assertEqual(bundle["matched_recycler"]["id"], "r1")
        self.assertTrue(bundle["decision_factors"])

    def test_out_of_radius_pickups_are_filtered(self):
        requests = [
            {"request_id": "near", "latitude": 23.81, "longitude": 90.41, "ready_volume_kg": 300,
             "paper_type": "office_paper", "pickup_start": "2026-03-01", "pickup_deadline": "2026-03-08"},
            {"request_id": "far", "latitude": 23.91, "longitude": 90.41, "ready_volume_kg": 350,
             "paper_type": "office_paper", "pickup_start": "2026-03-02", "pickup_deadline": "2026-03-07"},
        ]
        recycler = [{"id": "r1", "latitude": 23.83, "longitude": 90.42,
                     "available_capacity_kg": 5000, "accepted_paper_types": ["office_paper"]}]
        self.assertEqual(recommend_bulk_aggregations(requests, recycler, radius_km=5,
                                                     min_solo_dispatch_kg=500), [])

    def test_non_overlapping_windows_and_inadequate_capacity_are_filtered(self):
        requests = [
            {"request_id": "a", "latitude": 23.81, "longitude": 90.41, "ready_volume_kg": 300,
             "paper_type": "office_paper", "pickup_start": "2026-03-01", "pickup_deadline": "2026-03-02"},
            {"request_id": "b", "latitude": 23.811, "longitude": 90.411, "ready_volume_kg": 300,
             "paper_type": "office_paper", "pickup_start": "2026-03-10", "pickup_deadline": "2026-03-11"},
        ]
        recycler = [{"id": "r1", "latitude": 23.83, "longitude": 90.42,
                     "available_capacity_kg": 5000, "accepted_paper_types": ["office_paper"]}]
        self.assertEqual(recommend_bulk_aggregations(requests, recycler, min_solo_dispatch_kg=500), [])
        requests[1]["pickup_start"] = "2026-03-02"
        requests[1]["pickup_deadline"] = "2026-03-03"
        recycler[0]["available_capacity_kg"] = 500
        self.assertEqual(recommend_bulk_aggregations(requests, recycler, min_solo_dispatch_kg=500), [])


class ExistingDiscoveryAIIntegrationTests(TestCase):
    def test_recommendations_keep_eligibility_and_fallback_reasons(self):
        institution_user = User.objects.create_user(
            email="ai-institution@example.test", password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION, verification_status=VerificationStatus.VERIFIED,
            organization_name="Dhaka Pilot College", is_active=True,
        )
        institution = EducationalInstitution.objects.create(user=institution_user)
        listing = PaperListing.objects.create(
            institution=institution, paper_type=PaperListing.PaperCategory.OFFICE,
            quantity_kg=500, pickup_address="Campus", pickup_city="Dhaka",
            status=PaperListing.Status.AVAILABLE,
        )
        partner_user = User.objects.create_user(
            email="ai-partner@example.test", password="testpassword123",
            role=UserRole.RECYCLING_PARTNER, verification_status=VerificationStatus.VERIFIED,
            organization_name="Dhaka Paper Recycler", is_active=True,
        )
        RecyclingProfile.objects.create(
            user=partner_user, accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Dhaka", maximum_capacity=1500, collection_available=True,
        )
        results = get_recommended_partners(listing)
        self.assertEqual(len(results), 1)
        self.assertIn("match_factors", results[0])
        self.assertIsNone(results[0].get("ai_relevance"))


class LiveDjangoAIServicesTests(TestCase):
    def setUp(self):
        self.institution_user = User.objects.create_user(
            email="live-ai-institution@example.test", password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION, verification_status=VerificationStatus.VERIFIED,
            organization_name="Live Pilot Institute", is_active=True,
        )
        self.institution = EducationalInstitution.objects.create(
            user=self.institution_user, city="Dhaka", country="Bangladesh", student_count=2400,
        )
        self.client = Client()
        self.client.force_login(self.institution_user)

    def test_forecast_requires_history_then_uses_persisted_records(self):
        empty = forecast_institution(self.institution)
        self.assertFalse(empty["available"])
        today = timezone.localdate()
        monday = today - timedelta(days=today.weekday())
        for offset, weight in enumerate((40, 45, 42, 60)):
            WasteRecord.objects.create(
                institution=self.institution, week_start=monday - timedelta(weeks=3 - offset),
                paper_grade=PaperListing.PaperCategory.OFFICE, actual_weight_kg=weight,
            )
        forecast = forecast_institution(self.institution, weeks=3)
        self.assertTrue(forecast["available"])
        self.assertEqual(len(forecast["weeks"]), 3)
        self.assertIn(forecast["source"], ("pytorch", "seasonal_baseline"))

    def test_profile_and_bulk_pages_gracefully_handle_missing_geo_history(self):
        dashboard = self.client.get(reverse("accounts:institution_dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "four weeks of recorded paper weights")
        self.assertContains(dashboard, reverse("accounts:institution_profile"))
        profile_page = self.client.get(reverse("accounts:institution_profile"))
        self.assertEqual(profile_page.status_code, 200)
        bulk_page = self.client.get(reverse("accounts:bulk_aggregation"))
        self.assertEqual(bulk_page.status_code, 200)
        self.assertContains(bulk_page, "At least two geocoded")

    def test_profile_saves_coordinates_and_size(self):
        response = self.client.post(reverse("accounts:institution_profile"), {
            "institution_type": "College", "address": "Dhanmondi", "city": "Dhanmondi",
            "country": "Bangladesh", "student_count": "1800", "latitude": "23.746",
            "longitude": "90.376",
        })
        self.assertRedirects(response, reverse("accounts:institution_dashboard"))
        self.institution.refresh_from_db()
        self.assertEqual(self.institution.student_count, 1800)
        self.assertAlmostEqual(self.institution.latitude, 23.746)
        self.assertAlmostEqual(self.institution.longitude, 90.376)

    def test_bulk_page_shows_live_bundle_and_capacity_matched_recycler(self):
        today = timezone.localdate()
        self.institution.latitude, self.institution.longitude = 23.810, 90.410
        self.institution.city = "Dhanmondi"
        self.institution.save()
        other_user = User.objects.create_user(
            email="live-ai-neighbor@example.test", password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION, verification_status=VerificationStatus.VERIFIED,
            organization_name="Neighbor College", is_active=True,
        )
        other = EducationalInstitution.objects.create(user=other_user, city="Dhanmondi",
                                                       student_count=1200, latitude=23.812,
                                                       longitude=90.412)
        for institution, quantity in ((self.institution, 400), (other, 450)):
            PaperListing.objects.create(
                institution=institution, paper_type=PaperListing.PaperCategory.OFFICE,
                quantity_kg=quantity, pickup_address="Campus", pickup_city="Dhanmondi",
                available_from=today + timedelta(days=1), available_until=today + timedelta(days=8),
                status=PaperListing.Status.AVAILABLE,
            )
        recycler_user = User.objects.create_user(
            email="live-ai-recycler@example.test", password="testpassword123",
            role=UserRole.RECYCLING_PARTNER, verification_status=VerificationStatus.VERIFIED,
            organization_name="Nearby Green Recycler", is_active=True,
        )
        RecyclingProfile.objects.create(
            user=recycler_user, accepted_paper_types=[PaperListing.PaperCategory.OFFICE],
            service_area="Dhanmondi, Dhaka", maximum_capacity=5000,
            latitude=23.830, longitude=90.420, collection_available=True,
        )
        response = self.client.get(reverse("accounts:bulk_aggregation"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "850 kg combined")
        self.assertContains(response, "Nearby Green Recycler")
        self.assertContains(response, "Distance saved")

    def test_seed_command_is_repeatable(self):
        call_command("seed_pilot_data", institutions=2, recyclers=1, weeks=4,
                     minimum_records=1, force=True, allow_non_postgresql=True, stdout=StringIO())
        records_after_first = WasteRecord.objects.filter(is_synthetic=True).count()
        listings_after_first = PaperListing.objects.filter(description__contains="Synthetic Dhaka pilot").count()
        call_command("seed_pilot_data", institutions=2, recyclers=1, weeks=4,
                     minimum_records=1, force=True, allow_non_postgresql=True, stdout=StringIO())
        self.assertEqual(WasteRecord.objects.filter(is_synthetic=True).count(), records_after_first)
        self.assertEqual(PaperListing.objects.filter(description__contains="Synthetic Dhaka pilot").count(),
                         listings_after_first)
        self.assertEqual(records_after_first, 2 * 4 * 5)
        self.assertEqual(listings_after_first, 2)
