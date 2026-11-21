"""PaperLoop forecasting and recycler-ranking components."""

FORECAST_FEATURES = (
    "lag_1_kg", "lag_2_kg", "lag_4_kg", "student_count",
    "share_office_paper", "share_books_notebooks", "share_newspapers_magazines",
    "share_cardboard", "share_mixed_paper", "is_exam_period", "is_semester_end",
    "is_vacation", "month_sin", "month_cos",
)
RANK_FEATURES = (
    "distance_km", "capacity_utilization_ratio", "paper_grade_match",
    "historical_fulfillment_rate", "average_rating", "price_competitiveness",
)
AGGREGATION_FEATURES = (
    "institution_count", "combined_weight_kg", "truck_capacity_utilization",
    "radius_utilization", "deadline_overlap_days", "distance_savings_km",
    "estimated_transport_cost_per_kg",
)
FEATURE_SCHEMA_VERSION = "paperloop-forecast-v1"
RANK_SCHEMA_VERSION = "paperloop-recycler-rank-v1"
AGGREGATION_SCHEMA_VERSION = "paperloop-aggregation-v1"
MODEL_VERSION = "synthetic-pilot-v3"
