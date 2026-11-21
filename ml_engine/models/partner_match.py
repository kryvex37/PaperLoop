"""Neural candidate scorer for FR-07 recycler recommendations."""
import torch.nn as nn


class RecyclerRankerNet(nn.Module):
    def __init__(self, input_size=6):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 32), nn.ReLU(),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Linear(16, 1),
        )

    def forward(self, features):
        return self.network(features).squeeze(-1)
