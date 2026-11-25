from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from django.conf import settings

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
        collections = list(partner.collections.all())
        pending_load = sum(
            (collection.listing.quantity_kg for collection in collections
             if collection.status in ACTIVE_ALLOCATION_STATUSES),
            Decimal("0"),
        )
        if not partner_is_eligible(partner, listing, pending_load):
            continue

        resolved_collections = [
            collection for collection in collections
            if collection.status in (Collection.Status.COLLECTED, Collection.Status.REJECTED)
        ]
        fulfilled_count = sum(
            collection.status == Collection.Status.COLLECTED
            for collection in resolved_collections
        )
        if resolved_collections:
            fulfillment_rate = (fulfilled_count + 1) / (len(resolved_collections) + 2)
        elif partner.historical_fulfillment_rate is not None:
            fulfillment_rate = float(partner.historical_fulfillment_rate)
        else:
            fulfillment_rate = 0.5
        if resolved_collections:
            history_detail = (
                f"{fulfilled_count} of {len(resolved_collections)} resolved pickups completed; "
                f"smoothed fulfillment estimate {fulfillment_rate:.0%}"
            )
        elif partner.historical_fulfillment_rate is not None:
            history_detail = f"No resolved pickup history; stored fulfillment estimate {fulfillment_rate:.0%}"
        else:
            history_detail = "No resolved pickup history; neutral fulfillment prior used"
        history_features = {
            "historical_fulfillment_rate": fulfillment_rate,
            "history_observation_count": len(resolved_collections),
            "history_completed_count": fulfilled_count,
            "history_prior_used": not resolved_collections and partner.historical_fulfillment_rate is None,
        }

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

        # Structured factor breakdowns for clean visual rendering (FR-05/FR-08 UI polish)
        factor_breakdown = {
            "capacity": {
                "label": "Capacity Match",
                "status": "High" if capacity is None or capacity >= (listing.quantity_kg * Decimal("2")) else "Sufficient",
                "detail": f"{capacity} kg available" if capacity is not None else "Flexible monthly capacity",
                "passed": True,
            },
            "location": {
                "label": "Location & Service Area",
                "status": "In Service Area" if location_score == 30 else "Regional Coverage",
                "detail": f"Services {partner.service_area or area_label}",
                "passed": True,
            },
            "category": {
                "label": "Material Grade Acceptance",
                "status": "Verified Match",
                "detail": f"Accepts {category_label}",
                "passed": True,
            },
            "history": {
                "label": "Verification & History",
                "status": "Has completed history" if resolved_collections else "New to marketplace",
                "detail": history_detail,
                "passed": True,
            },
        }

        recommendations.append({
            "partner": partner,
            "match_score": match_score,
            "available_capacity_kg": capacity,
            "factor_breakdown": factor_breakdown,
            "history_features": history_features,
            "match_reasons": [
                f"✓ Accepts {category_label}",
                capacity_reason,
                f"✓ Services {area_label}",
                "✓ Verified recycling partner",
            ],
        })

    # Location and available capacity must be present for learned ranking.
    # Missing marketplace history, ratings, and price data use explicit neutral
    # priors so new partners can still be ranked without fabricated claims.
    feature_rows = []
    complete_features = True
    for item in recommendations:
        partner = item["partner"]
        capacity = item["available_capacity_kg"]
        listing_lat = getattr(listing, "pickup_latitude", None)
        listing_lon = getattr(listing, "pickup_longitude", None)
        if listing_lat is None:
            listing_lat = listing.institution.latitude
        if listing_lon is None:
            listing_lon = listing.institution.longitude
        partner_lat = getattr(partner, "latitude", None)
        partner_lon = getattr(partner, "longitude", None)
        coordinates = (listing_lat, listing_lon, partner_lat, partner_lon)
        if any(value is None for value in coordinates):
            complete_features = False
            break
        if not (-90 <= float(listing_lat) <= 90 and -90 <= float(partner_lat) <= 90
                and -180 <= float(listing_lon) <= 180 and -180 <= float(partner_lon) <= 180):
            complete_features = False
            break
        lat1, lon1, lat2, lon2 = map(float, (listing_lat, listing_lon, partner_lat, partner_lon))
        dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
        haversine = 2 * 6371 * asin(sqrt(sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2))
        history = item["history_features"]
        has_capacity_limit = capacity is not None and capacity > 0
        feature_rows.append({
            "distance_km": haversine,
            "capacity_utilization_ratio": (
                float(listing.quantity_kg / capacity) if has_capacity_limit else 0.0
            ),
            "paper_grade_match": 1,
            **history,
            "average_rating": float(partner.average_rating) if partner.average_rating is not None else 3.0,
            "price_competitiveness": (
                float(partner.price_competitiveness)
                if partner.price_competitiveness is not None else 1.0
            ),
            "rating_prior_used": partner.average_rating is None,
            "price_prior_used": partner.price_competitiveness is None,
            "capacity_is_flexible": not has_capacity_limit,
        })

    if complete_features and feature_rows:
        from ml_engine.inference.partner_match import PartnerMatchInference
        inference = PartnerMatchInference(settings.BASE_DIR / "ml_engine" / "artifacts" / "recycler_ranker.pt")
        ranked = inference.predict(feature_rows)
    else:
        ranked = None
    if ranked is None:
        for item in recommendations:
            item["match_factors"] = list(item["match_reasons"])
        recommendations.sort(
            key=lambda item: (
                -item["match_score"],
                item["partner"].user.organization_name.casefold(),
            )
        )
    else:
        for item, result in zip(recommendations, ranked):
            item["ai_relevance"] = round(result["score"], 4)
            item["match_factors"] = result["factors"]
        recommendations.sort(key=lambda item: (-item["ai_relevance"], item["partner"].user.organization_name.casefold()))
    return recommendations
