from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from PIL import Image

from .decorators import partner_profile_required, role_required
from .forms import (
    CollectionAcceptForm,
    CollectionCompleteForm,
    CollectionRejectForm,
    CollectionScheduleForm,
    EducationalInstitutionProfileForm,
    PartnerDirectoryFilterForm,
    RecyclingProfileForm,
    RegistrationForm,
)
from .listing_forms import PaperListingForm
from .matching import ACTIVE_ALLOCATION_STATUSES, get_recommended_partners, partner_is_eligible, capacity_available_kg
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
from ml_engine.services import forecast_institution, get_live_bulk_aggregation_recommendations


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            # The case-insensitive uniqueness check in the form can race with
            # another registration. Convert that database conflict into the
            # same field-level error instead of returning a server error.
            email = form.cleaned_data.get("email", "")
            if not User.objects.filter(email__iexact=email).exists():
                raise
            form.add_error("email", "An account with this email address already exists.")
        else:
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
    active_collections = Collection.objects.filter(
        listing=OuterRef("pk"),
        status__in=ACTIVE_ALLOCATION_STATUSES,
    )
    non_cancelled_collections = Collection.objects.filter(
        listing=OuterRef("pk"),
    ).exclude(status=Collection.Status.CANCELLED)
    listings = (
        PaperListing.objects.filter(institution=institution)
        .prefetch_related("collections__partner__user")
        .annotate(has_collection=Exists(active_collections))
        .annotate(has_collection_activity=Exists(non_cancelled_collections))
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
            "forecast_summary": forecast_institution(institution, weeks=4),
        },
    )


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
@require_http_methods(["GET", "POST"])
def edit_institution_profile(request):
    institution, _ = EducationalInstitution.objects.get_or_create(user=request.user)
    form = EducationalInstitutionProfileForm(request.POST or None, instance=institution)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Institution location and forecast profile saved.")
        return redirect("accounts:institution_dashboard")
    return render(request, "accounts/institution_profile_form.html", {"form": form})


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
def bulk_aggregation_dashboard(request):
    opportunities = get_live_bulk_aggregation_recommendations()
    return render(request, "accounts/bulk_aggregation.html", {"opportunities": opportunities})


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
@require_http_methods(["GET", "POST"])
def create_listing(request):
    institution = get_object_or_404(EducationalInstitution, user=request.user)
    form = PaperListingForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        listing = form.save(commit=False)
        listing.institution = institution
        listing.status = (
            PaperListing.Status.DRAFT
            if request.POST.get("listing_action") == "draft"
            else PaperListing.Status.AVAILABLE
        )
        listing.save()
        if listing.status == PaperListing.Status.DRAFT:
            messages.success(request, "Your paper listing has been saved as a draft.")
        else:
            messages.success(request, "Your paper listing is now available to recycling partners.")
        return redirect("accounts:institution_dashboard")
    return render(request, "accounts/listing_form.html", {"form": form, "page_title": "Create a paper listing"})


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
@require_http_methods(["GET", "POST"])
def edit_listing(request, listing_id):
    institution = get_object_or_404(EducationalInstitution, user=request.user)
    listing = get_object_or_404(PaperListing, pk=listing_id, institution=institution)
    if request.method == "GET":
        has_non_cancelled_collection = listing.collections.exclude(
            status=Collection.Status.CANCELLED
        ).exists()
        if (
            listing.status not in (PaperListing.Status.DRAFT, PaperListing.Status.AVAILABLE)
            or has_non_cancelled_collection
        ):
            messages.error(request, "This listing cannot be edited after a non-cancelled collection request exists.")
            return redirect("accounts:institution_dashboard")
    form = PaperListingForm(request.POST or None, request.FILES or None, instance=listing)
    if request.method == "POST":
        with transaction.atomic():
            listing = get_object_or_404(
                PaperListing.objects.select_for_update(),
                pk=listing_id,
                institution=institution,
            )
            has_non_cancelled_collection = listing.collections.exclude(
                status=Collection.Status.CANCELLED
            ).exists()
            if (
                listing.status not in (PaperListing.Status.DRAFT, PaperListing.Status.AVAILABLE)
                or has_non_cancelled_collection
            ):
                messages.error(request, "This listing cannot be edited after a non-cancelled collection request exists.")
                return redirect("accounts:institution_dashboard")

            form = PaperListingForm(request.POST, request.FILES, instance=listing)
            if form.is_valid():
                listing = form.save(commit=False)
                action = request.POST.get("listing_action")
                if action == "draft":
                    listing.status = PaperListing.Status.DRAFT
                elif action == "publish":
                    listing.status = PaperListing.Status.AVAILABLE
                listing.save()
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
    with transaction.atomic():
        listing = get_object_or_404(
            PaperListing.objects.select_for_update(),
            pk=listing_id,
            institution=institution,
        )
        has_non_cancelled_collection = listing.collections.exclude(
            status=Collection.Status.CANCELLED
        ).exists()
        if listing.status not in (PaperListing.Status.DRAFT, PaperListing.Status.AVAILABLE):
            messages.error(request, "Only draft or available listings can be withdrawn.")
        elif has_non_cancelled_collection:
            messages.error(request, "This listing cannot be withdrawn after a non-cancelled collection request exists.")
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
    available_listings = (
        PaperListing.objects.filter(status=PaperListing.Status.AVAILABLE)
        .select_related("institution__user")
        .order_by("-created_at")
    )
    total_requests = incoming_collections.count()
    pending_requests = incoming_collections.filter(status=Collection.Status.REQUESTED).count()
    return render(
        request,
        "accounts/partner_dashboard.html",
        {
            "profile": profile,
            "incoming_collections": incoming_collections,
            "available_listings": available_listings,
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
    has_collection = listing.collections.filter(status__in=ACTIVE_ALLOCATION_STATUSES).exists()
    if listing.status != PaperListing.Status.AVAILABLE or has_collection:
        messages.error(request, "Recommendations are only available for listings currently open for collection.")
        return redirect("accounts:institution_dashboard")
    recommendations = get_recommended_partners(listing)
    ranking_method = (
        "pytorch" if recommendations and all(item.get("ai_relevance") is not None for item in recommendations)
        else "rules"
    )
    return render(
        request,
        "accounts/listing_recommendations.html",
        {
            "listing": listing,
            "recommendations": recommendations,
            "ranking_method": ranking_method,
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
        has_active_collection = listing.collections.filter(status__in=ACTIVE_ALLOCATION_STATUSES).exists()
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
        collection = Collection.objects.create(
            listing=listing,
            partner=partner,
            status=Collection.Status.REQUESTED,
            estimated_quantity_kg=listing.quantity_kg,
            notes=request.POST.get("notes", "").strip(),
        )
        listing.status = PaperListing.Status.RESERVED
        listing.save(update_fields=["status", "updated_at"])

    messages.success(request, f"Collection request #{collection.pk} sent to {partner.user.organization_name}.")
    return redirect("accounts:institution_dashboard")


@login_required
def collection_detail(request, collection_id):
    """View details, status tracker, and quantity tracking for a collection."""
    collection = get_object_or_404(
        Collection.objects.select_related(
            "listing__institution__user",
            "partner__user",
            "transaction",
        ),
        pk=collection_id,
    )
    is_owner_institution = (
        request.user.role == UserRole.EDUCATIONAL_INSTITUTION
        and collection.listing.institution.user_id == request.user.id
    )
    is_assigned_partner = (
        request.user.role == UserRole.RECYCLING_PARTNER
        and collection.partner.user_id == request.user.id
    )
    if not (is_owner_institution or is_assigned_partner or request.user.is_superuser):
        return render(request, "403.html", status=403)

    return render(
        request,
        "accounts/collection_detail.html",
        {
            "collection": collection,
            "listing": collection.listing,
            "is_owner_institution": is_owner_institution,
            "is_assigned_partner": is_assigned_partner,
            "accept_form": CollectionAcceptForm(),
            "reject_form": CollectionRejectForm(),
            "schedule_form": CollectionScheduleForm(),
            "complete_form": CollectionCompleteForm(),
        },
    )


@role_required(UserRole.RECYCLING_PARTNER)
@require_POST
def partner_accept_collection(request, collection_id):
    """Partner accepts a requested collection."""
    form = CollectionAcceptForm(request.POST)
    with transaction.atomic():
        collection = get_object_or_404(
            Collection.objects.select_for_update(),
            pk=collection_id,
            partner__user=request.user,
        )
        if collection.status != Collection.Status.REQUESTED:
            messages.error(request, "This collection request is not in pending requested status.")
            return redirect("accounts:collection_detail", collection_id=collection.pk)
        collection.status = Collection.Status.ACCEPTED
        if form.is_valid() and form.cleaned_data.get("notes"):
            note = form.cleaned_data["notes"].strip()
            collection.notes = f"{collection.notes}\n[Partner acceptance]: {note}".strip()
        collection.save()

    messages.success(request, f"Collection #{collection.pk} has been accepted. You can now schedule pickup.")
    return redirect("accounts:collection_detail", collection_id=collection.pk)


@role_required(UserRole.RECYCLING_PARTNER)
@require_POST
def partner_reject_collection(request, collection_id):
    """Partner rejects a requested collection and releases listing back to available."""
    form = CollectionRejectForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please provide a valid reason for rejecting this collection request.")
        return redirect("accounts:collection_detail", collection_id=collection_id)

    with transaction.atomic():
        collection = get_object_or_404(
            Collection.objects.select_for_update().select_related("listing"),
            pk=collection_id,
            partner__user=request.user,
        )
        if collection.status != Collection.Status.REQUESTED:
            messages.error(request, "Only pending collection requests can be rejected.")
            return redirect("accounts:collection_detail", collection_id=collection.pk)
        collection.status = Collection.Status.REJECTED
        collection.rejection_reason = form.cleaned_data["rejection_reason"].strip()
        collection.save(update_fields=["status", "rejection_reason"])

        listing = PaperListing.objects.select_for_update().get(pk=collection.listing_id)
        if not listing.collections.filter(status__in=ACTIVE_ALLOCATION_STATUSES).exists():
            listing.status = PaperListing.Status.AVAILABLE
            listing.save(update_fields=["status", "updated_at"])

    messages.info(request, f"Collection #{collection.pk} was rejected. The paper listing has been released back to available status.")
    return redirect("accounts:partner_dashboard")


@role_required(UserRole.RECYCLING_PARTNER)
@require_POST
def partner_schedule_collection(request, collection_id):
    """Partner schedules the pickup date and time."""
    form = CollectionScheduleForm(request.POST)
    if not form.is_valid():
        for error_list in form.errors.values():
            for error in error_list:
                messages.error(request, error)
        return redirect("accounts:collection_detail", collection_id=collection_id)

    with transaction.atomic():
        collection = get_object_or_404(
            Collection.objects.select_for_update(),
            pk=collection_id,
            partner__user=request.user,
        )
        if collection.status not in (Collection.Status.ACCEPTED, Collection.Status.SCHEDULED):
            messages.error(request, "Accept the collection request before scheduling pickup.")
            return redirect("accounts:collection_detail", collection_id=collection.pk)
        collection.scheduled_for = form.cleaned_data["scheduled_for"]
        collection.status = Collection.Status.SCHEDULED
        if form.cleaned_data.get("notes"):
            note = form.cleaned_data["notes"].strip()
            collection.notes = f"{collection.notes}\n[Scheduled pickup note]: {note}".strip()
        collection.save()

    messages.success(request, f"Collection #{collection.pk} scheduled for {collection.scheduled_for.strftime('%b %d, %Y at %I:%M %p')}.")
    return redirect("accounts:collection_detail", collection_id=collection.pk)


@role_required(UserRole.RECYCLING_PARTNER)
@require_POST
def partner_complete_collection(request, collection_id):
    """Partner records final collected quantity and marks collection complete."""
    form = CollectionCompleteForm(request.POST)
    if not form.is_valid():
        for error_list in form.errors.values():
            for error in error_list:
                messages.error(request, error)
        return redirect("accounts:collection_detail", collection_id=collection_id)

    final_qty = form.cleaned_data["final_collected_quantity_kg"]
    notes = form.cleaned_data.get("notes", "").strip()

    with transaction.atomic():
        collection = get_object_or_404(
            Collection.objects.select_for_update().select_related("listing"),
            pk=collection_id,
            partner__user=request.user,
        )
        if collection.status != Collection.Status.SCHEDULED:
            messages.error(request, "Schedule pickup before recording a completed collection.")
            return redirect("accounts:collection_detail", collection_id=collection.pk)
        collection.final_collected_quantity_kg = final_qty
        collection.status = Collection.Status.COLLECTED
        collection.collected_at = timezone.now()
        if notes:
            collection.notes = f"{collection.notes}\n[Collection completion]: {notes}".strip()
        collection.save()

        listing = PaperListing.objects.select_for_update().get(pk=collection.listing_id)
        listing.status = PaperListing.Status.COMPLETED
        listing.save(update_fields=["status", "updated_at"])

        ref = f"TXN-{timezone.now().strftime('%Y%m%d')}-{collection.pk:05d}"
        Transaction.objects.update_or_create(
            collection=collection,
            defaults={
                "quantity_kg": final_qty,
                "completed_at": timezone.now(),
                "reference": ref,
                "notes": notes,
            },
        )

    messages.success(
        request,
        f"Collection #{collection.pk} recorded as completed! Final quantity: {final_qty} kg (Estimated: {collection.estimated_quantity} kg).",
    )
    return redirect("accounts:collection_detail", collection_id=collection.pk)


@role_required(UserRole.EDUCATIONAL_INSTITUTION)
@require_POST
def institution_cancel_collection(request, collection_id):
    """Institution cancels a collection request before it is accepted/scheduled."""
    with transaction.atomic():
        collection = get_object_or_404(
            Collection.objects.select_for_update().select_related("listing"),
            pk=collection_id,
            listing__institution__user=request.user,
        )
        if collection.status != Collection.Status.REQUESTED:
            messages.error(request, "You can only cancel collection requests that are still pending acceptance.")
            return redirect("accounts:collection_detail", collection_id=collection.pk)
        collection.status = Collection.Status.CANCELLED
        collection.notes = f"{collection.notes}\n[Cancelled by institution on {timezone.now().strftime('%Y-%m-%d %H:%M')}]".strip()
        collection.save(update_fields=["status", "notes"])

        listing = PaperListing.objects.select_for_update().get(pk=collection.listing_id)
        if not listing.collections.filter(status__in=ACTIVE_ALLOCATION_STATUSES).exists():
            listing.status = PaperListing.Status.AVAILABLE
            listing.save(update_fields=["status", "updated_at"])

    messages.info(request, f"Collection request #{collection.pk} was cancelled. Your listing is now available again.")
    return redirect("accounts:institution_dashboard")


@login_required
def transaction_history(request):
    """
    FR-11: Transaction history management for completed recycling activities.
    Scoped by the current user's role (Institution or Partner).
    """
    from .impact import calculate_impact_metrics

    if request.user.role == UserRole.EDUCATIONAL_INSTITUTION:
        txns = Transaction.objects.filter(
            collection__listing__institution__user=request.user
        ).select_related(
            "collection__listing__institution__user",
            "collection__partner__user",
        ).order_by("-completed_at")
    elif request.user.role == UserRole.RECYCLING_PARTNER:
        txns = Transaction.objects.filter(
            collection__partner__user=request.user
        ).select_related(
            "collection__listing__institution__user",
            "collection__partner__user",
        ).order_by("-completed_at")
    elif request.user.is_superuser:
        txns = Transaction.objects.all().select_related(
            "collection__listing__institution__user",
            "collection__partner__user",
        ).order_by("-completed_at")
    else:
        return render(request, "403.html", status=403)

    total_weight = txns.aggregate(total=Sum("quantity_kg"))["total"] or Decimal("0")
    total_impact = calculate_impact_metrics(total_weight)

    return render(
        request,
        "accounts/transaction_history.html",
        {
            "transactions": txns,
            "total_weight": total_weight,
            "total_impact": total_impact,
            "transaction_count": txns.count(),
        },
    )


@login_required
def transaction_detail(request, transaction_id):
    """
    Detailed transaction view with collection context and impact breakdown.
    """
    txn = get_object_or_404(
        Transaction.objects.select_related(
            "collection__listing__institution__user",
            "collection__partner__user",
        ),
        pk=transaction_id,
    )
    is_owner_institution = (
        request.user.role == UserRole.EDUCATIONAL_INSTITUTION
        and txn.collection.listing.institution.user_id == request.user.id
    )
    is_assigned_partner = (
        request.user.role == UserRole.RECYCLING_PARTNER
        and txn.collection.partner.user_id == request.user.id
    )
    if not (is_owner_institution or is_assigned_partner or request.user.is_superuser):
        return render(request, "403.html", status=403)

    return render(
        request,
        "accounts/transaction_detail.html",
        {
            "transaction": txn,
            "collection": txn.collection,
            "listing": txn.collection.listing,
            "impact": txn.impact_metrics,
            "is_owner_institution": is_owner_institution,
            "is_assigned_partner": is_assigned_partner,
        },
    )


@login_required
def digital_record_view(request, transaction_id):
    """
    FR-12: Digital recycling certificate / verifiable impact record.
    Clean, print-friendly and formal digital record of completed recycling activity.
    """
    txn = get_object_or_404(
        Transaction.objects.select_related(
            "collection__listing__institution__user",
            "collection__partner__user",
        ),
        pk=transaction_id,
    )
    is_owner_institution = (
        request.user.role == UserRole.EDUCATIONAL_INSTITUTION
        and txn.collection.listing.institution.user_id == request.user.id
    )
    is_assigned_partner = (
        request.user.role == UserRole.RECYCLING_PARTNER
        and txn.collection.partner.user_id == request.user.id
    )
    if not (is_owner_institution or is_assigned_partner or request.user.is_superuser):
        return render(request, "403.html", status=403)

    return render(
        request,
        "accounts/digital_record.html",
        {
            "transaction": txn,
            "collection": txn.collection,
            "listing": txn.collection.listing,
            "institution": txn.collection.listing.institution,
            "partner": txn.collection.partner,
            "impact": txn.impact_metrics,
        },
    )


def permission_denied(request, exception=None):

    return render(request, "403.html", status=403)

