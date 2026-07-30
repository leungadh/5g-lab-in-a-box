# Detection run — DGX Spark (ARM64, GPU)

First end-to-end detection run with the lab **fully ported to the NVIDIA DGX Spark**: the
5G core, RAN, attacks, capture, and model training all run natively on ARM64, with the
autoencoder trained on the GB10 GPU. Companion to the x86 run in [`../Sample_run.md`](../Sample_run.md).

## Platform

- **Host:** NVIDIA DGX Spark — GB10 (Grace-Blackwell), ARM64 (aarch64), DGX OS.
- **Layout:** all-Docker on the `open5gs-core` network. Open5GS built from source
  ([`../deploy/open5gs/Dockerfile`](../deploy/open5gs/Dockerfile)); UERANSIM containerized
  ([`../deploy/ran/ueransim/`](../deploy/ran/ueransim/)); UPF datapath (ogstun + NAT)
  configured by the image entrypoint. Container-native UPF (no Path B needed) and working
  internet egress — both improvements over the x86 host.
- **PyTorch:** `torch 2.11.0+cu128`, `cuda True`, device `NVIDIA GB10`.

## Dataset

- Captured from **inside the UPF network namespace** (nsenter + host tcpdump) — the
  authoritative UPF-side view of N3/N4. Runner:
  [`../capture/run_labeled_dataset_docker.sh`](../capture/run_labeled_dataset_docker.sh).
- Benign baseline = real UE traffic (ping over `uesimtun0`); attacks fired from a
  throwaway container at the UPF.
- **585 windows** (1.0s), labels: `benign, gtpu_flood, gtpu_malformed, pfcp_assoc_abuse,
  pfcp_session_flood`. Split: train(benign)=143, test=442.

## Results

Semi-supervised (train on benign only, threshold at the 99th percentile of benign score).

| Model | Device | ROC-AUC | Precision | Recall (all attacks) | F1 | Benign false-alarm |
|---|---|---|---|---|---|---|
| IsolationForest | CPU | 0.989 | 0.975 | 1.000 | 0.987 | 9.4% |
| Autoencoder | **GB10 GPU** | **1.000** | 0.986 | 1.000 | 0.993 | 5.2% |

Per-class recall = **1.000** for all four attack classes (gtpu_flood, gtpu_malformed,
pfcp_assoc_abuse, pfcp_session_flood), both models.

## Notes

- Both models beat the x86 run (IsoForest 0.958 there) — the cleaner UPF-netns capture
  vantage and attack windows sized to the capture window likely helped separation.
- At 585 windows the autoencoder is tiny; GPU vs CPU time is negligible here. The value is
  that the **training pipeline now runs on the GPU**, so scaling to a much larger capture
  and the heavier Phase-5 sequence/graph models offloads to the GB10.
- The benign false-alarm rate is tunable via `--contamination` / the operating threshold.

## Reproduce

```bash
# core + RAN up (see docs/DGX_ARM_PORTING.md "Verified end-to-end bring-up")
sudo -v
capture/run_labeled_dataset_docker.sh
python3 capture/extract_features.py capture/pcaps/*.pcap -o capture/data/features.parquet --window 1.0
python3 detector/baseline.py --data capture/data/features.parquet --model both
```
