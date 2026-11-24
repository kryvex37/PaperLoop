from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User, UserRole, VerificationStatus


class AdminVerificationFR02Tests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            email="platform-admin@example.test",
            password="testpassword123",
        )
        self.client = Client()
        self.organization = User.objects.create_user(
            email="pending-school@example.test",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
            organization_name="Pending School",
            verification_status=VerificationStatus.PENDING,
        )
        self.model_admin = admin.site._registry[User]

    def test_admin_home_uses_bootstrap_operations_dashboard(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Marketplace administration")
        self.assertContains(response, "card shadow-sm paperloop-admin-card")
        self.assertContains(response, "bootstrap@5.3.9")
        self.assertContains(response, reverse("admin:accounts_user_changelist"))

    def action_request(self):
        request = self.factory.post("/admin/accounts/user/")
        request.user = self.admin_user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_verify_action_sets_status_timestamp_actor_and_active_state(self):
        self.model_admin.verify_organizations(
            self.action_request(), User.objects.filter(pk=self.organization.pk)
        )

        self.organization.refresh_from_db()
        self.assertEqual(self.organization.verification_status, VerificationStatus.VERIFIED)
        self.assertIsNotNone(self.organization.verified_at)
        self.assertEqual(self.organization.verified_by, self.admin_user)
        self.assertIsNotNone(self.organization.reviewed_at)
        self.assertEqual(self.organization.reviewed_by, self.admin_user)
        self.assertTrue(self.organization.is_active)

    def test_reject_and_suspend_actions_apply_the_documented_policy(self):
        self.model_admin.reject_organizations(
            self.action_request(), User.objects.filter(pk=self.organization.pk)
        )
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.verification_status, VerificationStatus.REJECTED)
        self.assertTrue(self.organization.is_active)
        self.assertIsNotNone(self.organization.reviewed_at)
        self.assertEqual(self.organization.reviewed_by, self.admin_user)

        self.model_admin.suspend_organizations(
            self.action_request(), User.objects.filter(pk=self.organization.pk)
        )
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.verification_status, VerificationStatus.SUSPENDED)
        self.assertFalse(self.organization.is_active)
        self.assertEqual(self.organization.reviewed_by, self.admin_user)

    def test_admin_cannot_edit_verification_status_without_audited_action(self):
        request = self.action_request()
        readonly = self.model_admin.get_readonly_fields(request, self.organization)
        self.assertIn("verification_status", readonly)
        self.assertIn("reviewed_at", readonly)
        self.assertIn("reviewed_by", readonly)
