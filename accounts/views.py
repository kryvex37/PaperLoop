from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from PIL import Image

from .decorators import partner_profile_required, role_required
from .forms import PartnerDirectoryFilterForm, RecyclingProfileForm, RegistrationForm
from .listing_forms import PaperListingForm
from .matching import ACTIVE_ALLOCATION_STATUSES, get_recommended_partners, partner_is_eligible, capacity_available_kg
from .models import (
    Collection,
    EducationalInstitution,
    PaperListing,
    RecyclingProfile,
    UserRole,
    VerificationStatus,
)


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(
            request,
            "Your PaperLoop account has been created. You can now sign in.",
        )
        return redirect("accounts:login")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def dashboard(request):
    if request.user.is_superuser:
        return redirect("admin:index")
    if request.user.verification_status != VerificationStatus.VERIFIED:
        return render(
            request,
            "accounts/verification_pending.html",
            {"verification_status": request.user.get_verification_status_display()},
        )
    if request.user.role == UserRole.EDUCATIONAL_INSTITUTION:
        return redirect("accounts:institution_dashboard")
    if request.user.role == UserRole.RECYCLING_PARTNER:
        return redirect("accounts:partner_dashboard")
    return render(request, "accounts/access_unavailable.html", status=403)


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
def institution_dashboard(request):
    institution, _ = EducationalInstitution.objects.get_or_create(user=request.user)
    active_collections = Collection.objects.filter(listing=OuterRef("pk")).exclude(status=Collection.Status.CANCELLED)
    listings = (
        PaperListing.objects.filter(institution=institution)
        .annotate(has_collection=Exists(active_collections))
        .order_by("-created_at")
    )
    return render(
        request,
        "accounts/institution_dashboard.html",
        {
            "listings": listings,
            "listing_count": listings.count(),
            "available_count": listings.filter(status=PaperListing.Status.AVAILABLE).count(),
            "draft_count": listings.filter(status=PaperListing.Status.DRAFT).count(),
        },
    )


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
@require_http_methods(["GET", "POST"])
def create_listing(request):
    institution = get_object_or_404(EducationalInstitution, user=request.user)
    form = PaperListingForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        listing = form.save(commit=False)
        listing.institution = institution
        listing.status = PaperListing.Status.AVAILABLE
        listing.save()
        messages.success(request, "Your paper listing is now available to recycling partners.")
        return redirect("accounts:institution_dashboard")
    return render(request, "accounts/listing_form.html", {"form": form, "page_title": "Create a paper listing"})


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
@require_http_methods(["GET", "POST"])
def edit_listing(request, listing_id):
    institution = get_object_or_404(EducationalInstitution, user=request.user)
    listing = get_object_or_404(PaperListing, pk=listing_id, institution=institution)
    can_edit = listing.status in (PaperListing.Status.DRAFT, PaperListing.Status.AVAILABLE)
    has_collection = listing.collections.exclude(status=Collection.Status.CANCELLED).exists()
    if not can_edit or has_collection:
        messages.error(request, "This listing can no longer be edited after collection activity has started.")
        return redirect("accounts:institution_dashboard")
    form = PaperListingForm(request.POST or None, request.FILES or None, instance=listing)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your paper listing has been updated.")
        return redirect("accounts:institution_dashboard")
    return render(
        request,
        "accounts/listing_form.html",
        {"form": form, "listing": listing, "page_title": "Edit paper listing"},
    )


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
@require_POST
def cancel_listing(request, listing_id):
    institution = get_object_or_404(EducationalInstitution, user=request.user)
    listing = get_object_or_404(PaperListing, pk=listing_id, institution=institution)
    if listing.status not in (PaperListing.Status.DRAFT, PaperListing.Status.AVAILABLE):
        messages.error(request, "Only draft or available listings can be withdrawn.")
    elif listing.collections.exclude(status=Collection.Status.CANCELLED).exists():
        messages.error(request, "This listing cannot be withdrawn after collection activity has started.")
    else:
        listing.status = PaperListing.Status.CANCELLED
        listing.save(update_fields=("status", "updated_at"))
        messages.success(request, "Your listing has been withdrawn.")
    return redirect("accounts:institution_dashboard")


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
@never_cache
def listing_photo(request, listing_id):
    institution = get_object_or_404(EducationalInstitution, user=request.user)
    listing = get_object_or_404(PaperListing, pk=listing_id, institution=institution)
    if not listing.photo:
        raise Http404
    photo_file = listing.photo.open("rb")
    with Image.open(photo_file) as image:
        content_type = Image.MIME.get(image.format, "application/octet-stream")
    photo_file.seek(0)
    response = FileResponse(
        photo_file,
        content_type=content_type,
    )
    response["Content-Disposition"] = "inline"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@role_required(UserRole.RECYCLING_PARTNER)
def partner_dashboard(request):
    profile, _ = RecyclingProfile.objects.get_or_create(user=request.user)
    incoming_collections = (
        Collection.objects.filter(partner=profile)
        .select_related("listing__institution__user")
        .order_by("-requested_at")
    )
    total_requests = incoming_collections.count()
    pending_requests = incoming_collections.filter(status=Collection.Status.REQUESTED).count()
    return render(
        request,
        "accounts/partner_dashboard.html",
        {
            "profile": profile,
            "incoming_collections": incoming_collections,
            "total_requests": total_requests,
            "pending_requests": pending_requests,
        },
    )


