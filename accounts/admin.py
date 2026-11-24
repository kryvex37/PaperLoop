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
    WasteRecord,
)

# Custom PaperLoop Admin Branding & Polish
admin.site.site_header = "PaperLoop Administration"
admin.site.site_title = "PaperLoop Admin Portal"
admin.site.index_title = "Marketplace Overview & Verification Operations"



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
        ("Verification", {"fields": (
            "verification_status", "verified_at", "verified_by", "reviewed_at", "reviewed_by", "verification_notes",
        )}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": (
        "email", "organization_name", "contact_name", "role", "password1", "password2",
    )}),)
    # Keep lifecycle changes on the audited bulk actions. Editing the status
    # directly would allow a verified account with no verifier or timestamp.
    readonly_fields = (
        "last_login", "date_joined", "verification_status", "verified_at", "verified_by",
        "reviewed_at", "reviewed_by",
    )
    actions = ("verify_organizations", "reject_organizations", "suspend_organizations")

    @admin.action(description="Verify selected organizations")
    def verify_organizations(self, request, queryset):
        reviewed_at = timezone.now()
        count = queryset.filter(role__in=(UserRole.EDUCATIONAL_INSTITUTION, UserRole.RECYCLING_PARTNER)).update(
            verification_status=VerificationStatus.VERIFIED,
            verified_at=reviewed_at,
            verified_by=request.user,
            reviewed_at=reviewed_at,
            reviewed_by=request.user,
            is_active=True,
        )
        self.message_user(request, f"Verified {count} organization account(s).", messages.SUCCESS)

    @admin.action(description="Reject selected organizations")
    def reject_organizations(self, request, queryset):
        reviewed_at = timezone.now()
        count = queryset.filter(role__in=(UserRole.EDUCATIONAL_INSTITUTION, UserRole.RECYCLING_PARTNER)).update(
            verification_status=VerificationStatus.REJECTED,
            reviewed_at=reviewed_at,
            reviewed_by=request.user,
            is_active=True,
        )
        self.message_user(request, f"Rejected {count} organization account(s).", messages.SUCCESS)

    @admin.action(description="Suspend selected organizations")
    def suspend_organizations(self, request, queryset):
        reviewed_at = timezone.now()
        count = queryset.filter(role__in=(UserRole.EDUCATIONAL_INSTITUTION, UserRole.RECYCLING_PARTNER)).update(
            verification_status=VerificationStatus.SUSPENDED,
            reviewed_at=reviewed_at,
            reviewed_by=request.user,
            is_active=False,
        )
        self.message_user(request, f"Suspended {count} organization account(s).", messages.WARNING)


@admin.register(EducationalInstitution)
class EducationalInstitutionAdmin(admin.ModelAdmin):
    list_display = ("user", "institution_type", "registration_number", "city", "country", "student_count", "latitude", "longitude")
    search_fields = ("user__organization_name", "user__email", "registration_number")


@admin.register(RecyclingProfile)
class RecyclingProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "collection_available", "capacity_kg_per_month", "latitude", "longitude")
    search_fields = ("user__organization_name", "user__email", "service_area")


@admin.register(PaperListing)
class PaperListingAdmin(admin.ModelAdmin):
    list_display = ("paper_type", "institution", "quantity_kg", "status", "created_at")
    list_filter = ("status", "paper_type")
    search_fields = ("institution__user__organization_name", "paper_type")


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("listing", "partner", "status", "estimated_quantity_display", "final_collected_quantity_kg", "requested_at", "scheduled_for", "collected_at")
    list_filter = ("status",)
    search_fields = ("listing__institution__user__organization_name", "partner__user__organization_name", "notes", "rejection_reason")

    def estimated_quantity_display(self, obj):
        return f"{obj.estimated_quantity} kg" if obj.estimated_quantity else "—"
    estimated_quantity_display.short_description = "Est. Quantity"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("collection", "quantity_kg", "completed_at", "reference")


@admin.register(WasteRecord)
class WasteRecordAdmin(admin.ModelAdmin):
    list_display = ("institution", "week_start", "paper_grade", "actual_weight_kg", "is_synthetic")
    list_filter = ("paper_grade", "is_synthetic", "week_start")
    search_fields = ("institution__user__organization_name",)
