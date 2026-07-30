"""Baseline anomaly-detection models.

Two detectors, both semi-supervised: fit on benign windows only, then score any
window by how far it departs from "normal". Higher score = more anomalous.

- IsoForestDetector: sklearn IsolationForest. Fast, no GPU, good first signal.
- AutoencoderDetector: small PyTorch MLP autoencoder; anomaly score = reconstruction
  error. Optional — only used if torch is installed. This is the piece that later
  scales to the DGX Spark with sequence/graph variants.
"""
from __future__ import annotations
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


class IsoForestDetector:
    name = "isoforest"

    def __init__(self, contamination: float = 0.05, seed: int = 7):
        self.scaler = StandardScaler()
        self.clf = IsolationForest(
            n_estimators=200, contamination=contamination, random_state=seed
        )

    def fit(self, X_benign: np.ndarray) -> "IsoForestDetector":
        Xs = self.scaler.fit_transform(X_benign)
        self.clf.fit(Xs)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Anomaly score, higher = more anomalous."""
        Xs = self.scaler.transform(X)
        return -self.clf.score_samples(Xs)


class AutoencoderDetector:
    name = "autoencoder"

    def __init__(self, hidden=(16, 8), epochs: int = 80, lr: float = 1e-3, seed: int = 7,
                 device: str = "auto"):
        self.hidden = hidden
        self.epochs = epochs
        self.lr = lr
        self.seed = seed
        self.scaler = StandardScaler()
        self._torch = None
        self.net = None
        self.device_pref = device   # "auto" | "cuda" | "cpu"
        self.device = None

    @staticmethod
    def available() -> bool:
        try:
            import torch  # noqa: F401
            return True
        except Exception:
            return False

    def _build(self, d_in: int):
        import torch
        import torch.nn as nn
        torch.manual_seed(self.seed)
        h1, h2 = self.hidden
        self.net = nn.Sequential(
            nn.Linear(d_in, h1), nn.ReLU(),
            nn.Linear(h1, h2), nn.ReLU(),
            nn.Linear(h2, h1), nn.ReLU(),
            nn.Linear(h1, d_in),
        )
        self._torch = torch
        dev = self.device_pref
        if dev == "auto":
            dev = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(dev)
        self.net.to(self.device)
        if self.device.type == "cuda":
            print(f"[autoencoder] training on GPU: {torch.cuda.get_device_name(0)}")
        else:
            print("[autoencoder] training on CPU")

    def fit(self, X_benign: np.ndarray) -> "AutoencoderDetector":
        import torch
        Xs = self.scaler.fit_transform(X_benign).astype("float32")
        self._build(Xs.shape[1])
        X = torch.from_numpy(Xs).to(self.device)
        opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        loss_fn = torch.nn.MSELoss()
        self.net.train()
        for _ in range(self.epochs):
            opt.zero_grad()
            out = self.net(X)
            loss = loss_fn(out, X)
            loss.backward()
            opt.step()
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        torch = self._torch
        Xs = self.scaler.transform(X).astype("float32")
        self.net.eval()
        with torch.no_grad():
            recon = self.net(torch.from_numpy(Xs).to(self.device)).cpu().numpy()
        return ((Xs - recon) ** 2).mean(axis=1)  # per-row reconstruction MSE


def get_detector(name: str, contamination: float = 0.05, seed: int = 7):
    if name == "isoforest":
        return IsoForestDetector(contamination=contamination, seed=seed)
    if name == "autoencoder":
        if not AutoencoderDetector.available():
            raise RuntimeError("autoencoder needs PyTorch: pip install torch")
        return AutoencoderDetector(seed=seed)
    raise ValueError(f"unknown model '{name}' (isoforest|autoencoder)")
