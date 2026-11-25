from django.test import TestCase
from django.urls import reverse

from accounts.models import User, UserRole, VerificationStatus


class ThemeSystemTemplateTests(TestCase):
    def assert_shared_theme_shell(self, response):
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('data-theme-switcher', content)
        self.assertIn('data-theme-option="light"', content)
        self.assertIn('data-theme-option="dark"', content)
        self.assertIn('data-theme-option="forest"', content)
        self.assertIn('data-theme-option="system"', content)
        self.assertIn("paperloop-themes.css", content)
        self.assertIn("theme-system.js", content)
        self.assertIn('src="/static/img/paperloop-logo.webp"', content)
        logo = content.index('src="/static/img/paperloop-logo.webp"')
        brand = content.index("PaperLoop", logo)
        self.assertLess(logo, brand)

    def test_public_and_auth_pages_have_shared_theme_switcher(self):
        for route in ("accounts:landing", "accounts:about", "accounts:login", "accounts:register", "accounts:password_reset"):
            with self.subTest(route=route):
                self.assert_shared_theme_shell(self.client.get(reverse(route)))

    def test_institution_and_recycler_shells_have_switcher_and_settings_choices(self):
        cases = (
            (UserRole.EDUCATIONAL_INSTITUTION, "institution-theme@example.test", "accounts:institution_dashboard", "accounts:institution_profile"),
            (UserRole.RECYCLING_PARTNER, "recycler-theme@example.test", "accounts:partner_dashboard", "accounts:partner_profile"),
        )
        for role, email, dashboard, settings in cases:
            user = User.objects.create_user(
                email=email,
                password="safe-test-password",
                role=role,
                organization_name="Theme Test Organization",
                verification_status=VerificationStatus.VERIFIED,
            )
            self.client.force_login(user)
            with self.subTest(role=role, page="dashboard"):
                self.assert_shared_theme_shell(self.client.get(reverse(dashboard)))
            with self.subTest(role=role, page="settings"):
                response = self.client.get(reverse(settings))
                self.assert_shared_theme_shell(response)
                self.assertContains(response, "pl-theme-switcher-settings")
            self.client.logout()

    def test_admin_shell_has_theme_switcher(self):
        admin = User.objects.create_superuser(email="theme-admin@example.test", password="safe-test-password")
        self.client.force_login(admin)
        self.assert_shared_theme_shell(self.client.get(reverse("admin:index")))
