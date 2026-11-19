from decimal import Decimal

from .models import Collection, RecyclingProfile, VerificationStatus


KG_PER_TON = Decimal("1000")
ACTIVE_ALLOCATION_STATUSES = (
    Collection.Status.REQUESTED,
    Collection.Status.ACCEPTED,
    Collection.Status.SCHEDULED,
)


def service_area_matches(profile, city):
    """Match a pickup city against the partner's configured service area."""
    city = (city or "").strip().casefold()
    area = (profile.service_area or "").strip().casefold()
    if not city or not area:
        return False
    if city in area:
        return True
    return any(term in area for term in ("nationwide", "all regions", "all districts"))


def capacity_available_kg(profile, pending_load_kg=Decimal("0")):
    """Return remaining capacity in kg, or None when the partner is flexible."""
    maximum = profile.maximum_capacity
    unit = profile.capacity_unit
    if maximum is None:
        maximum = profile.capacity_kg_per_month
        unit = RecyclingProfile.CapacityUnit.KILOGRAM
    if maximum is None:
        return None

    multiplier = KG_PER_TON if unit == RecyclingProfile.CapacityUnit.TON else Decimal("1")
    allocated = (profile.current_allocated_load or Decimal("0")) * multiplier
    return (maximum * multiplier) - allocated - (pending_load_kg or Decimal("0"))


def partner_is_eligible(profile, listing, pending_load_kg=Decimal("0")):
    """Check every server-side requirement before a partner can be selected."""
    if (
        not profile.user.is_active
        or profile.user.verification_status != VerificationStatus.VERIFIED
        or not profile.collection_available
    ):
        return False
    if listing.paper_type not in (profile.accepted_paper_types or []):
        return False
    if not service_area_matches(profile, listing.pickup_city):
        return False
    available_kg = capacity_available_kg(profile, pending_load_kg)
    return available_kg is None or available_kg >= listing.quantity_kg


def get_recommended_partners(listing):
    """Return verified partners eligible for this listing, ranked with reasons."""
    partners = (
        RecyclingProfile.objects.filter(
            user__verification_status=VerificationStatus.VERIFIED,
            user__is_active=True,
            collection_available=True,
        )
        .select_related("user")
        .prefetch_related("collections__listing")
    )
    recommendations = []

    for partner in partners:
        pending_load = sum(
            (collection.listing.quantity_kg for collection in partner.collections.all()
             if collection.status in ACTIVE_ALLOCATION_STATUSES),
            Decimal("0"),
        )
        if not partner_is_eligible(partner, listing, pending_load):
            continue

        capacity = capacity_available_kg(partner, pending_load)
        category_label = listing.get_paper_type_display()
        area_label = listing.pickup_city
        if capacity is None:
            capacity_reason = f"✓ Capacity (Flexible kg/mo) covers listing"
        elif partner.maximum_capacity is None and not pending_load and partner.current_allocated_load == 0:
            capacity_reason = f"✓ Capacity ({partner.capacity_kg_per_month} kg/mo) covers listing"
        else:
            capacity_reason = f"✓ Capacity ({capacity} kg available) covers listing"
        location_score = 30 if (listing.pickup_city or "").casefold() in (partner.service_area or "").casefold() else 15
        match_score = min(98, 40 + 30 + location_score)
        recommendations.append({
            "partner": partner,
            "match_score": match_score,
            "available_capacity_kg": capacity,
            "match_reasons": [
                f"✓ Accepts {category_label}",
                capacity_reason,
                f"✓ Services {area_label}",
                "✓ Verified recycling partner",
            ],
        })

    recommendations.sort(key=lambda item: item["partner"].user.organization_name.casefold())
    return recommendations
