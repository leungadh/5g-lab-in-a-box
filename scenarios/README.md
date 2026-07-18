# scenarios/ — Traffic-scenario generator with ground-truth labels

Turns the lab into a **labeled dataset factory**. Instead of running one attack per pcap and labeling by filename, you play a *scenario* — a scheduled mix of benign control-plane flows and injected anomalies — and the runner emits a **sidecar** recording exactly which class was on the wire during which time range. Capture runs in parallel; [`join.py`](join.py) maps capture windows to those labels.

See [`../docs/DATASET.md`](../docs/DATASET.md) for the full design and rationale.

## Pieces

| File | Purpose |
|---|---|
| `schema.py` | `LabelEvent` + `RunManifest`, the sidecar format, writers/loaders, class list |
| `library.py` | Declarative `Scenario` / `Step` specs — benign flows (nr-cli) and anomalies (attacks/) |
| `runner.py` | Timeline orchestrator: play a scenario, record time ranges, emit the sidecar |
| `join.py` | Interval join: capture windows → class labels (supervised, multi-class) |

## The sidecar (per run)

Each run writes `out/<run_id>/`:

- `labels.jsonl` — one `LabelEvent` per line: `{start_ts, end_ts, cls, event, interface, scenario_id, params}`.
- `manifest.json` — provenance: core, seed, git SHA, tool versions, scenario, event count.

Because the generator knows what it ran and when, the data is **supervised by construction** — no hand-labeling.

## Usage

```bash
# list scenarios
python3 runner.py --list

# validate the label pipeline with NO live core (emits sidecar only)
python3 runner.py --scenario benign_baseline --dry-run

# real run (lab must be up; run capture in parallel on the same host)
make capture DURATION=40 &                 # from repo root
python3 runner.py --scenario gtpu_malformed_mixed --core open5gs

# join a capture's features to the run's labels
python3 join.py \
  --features ../capture/data/features.parquet \
  --labels out/<run_id>/labels.jsonl \
  --out ../capture/data/features_labeled.parquet
```

Then train the detector on the labeled table: `make detector-train DATA=capture/data/features_labeled.parquet`.

## Adding scenarios

Append a `Scenario` to `SCENARIOS` in `library.py`. Benign steps carry an `nr_cli` command; anomaly steps carry an `attack` path + args (reusing `attacks/`). Keep durations and the `--seed` fixed so runs replay identically.

## Status & limits

Skeleton: two scenarios wired (one benign, one mixed). Benign register / PDU / release / deregister drive cleanly via `nr-cli`; **handover** needs a ≥2-gNB topology and **periodic TAU** is timer-driven — both are stretch additions (see `../docs/DATASET.md`). Run the generator and capture on the **same host** so timestamps share one clock.
