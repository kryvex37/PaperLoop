"""Neural affinity scorer for spatial-temporal pickup bundles."""
import torch.nn as nn


class AggregationClusterScorer(nn.Module):
    def __init__(self, input_size=7):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 32), nn.ReLU(),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Linear(16, 1),
        )

    def forward(self, features):
        return self.network(features).squeeze(-1)
