# How the Detection Works — and the First Real Training Run

The idea: **collect attack data in the lab, feed it to machine learning, and get a model that flags future attacks.** This document explains how that works, what to realistically expect, and the concrete steps to do it for the first time on real captured traffic.

The building blocks already exist in the repo — [`capture/`](../capture/), [`capture/extract_features.py`](../capture/extract_features.py), and [`detector/`](../detector/). What's left is running them on live traffic.

---

## The pipeline in plain terms

A model can't read raw network packets — it needs numbers. So the flow is four steps:

```
capture traffic  →  turn it into numbers  →  train a model  →  the model flags suspicious traffic
   (N3 / N4)         (per-window features)      (detector/)         (on new, unseen traffic)
```

1. **Capture** — `capture/capture.sh` records traffic on the N3 (GTP-U) and N4 (PFCP) interfaces to pcap files.
2. **Featurize** — `extract_features.py` slices each recording into short time-windows and, for each window, computes a row of numbers: packet rate, byte rate, malformed-packet fraction, TEID churn, PFCP message counts, inter-arrival timing, etc. (schema in [`../capture/FEATURES.md`](../capture/FEATURES.md)).
3. **Train** — `detector/` fits a model on that table of numbers.
4. **Detect** — the trained model scores new windows and raises an alert on the anomalous ones. That last step is "identify future attacks."

## Two ways a model identifies attacks

Both are worth having; they cover each other's blind spots.

| Approach | How it learns | Strength | Weakness |
|---|---|---|---|
| **Anomaly detection** (unsupervised) — *already built: IsolationForest + small autoencoder* | Learn what "normal" looks like; flag anything that deviates | Can catch attacks it has **never seen before** | More false alarms — unusual-but-harmless traffic can trip it |
| **Supervised classification** — *next step* | Learn from labeled examples of each attack | Precise on known attacks; can **name** the attack type | A genuinely novel attack it never saw may slip past |

The strongest setup runs both: the classifier names known attacks, the anomaly model catches the novel stuff.

## Why this lab is unusually good for it

Training a detector needs traffic tagged "normal" vs "attack" — and getting those labels is usually the hard, scarce part. Here the lab **launches the attacks itself**, so it knows exactly which traffic was malicious and when. Every capture is **labeled automatically, for free** — the "labeled by construction" idea. That clean labeled dataset is what makes a good detector possible.

## Honest limitations (set expectations)

- **Lab data is not carrier data.** A model trained only on this lab's synthetic traffic will do well *in the lab*, but real 5G networks are far messier. Deployed for real, it would need realistic, diverse "normal" traffic to learn from — otherwise it learns "lab-normal," not "world-normal," and would false-alarm in production. **The lab proves the approach and makes the demo; real deployment is a bigger data problem.**
- **"Future" is relative.** The model catches attacks that resemble learned patterns or that deviate from normal. A subtle, genuinely new technique can still evade it — which is exactly why the anomaly model (catch-the-weird) matters alongside the classifier. Detection is never "set and forget."
- **False positives are the real cost.** In practice, tuning the alert threshold to catch attacks without drowning in false alarms is most of the work.
- **The N2 gap.** `signaling_storm` is an N2/NGAP attack, but the feature pipeline currently watches N3/N4 only, so it's caught weakly. Closing it means adding an N2 registration-rate feature (tracked in [`TODO.md`](../TODO.md)).

## Current status

The baseline detector already ran on **synthetic** data and separated attacks from normal very cleanly (ROC-AUC ≈ 0.985 — see [`detector/README.md`](../detector/README.md)). The next milestone is doing it on **real captured traffic** from the running lab.

---

## The first real training run — step by step

Do this once the lab is up and a UE is attached (see [`PLATFORM.md`](PLATFORM.md)).

### 1. Confirm the lab is live and passing traffic
```bash
ip addr show uesimtun0        # UE has an IP (e.g. 10.45.0.2)
# generate some benign user traffic so "normal" isn't just silence:
ping -I uesimtun0 10.45.0.1 &   # or any lab-reachable target; keep light traffic flowing
```

### 2. Build a labeled dataset (benign + each attack, tagged)
```bash
pip3 install --break-system-packages scapy pandas pyarrow
./capture/run_labeled_dataset.sh
```
This records a benign baseline, then each attack class in turn, tagging every window by what was running. Result: a folder of labeled pcaps.

> **Path B note (native UPF on the host):** N3/N4 traffic is on the host, not the Docker bridge, so point the capture at the host interfaces. If `capture.sh` comes back empty, capture `ogstun` and the loopback where the UPF binds instead of the container bridge — ask and I'll adjust `capture.sh` for the native-UPF layout.

### 3. Turn the captures into a feature table
```bash
python3 capture/extract_features.py "capture/pcaps/*.pcap" \
  -o capture/data/features.parquet --window 1.0
```
You now have `features.parquet` — the labeled numbers table, one row per 1-second window.

### 4. Train and evaluate the detector
```bash
make detector-train DATA=capture/data/features.parquet
# or: python3 detector/baseline.py --data capture/data/features.parquet --model both
```

### What to look at
- **ROC-AUC** — how cleanly attacks separate from normal (1.0 = perfect, 0.5 = coin-flip). Expect **lower and messier than the synthetic 0.985** — real traffic is noisier. That's honest and fine.
- **Per-class recall** — which attacks it catches. Volume/structure attacks (floods, malformed) should score high; `signaling_storm` low (the N2 gap).
- **Benign false-alarm rate** — should sit near your chosen threshold; if it's high, the "normal" data wasn't varied enough (add more, and busier, benign traffic in step 1).

### After the baseline works
- Capture **more and more varied benign traffic** — the single biggest lever on real-world quality.
- Add the **N2 registration-rate feature** to close the signaling-storm gap.
- Move to the heavier models (sequence/graph over windows) for the subtle, slow attacks the per-window baseline misses — the DGX Spark step in [`ROADMAP.md`](ROADMAP.md).

---

**In one line:** the lab generates cleanly-labeled attack + benign traffic, `extract_features` turns it into numbers, and `detector/` learns to flag anomalies — a working proof of the approach, with a clear path from lab demo toward something deployable.
