from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils import timezone

from .forms import AdminUserCreationForm
from .models import (
    Collection,
    EducationalInstitution,
    PaperListing,
    RecyclingProfile,
    Transaction,
    User,
    UserRole,
    VerificationStatus,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = AdminUserCreationForm
    ordering = ("email",)
    list_display = ("email", "organization_name", "role", "verification_status", "is_active", "is_staff")
    list_filter = ("role", "verification_status", "is_active", "is_staff")
    search_fields = ("email", "organization_name", "contact_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Organization", {"fields": ("role", "organization_name", "contact_name", "phone")}),
        ("Verification", {"fields": ("verification_status", "verified_at", "verified_by", "verification_notes")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": (
        "email", "organization_name", "contact_name", "role", "password1", "password2",
    )}),)
    readonly_fields = ("last_login", "date_joined", "verified_at", "verified_by")
    actions = ("verify_organizations", "reject_organizations", "suspend_organizations")

    @admin.action(description="Verify selected organizations")
    def verify_organizations(self, request, queryset):
        count = queryset.filter(role__in=(UserRole.EDUCATIONAL_INSTITUTION, UserRole.RECYCLING_PARTNER)).update(
            verification_status=VerificationStatus.VERIFIED,
            verified_at=timezone.now(),
            verified_by=request.user,
            is_active=True,
        )
        self.message_user(request, f"Verified {count} organization account(s).", messages.SUCCESS)

    @admin.action(description="Reject selected organizations")
    def reject_organizations(self, request, queryset):
        count = queryset.filter(role__in=(UserRole.EDUCATIONAL_INSTITUTION, UserRole.RECYCLING_PARTNER)).update(
            verification_status=VerificationStatus.REJECTED,
            verified_at=None,
            verified_by=request.user,
        )
        self.message_user(request, f"Rejected {count} organization account(s).", messages.SUCCESS)

    @admin.action(description="Suspend selected organizations")
    def suspend_organizations(self, request, queryset):
        count = queryset.filter(role__in=(UserRole.EDUCATIONAL_INSTITUTION, UserRole.RECYCLING_PARTNER)).update(
            verification_status=VerificationStatus.SUSPENDED,
            is_active=False,
        )
        self.message_user(request, f"Suspended {count} organization account(s).", messages.WARNING)


@admin.register(EducationalInstitution)
class EducationalInstitutionAdmin(admin.ModelAdmin):
    list_display = ("user", "institution_type", "registration_number", "city", "country")
    search_fields = ("user__organization_name", "user__email", "registration_number")


@admin.register(RecyclingProfile)
class RecyclingProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "collection_available", "capacity_kg_per_month")
    search_fields = ("user__organization_name", "user__email", "service_area")


@admin.register(PaperListing)
class PaperListingAdmin(admin.ModelAdmin):
    list_display = ("paper_type", "institution", "quantity_kg", "status", "created_at")
    list_filter = ("status", "paper_type")
    search_fields = ("institution__user__organization_name", "paper_type")


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("listing", "partner", "status", "requested_at", "scheduled_for")
    list_filter = ("status",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("collection", "quantity_kg", "completed_at", "reference")
