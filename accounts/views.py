from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from PIL import Image

from .decorators import role_required
from .listing_forms import PaperListingForm
from .forms import RegistrationForm
from .models import Collection, EducationalInstitution, PaperListing, UserRole, VerificationStatus


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
    return render(request, "accounts/partner_dashboard.html")


def permission_denied(request, exception=None):
    return render(request, "403.html", status=403)
