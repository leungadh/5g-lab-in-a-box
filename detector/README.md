# detector/ — Baseline GTP/PFCP anomaly detector (Phase 5)

The handoff from the lab (Idea 1) to the anomaly detector (Idea 2). It consumes the windowed features from [`../capture/extract_features.py`](../capture/extract_features.py) (schema in [`../capture/FEATURES.md`](../capture/FEATURES.md)) and flags anomalous windows.

Deliberately simple and CPU-only — this is the proof-of-concept baseline that establishes the pipeline works end to end, *before* scaling to heavier sequence/graph models on the DGX Spark.

## Approach

Semi-supervised anomaly detection: **train on benign windows only**, then score every window by how far it departs from normal. Higher score = more anomalous.

- **IsolationForest** (`--model isoforest`) — sklearn, fast, no GPU. First signal.
- **Autoencoder** (`--model autoencoder`) — small PyTorch MLP; anomaly score = reconstruction error. Optional (needs `torch`). This is the piece that later grows into the DGX Spark models.

Primary metric is **ROC-AUC** (threshold-free). We also pick an operating threshold at the 99th percentile of benign scores and report precision / recall / F1 there, plus **per-attack-class recall** so you see which techniques are caught.

## Install & run

```bash
pip install -r requirements.txt          # torch optional

# 1. Validate on synthetic data (no captures needed yet)
python3 baseline.py --synth --model isoforest

# 2. Run on real captured features
python3 baseline.py --data ../capture/data/features.parquet --model isoforest

# 3. Both models (autoencoder if torch present)
python3 baseline.py --synth --model both
```

Or via the repo Makefile: `make detector-synth`, `make detector-train`.

Outputs land in `detector/out/`: `scored_<model>.csv` (every test window + `anomaly_score` + `flagged`) and `report_<model>.txt`.

## Files

| File | Purpose |
|---|---|
| `data.py` | Load features; feature columns; **synthetic generator** matching FEATURES.md |
| `models.py` | `IsoForestDetector`, `AutoencoderDetector` (both fit-on-benign, score) |
| `metrics.py` | ROC-AUC, P/R/F1, per-class recall, threshold selection |
| `baseline.py` | CLI: load/split → train → score → report |

## Interpreting results

- **ROC-AUC near 1.0** — attack windows separate cleanly from benign.
- **Per-class recall** — volume/structure attacks (GTP-U flood, malformed, PFCP floods) should score high; subtle ones lower.
- **Benign false-alarm rate** — should sit near your `--contamination` (default 5%).

## Known gap (be honest in the demo)

The feature schema currently parses **N3 (GTP-U) and N4 (PFCP)** only. `signaling_storm` is an **N2/NGAP** technique, so it has no dedicated feature yet and the baseline catches it only weakly. Closing this means adding an N2 registration-rate feature to `extract_features.py` (and capturing NGAP/SCTP). Tracked as a next step in [`../docs/ROADMAP.md`](../docs/ROADMAP.md).

## Next (DGX Spark)

Once the baseline clears its bar, move to sequence models over consecutive windows (temporal structure the per-window model misses) and a graph over TEID/session relationships — the models that actually catch signaling storms and slow session abuse.
