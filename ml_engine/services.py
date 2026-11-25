"""Backend-facing forecast and bulk aggregation service functions.

Live aggregation reads geocoded, available listings and verified recycler
profiles. It skips rows without the coordinates or pickup windows required for
feasibility instead of inventing geographic or calendar data.
"""
from datetime import date, datetime
from datetime import timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

import numpy as np
from django.conf import settings
from django.db.models import Q, Sum
from django.utils import timezone

from ml_engine.inference.aggregation import AggregationInference
from ml_engine.inference.forecast import PaperWasteForecastInference
from accounts.matching import ACTIVE_ALLOCATION_STATUSES, capacity_available_kg
from accounts.models import (Collection, EducationalInstitution, PaperListing,
                             RecyclingProfile, UserRole, VerificationStatus, WasteRecord)


def forecast_week(feature_row, model_path=None):
    """Forecast a supplied institution-week feature row; return None on fallback."""
    path = model_path or settings.BASE_DIR / "ml_engine" / "artifacts" / "paper_waste_forecaster.pt"
    return PaperWasteForecastInference(path).predict(feature_row)


def _calendar_features(day):
    month = day.month
    return {
        "is_exam_period": int(month in (5, 6, 11, 12)),
        "is_semester_end": int(month in (5, 11)),
        "is_vacation": int(month in (6, 12)),
        "month_sin": sin(2 * 3.141592653589793 * month / 12),
        "month_cos": cos(2 * 3.141592653589793 * month / 12),
    }


def forecast_institution(institution, *, weeks=4, model_path=None):
    """Forecast upcoming weeks from persisted institution waste records.

    Returns an explicit unavailable response for new institutions with fewer
    than four historical weeks; no synthetic observations are fabricated.
    """
    if weeks < 1 or weeks > 26:
        raise ValueError("Forecast horizon must be between 1 and 26 weeks.")
    records = list(WasteRecord.objects.filter(institution=institution)
                   .order_by("week_start", "paper_grade"))
    weekly = {}
    grade_totals = {}
    for record in records:
        weekly[record.week_start] = weekly.get(record.week_start, 0.0) + float(record.actual_weight_kg)
        grade_totals[record.paper_grade] = grade_totals.get(record.paper_grade, 0.0) + float(record.actual_weight_kg)
    week_dates = sorted(weekly)
    if len(week_dates) < 4:
        return {"available": False, "source": None, "weeks": [],
                "message": "At least four weeks of recorded paper weights are needed for a forecast."}
    latest_week = week_dates[-1]
    if latest_week < timezone.localdate() - timedelta(weeks=4):
        return {"available": False, "source": None, "weeks": [],
                "message": "Recent weekly paper weights are needed to make a current forecast."}
    contiguous_tail = [latest_week]
    for prior_week in reversed(week_dates[:-1]):
        if (contiguous_tail[-1] - prior_week).days != 7:
            break
        contiguous_tail.append(prior_week)
    week_dates = list(reversed(contiguous_tail))
    if len(week_dates) < 4:
        return {"available": False, "source": None, "weeks": [],
                "message": "At least four weeks of recorded paper weights, in consecutive weeks, are needed for a forecast."}

    paper_types = [choice[0] for choice in PaperListing.PaperCategory.choices if choice[0] != PaperListing.PaperCategory.OTHER]
    total_grade_weight = sum(grade_totals.values()) or 1.0
    shares = {f"share_{grade}": grade_totals.get(grade, 0.0) / total_grade_weight for grade in paper_types}
    if sum(shares.values()) <= 0:
        shares = {f"share_{grade}": 1 / len(paper_types) for grade in paper_types}
    else:
        share_total = sum(shares.values())
        shares = {name: value / share_total for name, value in shares.items()}

    path = model_path or settings.BASE_DIR / "ml_engine" / "artifacts" / "paper_waste_forecaster.pt"
    inference = PaperWasteForecastInference(path)
    values = [weekly[day] for day in week_dates]
    start_day = week_dates[-1] + timedelta(days=7)
    output = []
    source = "pytorch"
    for offset in range(weeks):
        target_day = start_day + timedelta(days=7 * offset)
        lags = [values[-1], values[-2], values[-4]]
        features = {"lag_1_kg": lags[0], "lag_2_kg": lags[1], "lag_4_kg": lags[2],
                    "student_count": institution.student_count, **shares,
                    **_calendar_features(target_day)}
        prediction = inference.predict(features)
        if prediction is None:
            source = "seasonal_baseline"
            scale = 1.32 if features["is_exam_period"] else .78 if features["is_vacation"] else 1.0
            mean = (sum(lags) / len(lags)) * scale
            recent = values[-min(12, len(values)):]
            std = float(np.std(recent)) if len(recent) > 1 else mean * .2
            spread = 1.645 * max(std, mean * .1)
            prediction = {"predicted_kg": mean, "lower_90_kg": max(0, mean - spread),
                          "upper_90_kg": mean + spread}
        mean = max(0, float(prediction["predicted_kg"]))
        alert = bool(features["is_exam_period"] and mean > (sum(lags) / len(lags)) * 1.15)
        output.append({"week_start": target_day, **prediction,
                       "is_exam_period": bool(features["is_exam_period"]),
                       "is_semester_end": bool(features["is_semester_end"]),
                       "is_vacation": bool(features["is_vacation"]), "exam_spike_alert": alert})
        values.append(mean)
    return {"available": True, "source": source, "weeks": output,
            "message": ("Forecast uses the trained PyTorch model." if source == "pytorch"
                        else "Model unavailable; showing a calendar-adjusted historical baseline.")}


