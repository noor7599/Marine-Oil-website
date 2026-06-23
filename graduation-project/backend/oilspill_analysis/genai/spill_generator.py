import torch
import torch.nn as nn

class SpillGenerator(nn.Module):
    def __init__(self):
        super().__init__()

        self.encoder = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.ReLU()
        )

        self.fc = nn.Linear(32*100*100, 512)

        self.decoder = nn.Sequential(
            nn.Linear(512, 32*100*100),
            nn.ReLU(),
            nn.Unflatten(1, (32, 100, 100)),
            nn.Conv2d(32, 1, 3, padding=1),
            nn.Sigmoid()
        )

    def forward(self, x):
        B = x.shape[0]

        feat = self.encoder(x)
        feat = feat.view(B, -1)

        latent = self.fc(feat)
        out = self.decoder(latent)

        return out