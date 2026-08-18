# Detection run — DGX Spark (ARM64, GPU)

Detection runs with the lab **fully ported to the NVIDIA DGX Spark**: the 5G core, RAN, attacks,
capture, and model training all run natively on ARM64, with the autoencoder trained on the GB10
GPU. The headline results below are from the **latest run (a clean full-restart of the lab)**; an
earlier, larger capture is kept for reference. Companion to the x86 run in
[`../Sample_run.md`](../Sample_run.md).

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
- **Latest run (clean restart): 291 windows** (1.0s), labels: `benign, gtpu_flood,
  gtpu_malformed, pfcp_assoc_abuse, pfcp_session_flood`. Split: train(benign)=71, test=220
  (48 benign + 43 of each attack class). A smaller capture than the earlier 585-window run.

## Results

Semi-supervised (train on benign only, threshold at the 99th percentile of benign score).
**Latest run (291 windows):**

| Model | Device | ROC-AUC | Precision | Recall (all attacks) | F1 | Benign false-alarm |
|---|---|---|---|---|---|---|
| IsolationForest | CPU | 0.857 | 0.000 | 0.000 | 0.000 | 6.2% |
| Autoencoder | **GB10 GPU** | **1.000** | 0.983 | **1.000** | 0.991 | 6.2% |

The **autoencoder** flagged **100% of attack windows in every class** (gtpu_flood, gtpu_malformed,
pfcp_assoc_abuse, pfcp_session_flood) at a 6.2% benign false-alarm. The **IsolationForest** shows
ROC-AUC 0.857 (partial separability) but **0% recall at its operating threshold** — at the
99th-percentile cut it flagged nothing (see the note below).

**Earlier run (larger capture, for reference) — 585 windows, train(benign)=143:**

| Model | Device | ROC-AUC | Recall (all attacks) | Benign false-alarm |
|---|---|---|---|---|
| IsolationForest | CPU | 0.989 | 1.000 | 9.4% |
| Autoencoder | **GB10 GPU** | **1.000** | 1.000 | 5.2% |

## Notes — reading the IsolationForest result honestly

- The tree baseline **degraded on the smaller dataset**: with only 71 benign training windows, its
  99th-percentile operating threshold sat above every attack score, so recall fell to 0 — even
  though the ROC-AUC (0.857) shows the scores are *partly* separable. The larger 585-window run
  recovered it (0.989 / 100% recall), so this is a **data-size / threshold effect, not a code
  regression**.
- The **GPU autoencoder stayed robust — ROC-AUC 1.000, 100% recall — on the same small dataset**.
  A concrete illustration of why the neural model (and the GPU that trains it) is the reliable
  detector, with the tree model as a cheap cross-check rather than the primary.
- Both are tunable via `--contamination` / the operating threshold; lowering the IsolationForest
  threshold — or capturing more benign — restores its recall at the cost of more false alarms.
- Takeaway: prefer the autoencoder as the primary detector; treat IsolationForest as a fast sanity
  check whose operating point needs enough benign data to sit correctly.

## Reproduce

```bash
# core + RAN up (see docs/DGX_ARM_PORTING.md "Verified end-to-end bring-up")
sudo -v
capture/run_labeled_dataset_docker.sh
python3 capture/extract_features.py capture/pcaps/*.pcap -o capture/data/features.parquet --window 1.0
python3 detector/baseline.py --data capture/data/features.parquet --model both
```
