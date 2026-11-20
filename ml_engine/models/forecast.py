"""Residual tabular regressor predicting mean and uncertainty of next-week kg."""
import torch
from torch import nn


class PaperWasteForecaster(nn.Module):
    def __init__(self, input_size):
        super().__init__()
        self.backbone = nn.Sequential(nn.Linear(input_size, 64), nn.ReLU(),
                                      nn.Linear(64, 32), nn.ReLU())
        self.mean_head = nn.Linear(32, 1)
        self.log_variance_head = nn.Linear(32, 1)
        nn.init.zeros_(self.mean_head.weight)
        nn.init.zeros_(self.mean_head.bias)

    def forward(self, features):
        hidden = self.backbone(features)
        # Start from a persistence forecast and learn a non-negative correction.
        mean = (features[:, 0] + self.mean_head(hidden).squeeze(-1)).clamp(min=0)
        log_variance = self.log_variance_head(hidden).squeeze(-1).clamp(-8, 2)
        return mean, log_variance


def gaussian_nll(mean, log_variance, target):
    return .5 * (log_variance + (target - mean).square() * torch.exp(-log_variance)).mean()
