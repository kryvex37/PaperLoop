"""Cached ranking inference with input-perturbation explanations."""
from functools import lru_cache
from pathlib import Path

import torch

from ml_engine import RANK_FEATURES, RANK_SCHEMA_VERSION
from ml_engine.models.partner_match import RecyclerRankerNet


@lru_cache(maxsize=4)
def _load_ranker(path_string, modified_time):
    del modified_time
    checkpoint = torch.load(path_string, map_location="cpu", weights_only=True)
    if checkpoint.get("feature_schema_version") != RANK_SCHEMA_VERSION:
        raise ValueError("Ranker feature schema does not match this application.")
    model = RecyclerRankerNet(len(RANK_FEATURES))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def _scale_features(feature_rows):
    values = torch.tensor([[float(row[name]) for name in RANK_FEATURES]
                           for row in feature_rows], dtype=torch.float32)
    values[:, 0].clamp_(0, 250).div_(100)
    values[:, 1].clamp_(0, 2)
    values[:, 2].clamp_(0, 1)
    values[:, 3].clamp_(0, 1)
    values[:, 4].clamp_(0, 5).div_(5)
    values[:, 5].clamp_(.5, 1.5).div_(1.5)
    return values


def explain_ranking(model, scaled_features, raw_features):
    """Attribute score changes by replacing one feature with a neutral value."""
    neutral = torch.tensor([.25, .8, 1., .85, .8, 1 / 1.5], dtype=torch.float32)
    with torch.inference_mode():
        contributions = []
        for index, name in enumerate(RANK_FEATURES):
            perturbed = scaled_features.clone()
            perturbed[index] = neutral[index]
            delta = float(model(scaled_features.unsqueeze(0))[0] - model(perturbed.unsqueeze(0))[0])
            contributions.append((name, delta))
    total = sum(abs(value) for _, value in contributions) or 1.0
    history_count = int(raw_features.get("history_observation_count", 0))
    if history_count:
        history_text = (
            f"{raw_features.get('history_completed_count', 0)} of {history_count} resolved pickups completed; "
            f"smoothed estimate {raw_features['historical_fulfillment_rate']:.0%}"
        )
    elif raw_features.get("history_prior_used"):
        history_text = "Neutral fulfillment prior used; no resolved pickup history yet"
    else:
        history_text = (
            f"Stored fulfillment estimate {raw_features['historical_fulfillment_rate']:.0%}; "
            "no resolved pickup history yet"
        )
    rating_text = (
        "Neutral rating prior used; no partner ratings recorded"
        if raw_features.get("rating_prior_used") else
        f"{raw_features['average_rating']:.1f}/5 average rating"
    )
    price_text = (
        "Neutral price prior used; no price comparisons recorded"
        if raw_features.get("price_prior_used") else
        f"Price competitiveness {raw_features['price_competitiveness']:.2f}x local market"
    )
    feature_text = {
        "distance_km": f"Within {raw_features['distance_km']:.1f} km",
        "capacity_utilization_ratio": (
            "Flexible capacity; no fixed utilization limit"
            if raw_features.get("capacity_is_flexible") else
            f"Capacity use is {raw_features['capacity_utilization_ratio']:.0%} of available capacity"
        ),
        "paper_grade_match": "Paper type is accepted" if raw_features["paper_grade_match"] >= 1 else "Paper type is not confirmed",
        "historical_fulfillment_rate": history_text,
        "average_rating": rating_text,
        "price_competitiveness": price_text,
    }
    factors = []
    for name, delta in sorted(contributions, key=lambda pair: abs(pair[1]), reverse=True):
        if abs(delta) < 1e-6:
            continue
        pct = abs(delta) / total * 100
        direction = "+" if delta > 0 else "−"
        factors.append(f"{feature_text[name]} ({direction}{pct:.0f}% model attribution)")
    for flag, name in (
        ("history_prior_used", "historical_fulfillment_rate"),
        ("rating_prior_used", "average_rating"),
        ("price_prior_used", "price_competitiveness"),
    ):
        if raw_features.get(flag):
            factors.append(feature_text[name])
    return factors


class PartnerMatchInference:
    """Return scores and human-readable attribution for eligible candidates."""
    def __init__(self, model_path):
        self.model_path = Path(model_path)

    def predict(self, feature_rows):
        if not self.model_path.is_file() or not feature_rows:
            return None
        try:
            model = _load_ranker(str(self.model_path), self.model_path.stat().st_mtime_ns)
            values = _scale_features(feature_rows)
            if not torch.isfinite(values).all():
                return None
            with torch.inference_mode():
                scores = model(values)
                probabilities = torch.sigmoid(scores).tolist()
            explanations = [explain_ranking(model, values[index], row)
                            for index, row in enumerate(feature_rows)]
            return [{"score": score, "factors": factors}
                    for score, factors in zip(probabilities, explanations)]
        except (OSError, RuntimeError, ValueError, KeyError, TypeError):
            return None
