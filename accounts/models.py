from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F
from django.db.models.functions import Lower
from django.utils import timezone


class UserRole(models.TextChoices):
    EDUCATIONAL_INSTITUTION = "institution", "Educational Institution"
    RECYCLING_PARTNER = "partner", "Recycling/Collection Partner"
    PLATFORM_ADMIN = "platform_admin", "Platform Administrator"


class VerificationStatus(models.TextChoices):
    PENDING = "pending", "Pending review"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"


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
    verification_status = models.CharField(
        max_length=16, choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="verified_accounts",
    )
    verification_notes = models.TextField(blank=True)

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

    @property
    def is_verified_organization(self):
        return self.verification_status == VerificationStatus.VERIFIED and self.is_active


class EducationalInstitution(models.Model):
    """Verified institution account and its organization-specific details."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="institution")
    institution_type = models.CharField(max_length=80, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    student_count = models.PositiveIntegerField(default=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.organization_name


class RecyclingProfile(models.Model):
    """Capabilities and service area for a recycling/collection partner."""

    class CapacityUnit(models.TextChoices):
        KILOGRAM = "kg", "Kilograms"
        TON = "ton", "Metric tons"

    class CapacityPeriod(models.TextChoices):
        DAY = "day", "per day"
        WEEK = "week", "per week"
        MONTH = "month", "per month"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="recycling_profile")
    accepted_paper_types = models.JSONField(default=list, blank=True)
    service_area = models.TextField(blank=True)
    capacity_kg_per_month = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    maximum_capacity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    current_allocated_load = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    capacity_unit = models.CharField(max_length=8, choices=CapacityUnit.choices, default=CapacityUnit.KILOGRAM)
    capacity_period = models.CharField(max_length=8, choices=CapacityPeriod.choices, default=CapacityPeriod.MONTH)
    collection_available = models.BooleanField(default=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    historical_fulfillment_rate = models.FloatField(null=True, blank=True, default=None)
    average_rating = models.FloatField(null=True, blank=True, default=None)
    price_competitiveness = models.FloatField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(maximum_capacity__isnull=True) | models.Q(current_allocated_load__lte=F("maximum_capacity"))),
                name="recycler_allocated_within_capacity",
            ),
        ]

    @property
    def available_capacity(self):
        if self.maximum_capacity is None:
            return None
        return self.maximum_capacity - self.current_allocated_load

    def __str__(self):
        return f"Recycling profile: {self.user.organization_name}"


class PaperListing(models.Model):
    class PaperCategory(models.TextChoices):
        OFFICE = "office_paper", "Office paper"
        BOOKS = "books_notebooks", "Books and notebooks"
        NEWS = "newspapers_magazines", "Newspapers and magazines"
        CARDBOARD = "cardboard", "Cardboard"
        MIXED = "mixed_paper", "Mixed paper"
        OTHER = "other", "Other paper"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    institution = models.ForeignKey(EducationalInstitution, on_delete=models.PROTECT, related_name="paper_listings")
    paper_type = models.CharField(max_length=80, choices=PaperCategory.choices)
    category_details = models.CharField(max_length=160, blank=True)
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)
    pickup_address = models.TextField()
    pickup_city = models.CharField(max_length=100, blank=True, null=True)
    pickup_country = models.CharField(max_length=100, blank=True, null=True)
    available_from = models.DateField(null=True, blank=True)
    available_until = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to="paper-listings/%Y/%m/", blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_kg__gt=0), name="listing_quantity_positive"),
            models.CheckConstraint(
                condition=(models.Q(available_until__isnull=True) | models.Q(available_from__isnull=True) | models.Q(available_until__gte=F("available_from"))),
                name="listing_collection_window_ordered",
            ),
        ]

    def __str__(self):
        return f"{self.paper_type} ({self.quantity_kg} kg)"


class WasteRecord(models.Model):
    """Institution weekly paper weights used for forecasts and audit history."""

    institution = models.ForeignKey(EducationalInstitution, on_delete=models.CASCADE, related_name="waste_records")
    week_start = models.DateField(db_index=True)
    paper_grade = models.CharField(max_length=80, choices=PaperListing.PaperCategory.choices)
    actual_weight_kg = models.DecimalField(max_digits=12, decimal_places=2)
    is_synthetic = models.BooleanField(default=False, db_index=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-week_start", "institution_id", "paper_grade")
        constraints = [
            models.UniqueConstraint(fields=("institution", "week_start", "paper_grade"),
                                    name="unique_institution_week_paper_grade"),
            models.CheckConstraint(condition=models.Q(actual_weight_kg__gt=0),
                                   name="waste_record_weight_positive"),
        ]

    def __str__(self):
        return f"{self.institution} {self.paper_grade}: {self.actual_weight_kg} kg ({self.week_start})"


class Collection(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        ACCEPTED = "accepted", "Accepted"
        SCHEDULED = "scheduled", "Scheduled"
        COLLECTED = "collected", "Collected"
        CANCELLED = "cancelled", "Cancelled"

    listing = models.ForeignKey(PaperListing, on_delete=models.PROTECT, related_name="collections")
    partner = models.ForeignKey(RecyclingProfile, on_delete=models.PROTECT, related_name="collections")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-requested_at",)
        constraints = [models.UniqueConstraint(fields=("listing",), condition=models.Q(status__in=("requested", "accepted", "scheduled")), name="one_active_collection_per_listing")]

    def __str__(self):
        return f"Collection #{self.pk}: {self.listing}"


class Transaction(models.Model):
    """Record of a completed paper transfer; payment details are future scope."""

    collection = models.OneToOneField(Collection, on_delete=models.PROTECT, related_name="transaction")
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=2)
    completed_at = models.DateTimeField(default=timezone.now)
    reference = models.CharField(max_length=100, blank=True, unique=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-completed_at",)

    def __str__(self):
        return f"Transaction #{self.pk} ({self.quantity_kg} kg)"
