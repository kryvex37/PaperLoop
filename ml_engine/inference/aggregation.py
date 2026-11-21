"""Cached cluster scoring inference for bulk pickup proposals."""
from functools import lru_cache
from pathlib import Path

import torch

from ml_engine import AGGREGATION_FEATURES, AGGREGATION_SCHEMA_VERSION
from ml_engine.models.aggregation import AggregationClusterScorer


@lru_cache(maxsize=4)
def _load_scorer(path_string, modified_time):
    del modified_time
    checkpoint = torch.load(path_string, map_location="cpu", weights_only=True)
    if checkpoint.get("feature_schema_version") != AGGREGATION_SCHEMA_VERSION:
        raise ValueError("Aggregation model feature schema does not match this application.")
    model = AggregationClusterScorer(len(AGGREGATION_FEATURES))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def scale_features(rows):
    values = torch.tensor([[float(row[name]) for name in AGGREGATION_FEATURES]
                           for row in rows], dtype=torch.float32)
    values[:, 0].clamp_(1, 20).div_(10)
    values[:, 1].clamp_(0, 50000).div_(10000)
    values[:, 2].clamp_(0, 2)
    values[:, 3].clamp_(0, 2)
    values[:, 4].clamp_(-30, 30).div_(14)
    values[:, 5].clamp_(0, 250).div_(100)
    values[:, 6].clamp_(0, 2).div_(2)
    return values


class AggregationInference:
    def __init__(self, model_path):
        self.model_path = Path(model_path)

    def predict(self, feature_rows):
        if not feature_rows or not self.model_path.is_file():
            return None
        try:
            model = _load_scorer(str(self.model_path), self.model_path.stat().st_mtime_ns)
            features = scale_features(feature_rows)
            if not torch.isfinite(features).all():
                return None
            with torch.inference_mode():
                return torch.sigmoid(model(features)).tolist()
        except (OSError, RuntimeError, ValueError, KeyError, TypeError):
            return None
