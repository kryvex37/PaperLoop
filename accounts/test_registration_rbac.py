from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import (
    EducationalInstitution,
    PUBLIC_REGISTRATION_ROLES,
    RecyclingProfile,
    UserRole,
    VerificationStatus,
)

User = get_user_model()


class RegistrationFR01Tests(TestCase):
    def setUp(self):
        self.client = Client()

    def registration_data(self, role, email):
        return {
            "role": role,
            "organization_name": "PaperLoop Pilot School",
            "contact_name": "Amina Rahman",
            "email": email,
            "phone": "+8801700000000",
            "password1": "Safe-PaperLoop-Pass-2026!",
            "password2": "Safe-PaperLoop-Pass-2026!",
        }

    def test_each_public_role_registers_pending_account_with_matching_profile(self):
        for role in PUBLIC_REGISTRATION_ROLES:
            with self.subTest(role=role):
                email = f"{role.value}@example.test"
                response = self.client.post(
                    reverse("accounts:register"),
                    self.registration_data(role, email),
                )
                self.assertRedirects(response, reverse("accounts:login"))
                user = User.objects.get(email=email)
                self.assertEqual(user.role, role)
                self.assertEqual(user.verification_status, VerificationStatus.PENDING)
                self.assertTrue(user.is_active)
                self.assertTrue(user.check_password("Safe-PaperLoop-Pass-2026!"))
                if role == UserRole.EDUCATIONAL_INSTITUTION:
                    self.assertTrue(EducationalInstitution.objects.filter(user=user).exists())
                else:
                    self.assertTrue(RecyclingProfile.objects.filter(user=user).exists())

    def test_duplicate_email_is_reported_without_creating_another_account(self):
        User.objects.create_user(
            email="existing@example.test",
            password="testpassword123",
            role=UserRole.EDUCATIONAL_INSTITUTION,
        )
        data = self.registration_data(
            UserRole.RECYCLING_PARTNER, "EXISTING@example.test"
        )

        response = self.client.post(reverse("accounts:register"), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email address already exists.")
        self.assertEqual(User.objects.filter(email__iexact="existing@example.test").count(), 1)

    @patch("accounts.views.RegistrationForm.save", autospec=True)
    def test_duplicate_created_after_validation_is_reported_as_a_field_error(self, save):
        def simulate_competing_registration(form):
            User.objects.create_user(
                email=form.cleaned_data["email"],
                password="another-safe-password",
                role=form.cleaned_data["role"],
            )
            raise IntegrityError("simulated concurrent duplicate")

        save.side_effect = simulate_competing_registration
        response = self.client.post(
            reverse("accounts:register"),
            self.registration_data(UserRole.EDUCATIONAL_INSTITUTION, "race@example.test"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email address already exists.")

    def test_platform_admin_role_cannot_be_created_through_public_registration(self):
        response = self.client.post(
            reverse("accounts:register"),
            self.registration_data(UserRole.PLATFORM_ADMIN, "admin-signup@example.test"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="admin-signup@example.test").exists())
