# Sample Run — First Real Detection on Captured N3/N4 Traffic

A record of the first end-to-end detection run on **real captured traffic** (not the synthetic sanity check): capture N3/N4 → extract features → train the baseline detector → flag attacks.

## Environment

| Item | Value |
|---|---|
| Host | Ubuntu 24.04, kernel `6.17.0-14-generic`, x86-64, bare metal |
| Core | Open5GS 2.7.5 (control plane in Docker) |
| UPF | **native on host** (Path B) — container TUN creation is blocked on this host's kernels |
| RAN | UERANSIM v3.3.0 (simulated gNB + UE) |
| UE | registered, PDU session up, `uesimtun0` = `10.45.0.2/16` |
| Known gaps | internet egress (N6) not working — host-forwarding issue on this kernel; not needed for the security work |

## What was tested

The full detection pipeline on live lab traffic:

```
capture/ (tcpdump N3+N4)  →  extract_features.py  →  detector/ (IsolationForest)  →  attack flagged
```

## Steps performed

**1. Capture setup (Path B fix).** `capture.sh` was pointed at the Docker bridge by default, but with the native UPF the N3/N4 traffic is on the host (N3/GTP-U on loopback `127.0.0.1↔127.0.0.7`, attacks on `127.0.0.1`, N4/PFCP to the host IP). Fixed by capturing on `any`:

```bash
CAPTURE_IFACE=any   # now the default in capture.sh
```

**2. Generate + capture labeled traffic.**
- Attacks: `run_labeled_dataset.sh` injected each attack class onto `127.0.0.1` and captured it.
- Benign: the UE uplink was not reliably carrying traffic (same data-path issue as egress), so benign was generated **directly** as steady, well-formed GTP-U — the `gtpu_flood` tool at a *low* rate (a flood is the same packets, fast):

```bash
python3 attacks/gtpu/gtpu_flood.py --target 127.0.0.1 --i-own-this-lab --count 600 --rate 5 &
./capture/capture.sh 120 benign
```

Resulting captures (healthy sizes — an empty capture is ~1.8 KB):

| pcap | size |
|---|---|
| `benign` | 339 KB |
| `gtpu_flood` | 2.9 MB |
| `gtpu_malformed` | 228 KB |
| `pfcp_assoc_abuse` | 247 KB |
| `pfcp_session_flood` | 267 KB |

**3. Extract features.**
```bash
python3 capture/extract_features.py "capture/pcaps/*.pcap" -o capture/data/features.parquet --window 1.0
# -> 270 windows; labels: benign, gtpu_flood, gtpu_malformed, pfcp_assoc_abuse, pfcp_session_flood
```

**4. Train + evaluate.**
```bash
make detector-train DATA=capture/data/features.parquet
```

## Results

### Run 1 — thin benign (failed, instructive)

The first benign capture was only ~7 KB (traffic wasn't flowing during the window), giving just **10** benign training windows.

| Metric | Value |
|---|---|
| `train(benign)` | 10 |
| ROC-AUC | **0.355** (worse than random) |
| recall (all attacks) | 0.000 |
| benign false-alarm | 0.429 |

With a degenerate 10-window "normal," the model learned nothing. The built-in guard (ROC-AUC < 0.75) correctly failed the run. **Lesson: the benign baseline is the single biggest lever.**

### Run 2 — proper benign (success)

After capturing ~120 s of steady benign GTP-U → **68** benign training windows.

| Metric | Value |
|---|---|
| rows / `train(benign)` / `test` | 270 / 68 / 202 |
| **ROC-AUC** | **0.958** |
| precision | 0.981 |
| recall (all attacks) | 1.000 |
| F1 | 0.990 |
| benign false-alarm | 0.065 |

Per-class recall:

| Class | Windows | Recall |
|---|---|---|
| `gtpu_flood` | 29 | 1.000 |
| `gtpu_malformed` | 60 | 1.000 |
| `pfcp_assoc_abuse` | 34 | 1.000 |
| `pfcp_session_flood` | 33 | 1.000 |

Every attack window was flagged; benign false alarms sat near the 5% contamination setting. Scored output saved to `detector/out/scored_isoforest.csv` and `detector/out/report_isoforest.txt`.

## Interpretation & honest caveats

- **The pipeline works end to end on real captures** — this is the Phase 5 baseline validated on live traffic, not just synthetic.
- **Benign and attacks are both injected** here, and the classes are very distinct (benign = slow valid GTP-U; floods = fast; malformed = broken headers; PFCP attacks = N4 traffic benign never shows). So the separation is cleaner than real-world traffic would be. This proves the **approach and plumbing**, not production accuracy.
- **`signaling_storm` is absent** — it's an N2/NGAP attack and the feature pipeline watches N3/N4 only (known gap).
- This is **anomaly detection** (flags "abnormal"); it does not yet *name* the attack class.

## Reproduce

```bash
# lab up (Path B): native UPF running, control plane up, UE attached
sudo ./scripts/host-forward.sh        # or the inline host-networking commands
make up && make ran-up

# benign + attacks, captured and labeled
rm -f capture/pcaps/*.pcap
python3 attacks/gtpu/gtpu_flood.py --target 127.0.0.1 --i-own-this-lab --count 600 --rate 5 &
./capture/capture.sh 120 benign
./capture/run_labeled_dataset.sh

# features + detector
python3 capture/extract_features.py "capture/pcaps/*.pcap" -o capture/data/features.parquet --window 1.0
make detector-train DATA=capture/data/features.parquet
```

## Next steps

- Tune the false-alarm rate (`--contamination 0.02`) and read the precision/recall trade-off.
- Enrich benign (varied rates, some PFCP heartbeat) so "normal" is less artificially clean.
- Add a supervised classifier that **names** the attack, not just flags it.
- Close the N2 gap so `signaling_storm` is detectable.
- Scale to the autoencoder / sequence / graph models (DGX Spark) for subtler attacks.

See [`docs/DETECTION.md`](docs/DETECTION.md) for how the detection works and [`docs/ROADMAP.md`](docs/ROADMAP.md) for the milestone track.
