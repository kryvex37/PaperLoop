"""Seeded synthetic PaperLoop pilot data using calendar-aware weekly records.

All entities and outcomes are synthetic. The CSVs are schema-compatible training
fixtures, not production records or evidence of marketplace performance.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from ml_engine import AGGREGATION_FEATURES, FORECAST_FEATURES, RANK_FEATURES

PAPER_GRADES = ("office_paper", "books_notebooks", "newspapers_magazines", "cardboard", "mixed_paper")
CITY_CLUSTERS = {
    "Dhaka": (23.8103, 90.4125), "Chattogram": (22.3569, 91.7832),
    "Rajshahi": (24.3745, 88.6042), "Khulna": (22.8456, 89.5403),
    "Sylhet": (24.8949, 91.8687), "Mymensingh": (24.7471, 90.4203),
}
CALENDAR_MONTHS = {"admission": (1, 2, 6, 7), "semester_start": (1, 7), "midterm": (3, 9),
                   "semester_end": (5, 11), "final_exam": (5, 6, 11, 12), "vacation": (6, 12)}


def _calendar_flags(date):
    month = date.month
    return {
        "is_admission_season": int(month in CALENDAR_MONTHS["admission"]),
        "is_semester_start": int(month in CALENDAR_MONTHS["semester_start"]),
        "is_midterm_period": int(month in CALENDAR_MONTHS["midterm"]),
        "is_semester_end": int(month in CALENDAR_MONTHS["semester_end"]),
        "is_exam_period": int(month in CALENDAR_MONTHS["final_exam"]),
        "is_vacation": int(month in CALENDAR_MONTHS["vacation"]),
    }


def generate_pilot_data(output_dir, institutions=80, requests=1500, seed=42,
                        start_date="2024-01-01", months=24, candidates_per_request=6):
    """Write institution, weekly waste, transaction, pickup, and ranking CSVs."""
    if institutions < 2 or requests < 20 or not 1 <= months <= 60 or candidates_per_request < 3:
        raise ValueError("Use >=2 institutions, >=20 requests, 1-60 months, and >=3 candidates.")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    institution_rows = []
    for index in range(institutions):
        city = list(CITY_CLUSTERS)[index % len(CITY_CLUSTERS)]
        center_lat, center_lon = CITY_CLUSTERS[city]
        institution_rows.append({
            "institution_id": f"INST-{index + 1:04d}", "organization_name": f"Pilot Institution {index + 1:04d}",
            "institution_type": ["school", "college", "university", "library"][index % 4],
            "city": city, "country": "Bangladesh", "latitude": round(float(rng.normal(center_lat, .035)), 6),
            "longitude": round(float(rng.normal(center_lon, .035)), 6),
            "student_count": int(rng.integers(350, 18000)),
            "primary_paper_type": str(rng.choice(PAPER_GRADES)),
        })
    institutions_df = pd.DataFrame(institution_rows)
    start = pd.Timestamp(start_date).normalize()
    weeks = pd.date_range(start=start, periods=int(np.ceil(months * 30.4375 / 7)), freq="W-MON")
    waste_rows = []
    for institution in institution_rows:
        size = institution["student_count"]
        base = max(18.0, size * float(rng.uniform(.018, .052)))
        category_weights = rng.dirichlet(np.ones(len(PAPER_GRADES)) * 2)
        for week_index, date in enumerate(weeks):
            flags = _calendar_flags(date)
            weekly_seasonality = 1 + .08 * np.sin(2 * np.pi * date.isocalendar().week / 52)
            event_factor = (1 + .32 * flags["is_exam_period"] + .12 * flags["is_midterm_period"]
                            + .16 * flags["is_semester_end"] + .10 * flags["is_admission_season"]
                            - .36 * flags["is_vacation"])
            trend = 1 + .0008 * week_index
            weight = max(2.0, base * weekly_seasonality * event_factor * trend * rng.lognormal(0, .17))
            categories = rng.multinomial(max(1, int(round(weight))), category_weights)
            row = {"institution_id": institution["institution_id"], "week_start": date.date().isoformat(),
                   "waste_kg": round(weight, 2), "student_count": size,
                   **{f"share_{grade}": float(category_weights[i]) for i, grade in enumerate(PAPER_GRADES)},
                   **flags, "month_sin": float(np.sin(2 * np.pi * date.month / 12)),
                   "month_cos": float(np.cos(2 * np.pi * date.month / 12))}
            row.update({f"observed_{grade}_kg": float(categories[i]) for i, grade in enumerate(PAPER_GRADES)})
            waste_rows.append(row)
    weekly_df = pd.DataFrame(waste_rows)

    recycler_rows = []
    for index in range(max(12, institutions // 3)):
        city = list(CITY_CLUSTERS)[(index * 2) % len(CITY_CLUSTERS)]
        lat, lon = CITY_CLUSTERS[city]
        recycler_rows.append({"recycler_id": f"RECY-{index + 1:04d}", "service_city": city,
                              "latitude": float(rng.normal(lat, .025)), "longitude": float(rng.normal(lon, .025)),
                              "capacity_kg_month": float(rng.integers(2500, 50000)),
                              "accepted_paper_types": "|".join(rng.choice(PAPER_GRADES, size=int(rng.integers(2, 6)), replace=False)),
                              "base_price_per_kg": round(float(rng.uniform(8, 32)), 2),
                              "historical_fulfillment_rate": round(float(rng.beta(12, 2)), 4),
                              "average_rating": round(float(rng.uniform(3.3, 5.0)), 2)})
    recyclers_df = pd.DataFrame(recycler_rows)

    transaction_rows = []
    for index in range(max(requests * 2, 1000)):
        inst = institution_rows[int(rng.integers(0, len(institution_rows)))]
        recycler = recycler_rows[int(rng.integers(0, len(recycler_rows)))]
        grade = str(rng.choice(PAPER_GRADES))
        accepted = grade in recycler["accepted_paper_types"].split("|")
        weight = float(np.clip(rng.lognormal(7.1, .65), 100, 12000))
        capacity = recycler["capacity_kg_month"]
        utilization = min(2.0, weight / capacity)
        distance = float(np.hypot((inst["latitude"] - recycler["latitude"]) * 111,
                                  (inst["longitude"] - recycler["longitude"]) * 102))
        complete_prob = np.clip(.18 + .42 * accepted + .24 * (utilization < .8)
                                + .18 * recycler["historical_fulfillment_rate"] - .002 * distance, .03, .98)
        completed = int(rng.random() < complete_prob)
        transaction_rows.append({
            "transaction_id": f"TX-{index + 1:07d}", "institution_id": inst["institution_id"],
            "recycler_id": recycler["recycler_id"], "created_at": (start + pd.Timedelta(days=int(rng.integers(0, months * 30)))).date().isoformat(),
            "distance_km": round(distance, 2), "paper_type": grade, "paper_grade_match": int(accepted),
            "available_capacity_kg": round(capacity, 2), "batch_weight_kg": round(weight, 2),
            "capacity_utilization_ratio": round(utilization, 4),
            "price_offered_per_kg": round(float(recycler["base_price_per_kg"] * rng.uniform(.75, 1.25)), 2),
            "completed": completed, "completion_rating": round(float(np.clip(rng.normal(4.15 if completed else 2.5, .65), 1, 5)), 2),
            "response_latency_hours": round(float(rng.lognormal(2.25, .75)), 2),
        })
    transactions_df = pd.DataFrame(transaction_rows)

    pickup_rows, ranking_rows = [], []
    transaction_frame = transactions_df
    for request_index in range(requests):
        inst = institution_rows[int(rng.integers(0, len(institution_rows)))]
        ready = float(np.clip(rng.lognormal(7.3, .7), 100, 20000))
        days_until_deadline = int(rng.integers(2, 22))
        request_date = start + pd.Timedelta(days=int(rng.integers(0, max(1, months * 30))))
        grade = str(rng.choice(PAPER_GRADES))
        request_id = f"PICK-{request_index + 1:06d}"
        pickup_rows.append({"request_id": request_id, "institution_id": inst["institution_id"],
                            "created_at": request_date.date().isoformat(), "latitude": inst["latitude"],
                            "longitude": inst["longitude"], "ready_volume_kg": round(ready, 2),
                            "paper_type": grade, "pickup_deadline": (request_date + pd.Timedelta(days=days_until_deadline)).date().isoformat(),
                            "deadline_window_days": days_until_deadline, "geo_cluster": inst["city"]})
        candidate_recyclers = rng.choice(len(recycler_rows), size=candidates_per_request, replace=False)
        candidate_distances = []
        for recycler_index in candidate_recyclers:
            recycler = recycler_rows[int(recycler_index)]
            distance = float(np.hypot((inst["latitude"] - recycler["latitude"]) * 111,
                                      (inst["longitude"] - recycler["longitude"]) * 102))
            candidate_distances.append((recycler, distance))
        local_prices = [r["base_price_per_kg"] for r, _ in candidate_distances]
        market_price = float(np.mean(local_prices))
        for recycler, distance in candidate_distances:
            grade_match = int(grade in recycler["accepted_paper_types"].split("|"))
            cap_ratio = ready / recycler["capacity_kg_month"]
            utilization = min(2., cap_ratio)
            price = recycler["base_price_per_kg"] * rng.uniform(.9, 1.1)
            competitiveness = float(np.clip(market_price / price, .5, 1.5))
            response = float(rng.lognormal(2.25, .75))
            latent = (1.25 * grade_match + .9 * (cap_ratio <= .8) + .65 * recycler["historical_fulfillment_rate"]
                      + .28 * recycler["average_rating"] + .25 * competitiveness - .018 * distance
                      - .003 * response + rng.normal(0, .35))
            label = int(latent >= 1.65)
            ranking_rows.append({"request_id": request_id, "institution_id": inst["institution_id"],
                                 "recycler_id": recycler["recycler_id"], "distance_km": round(distance, 3),
                                 "capacity_utilization_ratio": round(utilization, 5),
                                 "paper_grade_match": grade_match,
                                 "historical_fulfillment_rate": recycler["historical_fulfillment_rate"],
                                 "average_rating": recycler["average_rating"],
                                 "price_competitiveness": round(competitiveness, 5), "label": label})

    # Create same-city pair proposals as supervised examples. Runtime still
    # applies hard radius, deadline, and truck-capacity constraints before scoring.
    aggregation_rows = []
    request_frame = pd.DataFrame(pickup_rows)
    for _, left in request_frame.iterrows():
        peers = request_frame[(request_frame.geo_cluster == left.geo_cluster) &
                              (request_frame.request_id > left.request_id)]
        if peers.empty:
            continue
        right = peers.iloc[int(rng.integers(0, len(peers)))]
        distance = float(np.hypot((left.latitude - right.latitude) * 111,
                                  (left.longitude - right.longitude) * 102))
        left_start, right_start = pd.Timestamp(left.created_at), pd.Timestamp(right.created_at)
        left_end, right_end = pd.Timestamp(left.pickup_deadline), pd.Timestamp(right.pickup_deadline)
        overlap_days = (min(left_end, right_end) - max(left_start, right_start)).days
        combined = float(left.ready_volume_kg + right.ready_volume_kg)
        capacity_utilization = combined / 5000
        savings = max(0.0, distance * .7)
        cost_per_kg = (distance * 2 * 12) / max(combined, 1)
        feasible = distance <= 10 and overlap_days >= 0 and combined <= 5000 and combined >= 800
        aggregation_rows.append({
            "request_id": left.request_id, "peer_request_id": right.request_id,
            "institution_count": 2, "combined_weight_kg": round(combined, 2),
            "truck_capacity_utilization": round(capacity_utilization, 5),
            "radius_utilization": round(distance / 10, 5), "deadline_overlap_days": overlap_days,
            "distance_savings_km": round(savings, 3),
            "estimated_transport_cost_per_kg": round(cost_per_kg, 5),
            "label": int(feasible and savings >= .25 and cost_per_kg <= .12),
        })

    outputs = {
        "institutions.csv": institutions_df,
        "recyclers.csv": recyclers_df,
        "weekly_waste.csv": weekly_df,
        "pickup_history.csv": transaction_frame,
        "transactions.csv": transactions_df,
        "pickup_requests.csv": pd.DataFrame(pickup_rows),
        "ranking_candidates.csv": pd.DataFrame(ranking_rows),
        "aggregation_candidates.csv": pd.DataFrame(aggregation_rows, columns=[*AGGREGATION_FEATURES, "request_id", "peer_request_id", "label"]),
    }
    for name, frame in outputs.items():
        frame.to_csv(root / name, index=False)
    return {name: len(frame) for name, frame in outputs.items()}


class PaperWasteDataset(Dataset):
    """Weekly sequence/tabular rows with t-1, t-2 and t-4 kg lags."""
    def __init__(self, weekly_csv):
        frame = pd.read_csv(weekly_csv).sort_values(["institution_id", "week_start"]).copy()
        for name, periods in (("lag_1_kg", 1), ("lag_2_kg", 2), ("lag_4_kg", 4)):
            frame[name] = frame.groupby("institution_id", sort=False).waste_kg.shift(periods)
        frame = frame.dropna(subset=["lag_1_kg", "lag_2_kg", "lag_4_kg"])
        self.features = frame[list(FORECAST_FEATURES)].to_numpy(dtype=np.float32)
        self.targets = frame.waste_kg.to_numpy(dtype=np.float32)

    def __len__(self):
        return len(self.targets)

    def __getitem__(self, index):
        return torch.tensor(self.features[index]), torch.tensor(self.targets[index])


class RecyclerPairDataset(Dataset):
    """Grouped (request, recycler candidates) feature tensors and binary labels."""
    def __init__(self, candidates_csv):
        frame = pd.read_csv(candidates_csv).sort_values(["request_id", "recycler_id"])
        sizes = frame.groupby("request_id").size()
        if sizes.nunique() != 1:
            raise ValueError("Every request must have the same number of candidate recyclers.")
        self.group_size = int(sizes.iloc[0])
        self.features = frame[list(RANK_FEATURES)].to_numpy(dtype=np.float32).reshape(
            len(sizes), self.group_size, len(RANK_FEATURES))
        self.labels = frame.label.to_numpy(dtype=np.float32).reshape(len(sizes), self.group_size)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, index):
        return torch.tensor(self.features[index]), torch.tensor(self.labels[index])


class AggregationCandidateDataset(Dataset):
    """Synthetic or historical candidate bundle features and recommendation labels."""
    def __init__(self, candidates_csv):
        frame = pd.read_csv(candidates_csv)
        self.features = frame[list(AGGREGATION_FEATURES)].to_numpy(dtype=np.float32)
        self.labels = frame.label.to_numpy(dtype=np.float32)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, index):
        return torch.tensor(self.features[index]), torch.tensor(self.labels[index])
