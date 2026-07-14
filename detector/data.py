"""Data layer for the baseline detector.

Loads the windowed feature table produced by ../capture/extract_features.py
(see ../capture/FEATURES.md), and can synthesize a realistic feature set so the
detector runs before any real captures exist.
"""
from __future__ import annotations
import os
import numpy as np

# Feature columns the model consumes (everything except window_start + label).
FEATURE_COLS = [
    "n_pkts", "bytes_total", "pkt_rate", "n_gtpu", "n_pfcp",
    "gtpu_malformed_frac", "teid_unique", "teid_churn",
    "pfcp_est_req", "pfcp_assoc_req", "pfcp_heartbeat", "iat_mean",
]

BENIGN = "benign"
ATTACK_CLASSES = [
    "gtpu_malformed", "gtpu_flood",
    "pfcp_session_flood", "pfcp_assoc_abuse", "signaling_storm",
]


def load_features(path: str):
    """Read a features.parquet / .csv into a DataFrame."""
    import pandas as pd
    if path.endswith(".csv"):
        df = pd.read_csv(path)
    else:
        df = pd.read_parquet(path)
    missing = [c for c in FEATURE_COLS + ["label"] if c not in df.columns]
    if missing:
        raise ValueError(f"features file missing columns: {missing}")
    return df


def make_xy(df):
    """Return (X, y_binary, labels): X feature matrix, y=1 for any attack, 0 benign."""
    X = df[FEATURE_COLS].to_numpy(dtype=float)
    labels = df["label"].astype(str).to_numpy()
    y = (labels != BENIGN).astype(int)
    return X, y, labels


def synthesize(n_per_class: int = 400, seed: int = 7):
    """Generate a plausible labeled feature set matching FEATURES.md signatures.

    Benign windows plus each attack class, with the attack class perturbing the
    features that its real signature moves. Values are clipped to be non-negative.
    Returns a DataFrame.
    """
    import pandas as pd
    rng = np.random.default_rng(seed)
    rows = []

    def base_benign(n):
        pkts = rng.poisson(80, n).astype(float)
        gtpu = (pkts * rng.uniform(0.55, 0.75, n))
        pfcp = np.clip(rng.poisson(3, n).astype(float), 0, None)
        return {
            "n_pkts": pkts,
            "bytes_total": pkts * rng.uniform(500, 900, n),
            "pkt_rate": pkts,
            "n_gtpu": gtpu,
            "n_pfcp": pfcp,
            "gtpu_malformed_frac": np.clip(rng.normal(0.0, 0.01, n), 0, 1),
            "teid_unique": rng.integers(1, 4, n).astype(float),
            "teid_churn": rng.uniform(0.0, 0.05, n),
            "pfcp_est_req": np.clip(rng.poisson(0.3, n).astype(float), 0, None),
            "pfcp_assoc_req": np.zeros(n),
            "pfcp_heartbeat": np.clip(rng.poisson(1, n).astype(float), 0, None),
            "iat_mean": rng.uniform(0.008, 0.02, n),
        }

    def col(d, k, n):
        return d.get(k, np.zeros(n))

    for cls in [BENIGN] + ATTACK_CLASSES:
        n = n_per_class
        d = base_benign(n)
        if cls == "gtpu_malformed":
            d["gtpu_malformed_frac"] = np.clip(rng.uniform(0.25, 0.9, n), 0, 1)
            d["n_gtpu"] = d["n_gtpu"] * rng.uniform(1.5, 3.0, n)
            d["teid_churn"] = rng.uniform(0.1, 0.6, n)
            d["teid_unique"] = rng.integers(5, 40, n).astype(float)
        elif cls == "gtpu_flood":
            boost = rng.uniform(4, 12, n)
            d["n_pkts"] = d["n_pkts"] * boost
            d["pkt_rate"] = d["pkt_rate"] * boost
            d["n_gtpu"] = d["n_gtpu"] * boost
            d["bytes_total"] = d["bytes_total"] * boost
            d["teid_unique"] = rng.integers(1, 2, n).astype(float)  # focused on one TEID
            d["iat_mean"] = rng.uniform(0.001, 0.004, n)
        elif cls == "pfcp_session_flood":
            d["pfcp_est_req"] = rng.uniform(40, 120, n)
            d["n_pfcp"] = d["pfcp_est_req"] * rng.uniform(1.0, 1.4, n)
            d["n_pkts"] = d["n_pkts"] + d["n_pfcp"]
        elif cls == "pfcp_assoc_abuse":
            d["pfcp_assoc_req"] = rng.uniform(30, 90, n)
            d["pfcp_heartbeat"] = rng.uniform(20, 80, n)
            d["n_pfcp"] = d["pfcp_assoc_req"] + d["pfcp_heartbeat"]
            d["n_pkts"] = d["n_pkts"] + d["n_pfcp"]
        elif cls == "signaling_storm":
            # NOTE: N2/NGAP registration rate is not yet in the feature schema
            # (extract_features.py parses N3/N4 only). Modeled here as a mild,
            # broad elevation; see detector/README.md "Known gap".
            d["n_pkts"] = d["n_pkts"] * rng.uniform(1.2, 1.8, n)
            d["pkt_rate"] = d["pkt_rate"] * rng.uniform(1.2, 1.8, n)
            d["iat_mean"] = rng.uniform(0.004, 0.01, n)

        frame = {k: np.clip(col(d, k, n), 0, None) for k in FEATURE_COLS}
        frame["label"] = cls
        frame["window_start"] = np.arange(n, dtype=float)
        rows.append(pd.DataFrame(frame))

    return pd.concat(rows, ignore_index=True).sample(frac=1.0, random_state=seed).reset_index(drop=True)


def write_synth(path: str, n_per_class: int = 400, seed: int = 7):
    df = synthesize(n_per_class, seed)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if path.endswith(".csv"):
        df.to_csv(path, index=False)
    else:
        try:
            df.to_parquet(path, index=False)
        except Exception:
            path = path.replace(".parquet", ".csv")
            df.to_csv(path, index=False)
    return path, df