@partner_profile_required
@require_http_methods(["GET", "POST"])
def edit_partner_profile(request):
    profile, _ = RecyclingProfile.objects.get_or_create(user=request.user)
    form = RecyclingProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your recycling partner profile has been updated.")
        return redirect("accounts:partner_dashboard")
    return render(
        request,
        "accounts/partner_profile_form.html",
        {"form": form, "profile": profile},
    )


@partner_profile_required
def partner_profile_detail(request):
    profile, _ = RecyclingProfile.objects.get_or_create(user=request.user)
    return render(
        request,
        "accounts/partner_profile_detail.html",
        {"profile": profile, "paper_category_choices": PaperListing.PaperCategory.choices},
    )


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
def listing_recommendations(request, listing_id):
    institution = get_object_or_404(EducationalInstitution, user=request.user)
    listing = get_object_or_404(PaperListing, pk=listing_id, institution=institution)
    has_collection = listing.collections.exclude(status=Collection.Status.CANCELLED).exists()
    if listing.status != PaperListing.Status.AVAILABLE or has_collection:
        messages.error(request, "Recommendations are only available for listings currently open for collection.")
        return redirect("accounts:institution_dashboard")
    recommendations = get_recommended_partners(listing)
    return render(
        request,
        "accounts/listing_recommendations.html",
        {
            "listing": listing,
            "recommendations": recommendations,
        },
    )


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
def partner_directory(request):
    form = PartnerDirectoryFilterForm(request.GET or None)
    partner_queryset = RecyclingProfile.objects.filter(
        user__role=UserRole.RECYCLING_PARTNER,
        user__verification_status=VerificationStatus.VERIFIED,
        user__is_active=True,
        collection_available=True,
    ).select_related("user").annotate(
        pending_load_kg=Sum(
            "collections__listing__quantity_kg",
            filter=Q(collections__status__in=ACTIVE_ALLOCATION_STATUSES),
        ),
    )
    partners = list(partner_queryset)
    for partner in partners:
        partner.available_capacity_kg = capacity_available_kg(partner, partner.pending_load_kg)
    if form.is_valid():
        filters = form.cleaned_data
        if filters["search"]:
            query = filters["search"].strip().casefold()
            partners = [p for p in partners if query in p.user.organization_name.casefold()]
        if filters["paper_type"]:
            partners = [p for p in partners if filters["paper_type"] in (p.accepted_paper_types or [])]
        if filters["service_area"]:
            partners = [p for p in partners if filters["service_area"].casefold() in (p.service_area or "").casefold()]
        if filters["quantity_kg"] is not None:
            partners = [
                p for p in partners
                if p.available_capacity_kg is None or p.available_capacity_kg >= filters["quantity_kg"]
            ]
    return render(request, "accounts/partner_directory.html", {
        "form": form,
        "partners": partners,
        "paper_category_choices": PaperListing.PaperCategory.choices,
    })


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
def partner_public_detail(request, profile_id):
    partner = get_object_or_404(
        RecyclingProfile.objects.select_related("user").annotate(
            pending_load_kg=Sum(
                "collections__listing__quantity_kg",
                filter=Q(collections__status__in=ACTIVE_ALLOCATION_STATUSES),
            ),
        ),
        pk=profile_id,
        user__role=UserRole.RECYCLING_PARTNER,
        user__verification_status=VerificationStatus.VERIFIED,
        user__is_active=True,
        collection_available=True,
    )
    partner.available_capacity_kg = capacity_available_kg(partner, partner.pending_load_kg)
    return render(request, "accounts/partner_public_detail.html", {
        "partner": partner,
        "paper_category_choices": PaperListing.PaperCategory.choices,
    })


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
@require_POST
def select_recommended_partner(request, listing_id):
    institution = get_object_or_404(EducationalInstitution, user=request.user)
    with transaction.atomic():
        listing = get_object_or_404(
            PaperListing.objects.select_for_update(),
            pk=listing_id,
            institution=institution,
        )
        has_active_collection = listing.collections.exclude(status=Collection.Status.CANCELLED).exists()
        if listing.status != PaperListing.Status.AVAILABLE or has_active_collection:
            messages.error(request, "This listing is not available for a new collection request.")
            return redirect("accounts:institution_dashboard")

        partner_id = request.POST.get("partner_id")
        try:
            partner_id = int(partner_id)
        except (TypeError, ValueError):
            partner_id = None
        partner = (
            RecyclingProfile.objects.select_for_update().select_related("user")
            .filter(pk=partner_id, user__role=UserRole.RECYCLING_PARTNER)
            .first()
        )
        if partner is None:
            messages.error(request, "Choose an available recycling partner from the matching results.")
            return redirect("accounts:listing_recommendations", listing_id=listing.pk)
        pending_load_kg = Collection.objects.filter(
            partner=partner,
            status__in=ACTIVE_ALLOCATION_STATUSES,
        ).aggregate(total=Sum("listing__quantity_kg"))["total"] or 0
        if not partner_is_eligible(partner, listing, pending_load_kg):
            messages.error(request, "This partner no longer meets the listing's category, service area, or remaining capacity requirements.")
            return redirect("accounts:listing_recommendations", listing_id=listing.pk)
        Collection.objects.create(
            listing=listing,
            partner=partner,
            status=Collection.Status.REQUESTED,
            notes=request.POST.get("notes", "").strip(),
        )
        listing.status = PaperListing.Status.RESERVED
        listing.save(update_fields=["status", "updated_at"])

    messages.success(request, f"Collection request sent to {partner.user.organization_name}.")
    return redirect("accounts:institution_dashboard")


def permission_denied(request, exception=None):
    return render(request, "403.html", status=403)
