"""Deterministic chronological forecasting and grouped pairwise ranker training."""
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from ml_engine import (FEATURE_SCHEMA_VERSION, FORECAST_FEATURES, MODEL_VERSION,
                       RANK_FEATURES, RANK_SCHEMA_VERSION, AGGREGATION_FEATURES,
                       AGGREGATION_SCHEMA_VERSION)
from ml_engine.models.aggregation import AggregationClusterScorer
from ml_engine.models.forecast import PaperWasteForecaster, gaussian_nll
from ml_engine.models.partner_match import RecyclerRankerNet


def _save_checkpoint(path, state_dict, metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({**metadata, "model_state_dict": state_dict}, path)
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def _forecast_matrix(frame):
    matrix = frame[list(FORECAST_FEATURES)].to_numpy(dtype=np.float32).copy()
    # Stable domain scaling keeps kg and population inputs in a useful range.
    for index, name in enumerate(FORECAST_FEATURES):
        if name.startswith("lag_"):
            matrix[:, index] /= 1000.0
        elif name == "student_count":
            matrix[:, index] /= 10000.0
    target = frame["waste_kg"].to_numpy(dtype=np.float32) / 1000.0
    return matrix, target


def train_forecaster(waste_csv, artifact_path, seed=42, epochs=35, learning_rate=.003):
    _seed_everything(seed)
    frame = pd.read_csv(waste_csv, parse_dates=["week_start"])
    frame = frame.sort_values(["institution_id", "week_start"]).copy()
    groups = frame.groupby("institution_id", sort=False)
    for lag, periods in (("lag_1_kg", 1), ("lag_2_kg", 2), ("lag_4_kg", 4)):
        frame[lag] = groups["waste_kg"].shift(periods)
    frame = frame.dropna(subset=["lag_1_kg", "lag_2_kg", "lag_4_kg"])
    cutoff = frame["week_start"].quantile(.8)
    train_frame, validation_frame = frame[frame.week_start <= cutoff], frame[frame.week_start > cutoff]
    if len(train_frame) < 20 or len(validation_frame) < 10:
        raise ValueError("Weekly history is too small for a chronological train/validation split.")
    x_train, y_train = _forecast_matrix(train_frame)
    x_val, y_val = _forecast_matrix(validation_frame)
    x_train_t, y_train_t = torch.tensor(x_train), torch.tensor(y_train)
    x_val_t, y_val_t = torch.tensor(x_val), torch.tensor(y_val)
    model = PaperWasteForecaster(len(FORECAST_FEATURES))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    with torch.no_grad():
        initial_mean, initial_log_var = model(x_train_t)
        training_loss_initial = gaussian_nll(initial_mean, initial_log_var, y_train_t).item()
    training_loss_final = training_loss_initial
    for _ in range(epochs):
        model.train()
        # Full batch is deterministic and inexpensive for the generated pilot set.
        optimizer.zero_grad(set_to_none=True)
        mean, log_var = model(x_train_t)
        loss = gaussian_nll(mean, log_var, y_train_t)
        loss.backward()
        optimizer.step()
        training_loss_final = loss.item()
    model.eval()
    with torch.no_grad():
        mean, log_var = model(x_val_t)
        predictions = mean * 1000
        actual = y_val_t * 1000
        std_kg = torch.exp(.5 * log_var) * 1000
        errors = predictions - actual
        persistence_errors = validation_frame["lag_1_kg"].to_numpy(dtype=np.float32) - actual.numpy()
        metrics = {
            "validation_rows": len(validation_frame),
            "mae_kg": torch.abs(errors).mean().item(),
            "rmse_kg": torch.sqrt(errors.square().mean()).item(),
            "prediction_interval_90_coverage": ((torch.abs(errors) <= 1.645 * std_kg).float().mean().item()),
            "mean_prediction_interval_width_90_kg": (3.29 * std_kg).mean().item(),
            "persistence_baseline_mae_kg": float(np.abs(persistence_errors).mean()),
            "training_loss_initial": training_loss_initial,
            "training_loss_final": training_loss_final,
            "data_note": "Synthetic calendar-driven targets; not a production forecast estimate.",
        }
    metadata = {"model_version": MODEL_VERSION, "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "feature_names": list(FORECAST_FEATURES), "seed": seed,
                "training_config": {"epochs": epochs, "learning_rate": learning_rate,
                                    "split": "chronological_last_20_percent"},
                "feature_scaler": {"lag_kg_divisor": 1000, "student_count_divisor": 10000},
                "target_scale_kg": 1000, "evaluation": metrics}
    _save_checkpoint(artifact_path, model.state_dict(), metadata)
    return metrics


def _rank_matrix(frame):
    matrix = frame[list(RANK_FEATURES)].to_numpy(dtype=np.float32).copy()
    matrix[:, 0] = np.clip(matrix[:, 0], 0, 250) / 100.0
    matrix[:, 1] = np.clip(matrix[:, 1], 0, 2)
    matrix[:, 2] = np.clip(matrix[:, 2], 0, 1)
    matrix[:, 3] = np.clip(matrix[:, 3], 0, 1)
    matrix[:, 4] = np.clip(matrix[:, 4], 0, 5) / 5.0
    matrix[:, 5] = np.clip(matrix[:, 5], .5, 1.5) / 1.5
    return matrix


def _aggregation_matrix(frame):
    matrix = frame[list(AGGREGATION_FEATURES)].to_numpy(dtype=np.float32).copy()
    matrix[:, 0] = np.clip(matrix[:, 0], 1, 20) / 10
    matrix[:, 1] = np.clip(matrix[:, 1], 0, 50000) / 10000
    matrix[:, 2] = np.clip(matrix[:, 2], 0, 2)
    matrix[:, 3] = np.clip(matrix[:, 3], 0, 2)
    matrix[:, 4] = np.clip(matrix[:, 4], -30, 30) / 14
    matrix[:, 5] = np.clip(matrix[:, 5], 0, 250) / 100
    matrix[:, 6] = np.clip(matrix[:, 6], 0, 2) / 2
    return matrix


def train_aggregation_model(candidates_csv, artifact_path, seed=42, epochs=35, learning_rate=.003):
    _seed_everything(seed)
    frame = pd.read_csv(candidates_csv).sample(frac=1, random_state=seed).reset_index(drop=True)
    if len(frame) < 20 or frame.label.nunique() < 2:
        raise ValueError("Aggregation training needs at least 20 proposals with positive and negative labels.")
    features = torch.tensor(_aggregation_matrix(frame))
    labels = torch.tensor(frame.label.to_numpy(dtype=np.float32))
    split = int(len(frame) * .8)
    if split < 1 or len(frame) - split < 1:
        raise ValueError("Not enough aggregation proposals to split.")
    train_x, train_y, val_x, val_y = features[:split], labels[:split], features[split:], labels[split:]
    model = AggregationClusterScorer(len(AGGREGATION_FEATURES))
    positive_weight = (train_y == 0).sum().float() / (train_y == 1).sum().clamp(min=1)
    criterion = nn.BCEWithLogitsLoss(pos_weight=positive_weight)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    training_loss_initial = None
    training_loss_final = None
    for _ in range(epochs):
        model.train()
        logits = model(train_x)
        loss = criterion(logits, train_y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        if training_loss_initial is None:
            training_loss_initial = loss.item()
        training_loss_final = loss.item()
    model.eval()
    with torch.no_grad():
        logits = model(val_x)
        predictions = logits >= 0
        accuracy = (predictions == val_y.bool()).float().mean().item()
        positive = predictions & val_y.bool()
        precision = (positive.sum().float() / predictions.sum().clamp(min=1)).item()
        recall = (positive.sum().float() / val_y.sum().clamp(min=1)).item()
        metrics = {"validation_rows": len(val_y), "accuracy": accuracy,
                   "positive_precision": precision, "positive_recall": recall,
                   "majority_baseline_accuracy": max(val_y.mean().item(), 1 - val_y.mean().item()),
                   "training_loss_initial": training_loss_initial,
                   "training_loss_final": training_loss_final,
                   "data_note": "Synthetic spatial-temporal labels; not real dispatch outcomes."}
    metadata = {"model_version": MODEL_VERSION, "feature_schema_version": AGGREGATION_SCHEMA_VERSION,
                "feature_names": list(AGGREGATION_FEATURES), "seed": seed,
                "training_config": {"epochs": epochs, "learning_rate": learning_rate,
                                    "objective": "weighted_binary_cross_entropy"},
                "feature_scaler": {"institution_count_divisor": 10, "weight_kg_divisor": 10000,
                                   "deadline_overlap_days_divisor": 14, "distance_savings_km_divisor": 100,
                                   "cost_per_kg_divisor": 2}, "evaluation": metrics}
    _save_checkpoint(artifact_path, model.state_dict(), metadata)
    return metrics


def _pairwise_loss(scores, labels):
    losses = []
    for row_scores, row_labels in zip(scores, labels):
        positive = row_scores[row_labels > .5]
        negative = row_scores[row_labels <= .5]
        if positive.numel() and negative.numel():
            losses.append(torch.nn.functional.softplus(-(positive[:, None] - negative[None, :])).mean())
    return torch.stack(losses).mean() if losses else scores.sum() * 0


def train_ranker(ranking_csv, artifact_path, seed=42, epochs=35, learning_rate=.003):
    _seed_everything(seed)
    frame = pd.read_csv(ranking_csv).sort_values("request_id")
    request_count = frame.request_id.nunique()
    candidate_counts = frame.groupby("request_id").size()
    if request_count < 20 or candidate_counts.nunique() != 1 or candidate_counts.iloc[0] < 2:
        raise ValueError("Ranking data must have at least 20 requests with equal candidate groups.")
    features = _rank_matrix(frame)
    labels = frame.label.to_numpy(dtype=np.float32)
    group_size = int(candidate_counts.iloc[0])
    features = torch.tensor(features.reshape(request_count, group_size, len(RANK_FEATURES)))
    labels = torch.tensor(labels.reshape(request_count, group_size))
    split = int(request_count * .8)
    if split < 1 or request_count - split < 1:
        raise ValueError("Not enough request groups to split.")
    train_x, train_y = features[:split], labels[:split]
    val_x, val_y = features[split:], labels[split:]
    model = RecyclerRankerNet(len(RANK_FEATURES))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    training_loss_initial = None
    training_loss_final = None
    for _ in range(epochs):
        model.train()
        order = torch.randperm(len(train_x))
        epoch_losses = []
        for indices in order.split(64):
            batch_x, batch_y = train_x[indices], train_y[indices]
            scores = model(batch_x.reshape(-1, len(RANK_FEATURES))).reshape(len(indices), group_size)
            bce = nn.functional.binary_cross_entropy_with_logits(scores, batch_y)
            loss = _pairwise_loss(scores, batch_y) + .25 * bce
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            epoch_losses.append(loss.item())
        epoch_loss = float(np.mean(epoch_losses))
        if training_loss_initial is None:
            training_loss_initial = epoch_loss
        training_loss_final = epoch_loss
    model.eval()
    with torch.no_grad():
        scores = model(val_x.reshape(-1, len(RANK_FEATURES))).reshape(len(val_x), group_size)
        valid = (val_y > .5).any(dim=1)
        top_label = val_y[torch.arange(len(val_y)), scores.argmax(dim=1)] > .5
        hit_rate = (top_label[valid].float().mean().item() if valid.any() else 0.0)
        auc_proxy = ((scores >= 0) == val_y.bool()).float().mean().item()
        baseline_raw = frame.iloc[split * group_size:][list(RANK_FEATURES)].copy()
        baseline_raw["heuristic_score"] = (
            1.25 * baseline_raw.paper_grade_match
            + .9 * (baseline_raw.capacity_utilization_ratio <= .8)
            + .65 * baseline_raw.historical_fulfillment_rate
            + .28 * baseline_raw.average_rating
            + .25 * baseline_raw.price_competitiveness
            - .018 * baseline_raw.distance_km
        )
        baseline_scores = torch.tensor(baseline_raw.heuristic_score.to_numpy().reshape(len(val_x), group_size))
        baseline_top_label = val_y[torch.arange(len(val_y)), baseline_scores.argmax(dim=1)] > .5
        baseline_hit_rate = (baseline_top_label[valid].float().mean().item() if valid.any() else 0.0)
        metrics = {"validation_requests": len(val_x), "requests_with_positive": int(valid.sum()),
                   "positive_top1_hit_rate": hit_rate, "threshold_accuracy": auc_proxy,
                   "heuristic_baseline_positive_top1_hit_rate": baseline_hit_rate,
                   "training_loss_initial": training_loss_initial,
                   "training_loss_final": training_loss_final,
                   "data_note": "Synthetic heuristic preferences; not evidence of real recycler selection quality."}
    metadata = {"model_version": MODEL_VERSION, "feature_schema_version": RANK_SCHEMA_VERSION,
                "feature_names": list(RANK_FEATURES), "seed": seed,
                "training_config": {"epochs": epochs, "learning_rate": learning_rate,
                                    "objective": "grouped_pairwise_softplus_plus_bce"},
                "feature_scaler": {"distance_km_divisor": 100, "average_rating_divisor": 5,
                                   "price_competitiveness_divisor": 1.5,
                                   "clipping": {"distance_km": [0, 250], "capacity_utilization_ratio": [0, 2]}},
                "evaluation": metrics}
    _save_checkpoint(artifact_path, model.state_dict(), metadata)
    return metrics


def train_all_models(data_dir, artifact_dir, seed=42, epochs=35):
    root = Path(data_dir)
    artifacts = Path(artifact_dir)
    return {
        "forecast": train_forecaster(root / "weekly_waste.csv", artifacts / "paper_waste_forecaster.pt",
                                      seed=seed, epochs=epochs),
        "ranker": train_ranker(root / "ranking_candidates.csv", artifacts / "recycler_ranker.pt",
                                seed=seed, epochs=epochs),
        "aggregation": train_aggregation_model(root / "aggregation_candidates.csv",
                                                artifacts / "aggregation_scorer.pt",
                                                seed=seed, epochs=epochs),
    }
