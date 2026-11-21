"""Cached forecast service returning a mean and approximate 90% interval."""
from functools import lru_cache
from pathlib import Path

import torch

from ml_engine import FEATURE_SCHEMA_VERSION, FORECAST_FEATURES
from ml_engine.models.forecast import PaperWasteForecaster


@lru_cache(maxsize=4)
def _load_forecaster(path_string, modified_time):
    del modified_time
    checkpoint = torch.load(path_string, map_location="cpu", weights_only=True)
    if checkpoint.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise ValueError("Forecaster feature schema does not match this application.")
    model = PaperWasteForecaster(len(FORECAST_FEATURES))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


class PaperWasteForecastInference:
    def __init__(self, model_path):
        self.model_path = Path(model_path)

    def predict(self, feature_row):
        if not self.model_path.is_file():
            return None
        try:
            values = [float(feature_row[name]) for name in FORECAST_FEATURES]
            values[:3] = [value / 1000 for value in values[:3]]
            values[3] /= 10000
            tensor = torch.tensor([values], dtype=torch.float32)
            if not torch.isfinite(tensor).all():
                return None
            model = _load_forecaster(str(self.model_path), self.model_path.stat().st_mtime_ns)
            with torch.inference_mode():
                mean, log_variance = model(tensor)
                mean_kg = float(mean[0]) * 1000
                std_kg = float(torch.exp(.5 * log_variance[0])) * 1000
            return {"predicted_kg": mean_kg,
                    "lower_90_kg": max(0, mean_kg - 1.645 * std_kg),
                    "upper_90_kg": mean_kg + 1.645 * std_kg}
        except (OSError, RuntimeError, ValueError, KeyError, TypeError):
            return None