def _haversine_km(left, right):
    lat1, lon1 = radians(float(left["latitude"])), radians(float(left["longitude"]))
    lat2, lon2 = radians(float(right["latitude"])), radians(float(right["longitude"]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    return 2 * 6371 * asin(sqrt(sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2))


def _mst_length(points):
    if len(points) < 2:
        return 0.0
    visited = {0}
    total = 0.0
    while len(visited) < len(points):
        distance, index = min((_haversine_km(points[left], points[right]), right)
                              for left in visited for right in range(len(points)) if right not in visited)
        total += distance
        visited.add(index)
    return total


def _canonical_request(row):
    start = row.get("pickup_start") or row.get("available_from") or row.get("created_at")
    end = row.get("pickup_deadline") or row.get("available_until")
    if not start or not end or row.get("latitude") is None or row.get("longitude") is None:
        raise ValueError("Each pickup needs coordinates and an explicit overlapping pickup window.")
    start = start.date() if isinstance(start, datetime) else (
        date.fromisoformat(str(start)[:10]) if not isinstance(start, date) else start)
    end = end.date() if isinstance(end, datetime) else (
        date.fromisoformat(str(end)[:10]) if not isinstance(end, date) else end)
    if end < start:
        raise ValueError("Pickup deadline must not precede its start date.")
    weight = float(row.get("ready_volume_kg", row.get("quantity_kg", 0)))
    if weight <= 0:
        raise ValueError("Pickup volume must be greater than zero.")
    request_id = row.get("request_id", row.get("id"))
    if request_id is None:
        raise ValueError("Each pickup needs a stable request ID.")
    latitude, longitude = float(row["latitude"]), float(row["longitude"])
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Pickup coordinates must be valid latitude/longitude values.")
    return {**row, "request_id": str(request_id),
            "pickup_start_date": start, "pickup_end_date": end, "weight_kg": weight,
            "latitude": latitude, "longitude": longitude}


def _eligible_recyclers(recyclers, requests, weight):
    grades = {row.get("paper_type") for row in requests if row.get("paper_type")}
    eligible = []
    for recycler in recyclers:
        capacity = recycler.get("available_capacity_kg", recycler.get("capacity_kg"))
        accepted = set(recycler.get("accepted_paper_types", []))
        if isinstance(recycler.get("accepted_paper_types"), str):
            accepted = set(recycler["accepted_paper_types"].split("|"))
        if capacity is None or float(capacity) < weight or (grades and not grades.issubset(accepted)):
            continue
        if recycler.get("latitude") is None or recycler.get("longitude") is None:
            continue
        if not -90 <= float(recycler["latitude"]) <= 90 or not -180 <= float(recycler["longitude"]) <= 180:
            continue
        area = (recycler.get("service_area") or "").casefold()
        if area and any(row.get("city") for row in requests):
            if not all((not row.get("city")) or row["city"].casefold() in area
                       or any(term in area for term in ("nationwide", "all regions", "all districts"))
                       for row in requests):
                continue
        eligible.append(recycler)
    return eligible


def recommend_bulk_aggregations(pickup_requests, recyclers, *, radius_km=10,
                                truck_capacity_kg=5000, min_solo_dispatch_kg=800,
                                transport_cost_per_km=12, model_path=None):
    """Build feasible, window-overlapping bulk bundles and match a capable recycler.

    Pickup dictionaries need IDs, coordinates, positive kg, a paper type, and
    pickup_start/available_from/created_at plus pickup_deadline/available_until.
    Recycler dictionaries need coordinates, capacity, and accepted paper types.
    """
    if radius_km <= 0 or truck_capacity_kg <= 0 or min_solo_dispatch_kg <= 0:
        raise ValueError("Radius, truck capacity and solo dispatch threshold must be positive.")
    requests = [_canonical_request(row) for row in pickup_requests]
    if len({row["request_id"] for row in requests}) != len(requests):
        raise ValueError("Pickup request IDs must be unique within an aggregation run.")
    requests.sort(key=lambda row: (row["pickup_start_date"], row["request_id"]))
    unused = {row["request_id"] for row in requests}
    proposals = []
    for seed in requests:
        if seed["request_id"] not in unused or seed["weight_kg"] >= min_solo_dispatch_kg:
            continue
        members = [seed]
        start, end = seed["pickup_start_date"], seed["pickup_end_date"]
        weight = seed["weight_kg"]
        candidates = sorted((row for row in requests if row["request_id"] in unused
                             and row["request_id"] != seed["request_id"]
                             and (row.get("institution_id") is None
                                  or seed.get("institution_id") is None
                                  or row.get("institution_id") != seed.get("institution_id"))
                             and all(row.get("institution_id") is None
                                     or member.get("institution_id") is None
                                     or row.get("institution_id") != member.get("institution_id")
                                     for member in members)
                             and row["weight_kg"] < min_solo_dispatch_kg),
                            key=lambda row: _haversine_km(seed, row))
        for candidate in candidates:
            candidate_distance = _haversine_km(seed, candidate)
            if candidate_distance > radius_km or weight + candidate["weight_kg"] > truck_capacity_kg:
                continue
            overlap_start = max(start, candidate["pickup_start_date"])
            overlap_end = min(end, candidate["pickup_end_date"])
            if overlap_start > overlap_end:
                continue
            trial_members = [*members, candidate]
            trial_center = {"latitude": sum(row["latitude"] for row in trial_members) / len(trial_members),
                            "longitude": sum(row["longitude"] for row in trial_members) / len(trial_members)}
            if max(_haversine_km(trial_center, row) for row in trial_members) > radius_km:
                continue
            members.append(candidate)
            weight += candidate["weight_kg"]
            start, end = overlap_start, overlap_end
        if len(members) < 2 or weight < min_solo_dispatch_kg:
            continue

        eligible = _eligible_recyclers(recyclers, members, weight)
        if not eligible:
            continue
        centroid = {"latitude": sum(row["latitude"] for row in members) / len(members),
                    "longitude": sum(row["longitude"] for row in members) / len(members)}
        recycler_routes = []
        for recycler in eligible:
            distance_to_recycler = _haversine_km(centroid, recycler)
            route_km = _mst_length(members) + 2 * distance_to_recycler
            cost = float(recycler.get("transport_cost_per_km", transport_cost_per_km)) * route_km
            recycler_routes.append((cost, distance_to_recycler, route_km, recycler))
        group_cost, recycler_distance, route_km, best_recycler = min(recycler_routes, key=lambda row: row[0])
        solo_route_km = 0.0
        for member in members:
            individual = _eligible_recyclers(recyclers, [member], member["weight_kg"])
            if individual:
                solo_route_km += 2 * min(_haversine_km(member, recycler) for recycler in individual)
        savings = max(0.0, solo_route_km - route_km)
        cost_per_kg = group_cost / weight
        if savings <= 0:
            continue
        overlap_days = max(0, (end - start).days)
        max_radius_distance = max(_haversine_km(seed, row) for row in members)
        feature = {
            "institution_count": len(members), "combined_weight_kg": weight,
            "truck_capacity_utilization": weight / truck_capacity_kg,
            "radius_utilization": max_radius_distance / radius_km,
            "deadline_overlap_days": overlap_days, "distance_savings_km": savings,
            "estimated_transport_cost_per_kg": cost_per_kg,
        }
        artifact = model_path or settings.BASE_DIR / "ml_engine" / "artifacts" / "aggregation_scorer.pt"
        model_score = AggregationInference(artifact).predict([feature])
        score = model_score[0] if model_score is not None else min(
            .99, .35 + .35 * min(feature["truck_capacity_utilization"], 1)
            + .2 * (1 - min(feature["radius_utilization"], 1))
            + .1 * min(savings / max(solo_route_km, 1), 1))
        factors = [f"{len(members)} nearby institutions share an overlapping {overlap_days}-day pickup window",
                   f"Combined load uses {weight / truck_capacity_kg:.0%} of truck capacity",
                   f"Estimated route saves {savings:.1f} km versus separate dispatches",
                   f"Estimated transport cost is {cost_per_kg:.2f} per kg"]
        proposals.append({
            "request_ids": [row["request_id"] for row in members],
            "institution_ids": [row.get("institution_id") for row in members],
            "participants": [{"institution_id": row.get("institution_id"),
                              "listing_id": row.get("listing_id"), "city": row.get("city", ""),
                              "weight_kg": round(row["weight_kg"], 2)} for row in members],
            "combined_weight_kg": round(weight, 2), "pickup_window": {"start": start.isoformat(), "end": end.isoformat()},
            "distance_savings_km": round(savings, 2), "estimated_transport_cost_per_kg": round(cost_per_kg, 4),
            "truck_capacity_utilization_pct": round(weight / truck_capacity_kg * 100, 1),
            "route_distance_km": round(route_km, 2), "score": round(float(score), 4),
            "matched_recycler": {"id": best_recycler.get("recycler_id", best_recycler.get("id")),
                                  "name": best_recycler.get("name"), "distance_km": round(recycler_distance, 2)},
            "decision_factors": factors,
        })
        unused.difference_update(row["request_id"] for row in members)
    proposals.sort(key=lambda row: (-row["score"], row["estimated_transport_cost_per_kg"]))
    return proposals


def get_live_bulk_aggregation_recommendations(*, radius_km=10, truck_capacity_kg=5000,
                                              min_solo_dispatch_kg=800, model_path=None):
    """Build bulk opportunities from available listings and verified geocoded recyclers."""
    active_listings = list(PaperListing.objects.filter(
        status=PaperListing.Status.AVAILABLE,
    ).filter(
        Q(available_until__isnull=True) | Q(available_until__gte=timezone.localdate()),
    ).filter(
        institution__latitude__isnull=False,
        institution__longitude__isnull=False,
        institution__user__is_active=True,
        institution__user__verification_status=VerificationStatus.VERIFIED,
        institution__user__role=UserRole.EDUCATIONAL_INSTITUTION,
    ).select_related("institution", "institution__user"))
    pickup_rows = []
    today = timezone.localdate()
    for listing in active_listings:
        institution = listing.institution
        start = max(listing.available_from or today, today)
        end = listing.available_until or (start + timedelta(days=7))
        pickup_rows.append({
            "request_id": f"listing-{listing.pk}", "listing_id": listing.pk,
            "institution_id": institution.pk,
            "latitude": institution.latitude, "longitude": institution.longitude,
            "city": listing.pickup_city or institution.city,
            "ready_volume_kg": float(listing.quantity_kg), "paper_type": listing.paper_type,
            "pickup_start": start, "pickup_deadline": end,
        })
    if len(pickup_rows) < 2:
        return {"available": False, "bundles": [],
                "message": "At least two geocoded, available institution listings are needed."}

    profiles = RecyclingProfile.objects.filter(
        latitude__isnull=False, longitude__isnull=False,
        collection_available=True, user__is_active=True,
        user__verification_status=VerificationStatus.VERIFIED,
        user__role=UserRole.RECYCLING_PARTNER,
    ).select_related("user").prefetch_related("collections__listing")
    recycler_rows = []
    for profile in profiles:
        pending = sum((collection.listing.quantity_kg for collection in profile.collections.all()
                       if collection.status in ACTIVE_ALLOCATION_STATUSES), Decimal("0"))
        remaining = capacity_available_kg(profile, pending)
        if remaining is None:
            continue
        recycler_rows.append({
            "recycler_id": profile.pk, "name": profile.user.organization_name,
            "latitude": profile.latitude, "longitude": profile.longitude,
            "available_capacity_kg": float(remaining),
            "accepted_paper_types": profile.accepted_paper_types or [],
            "service_area": profile.service_area,
        })
    if not recycler_rows:
        return {"available": False, "bundles": [],
                "message": "No verified recycler has geocoordinates and a configured finite capacity."}
    bundles = recommend_bulk_aggregations(
        pickup_rows, recycler_rows, radius_km=radius_km,
        truck_capacity_kg=truck_capacity_kg,
        min_solo_dispatch_kg=min_solo_dispatch_kg, model_path=model_path,
    )
    return {"available": bool(bundles), "bundles": bundles,
            "message": "Nearby listing bundles ranked by capacity and estimated route cost." if bundles
            else "No listings currently meet the distance, timing, load, and recycler-capacity constraints."}
