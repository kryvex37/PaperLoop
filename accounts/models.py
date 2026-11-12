from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class UserRole(models.TextChoices):
    EDUCATIONAL_INSTITUTION = "institution", "Educational Institution"
    RECYCLING_PARTNER = "partner", "Recycling/Collection Partner"
    PLATFORM_ADMIN = "platform_admin", "Platform Administrator"


PUBLIC_REGISTRATION_ROLES = (
    UserRole.EDUCATIONAL_INSTITUTION,
    UserRole.RECYCLING_PARTNER,
)


class UserManager(BaseUserManager):
    """Create users with normalized email addresses and securely hashed passwords."""

    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", UserRole.PLATFORM_ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        if extra_fields.get("role") != UserRole.PLATFORM_ADMIN:
            raise ValueError("A superuser must have the platform administrator role.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """PaperLoop organization account with a role selected at registration."""

    username = None
    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=24, choices=UserRole.choices)
    organization_name = models.CharField(max_length=180, blank=True)
    contact_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=32, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["organization_name", "email"]
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]

    def __str__(self):
        return self.organization_name or self.email

    @property
    def is_institution(self):
        return self.role == UserRole.EDUCATIONAL_INSTITUTION

    @property
    def is_recycling_partner(self):
        return self.role == UserRole.RECYCLING_PARTNER
