# Dataset Design — Traffic-Scenario Generator with Ground-Truth Labels

This is the plan for turning the lab into a **labeled dataset factory** for the anomaly detector (Idea 2). It documents the label schema, the generator design, and the known limitations. The skeleton lives in [`../scenarios/`](../scenarios/).

## The core upgrade

Today the lab labels traffic **by pcap filename**: `capture/run_labeled_dataset.sh` runs one attack at a time and `extract_features.py` reads the class from the filename. That works, but it only produces clean single-class blocks and can't represent realistic traffic where benign and malicious flows overlap.

The upgrade changes the model to **one continuous mixed timeline + a sidecar label file** (timestamp ranges → class):

```
            OLD                                    NEW
  attack A → a.pcap (label=A)          one long capture over a mixed scenario
  attack B → b.pcap (label=B)                        +
  benign   → c.pcap (label=benign)     labels.jsonl: [ {t0..t1: benign},
  label = filename                                     {t2..t3: gtpu_flood},
                                                        {t4..t5: benign}, ... ]
                                       label = timestamp overlap (join.py)
```

Benefits: realistic overlapping traffic, multi-class supervision, exact provenance, and no hand-labeling — the generator knows what it ran and when.

## Sidecar label schema

Every run writes `scenarios/out/<run_id>/` containing two files.

### `labels.jsonl` — one event per line
```json
{"start_ts": 1752700000.0, "end_ts": 1752700006.0, "cls": "gtpu_malformed",
 "event": "gtpu_malformed", "interface": "N3", "scenario_id": "gtpu_malformed_mixed",
 "params": {}}
```

| Field | Meaning |
|---|---|
| `start_ts`, `end_ts` | epoch seconds, `[start, end)` |
| `cls` | ground-truth class — `benign` or an attack class |
| `event` | human-readable step name (`pdu_establish`, `gtpu_flood`, …) |
| `interface` | N1 / N2 / N3 / N4 |
| `scenario_id` | which scenario produced it |
| `params` | free-form (rate, count, target, …) for provenance |

Classes: `benign`, `gtpu_malformed`, `gtpu_flood`, `pfcp_session_flood`, `pfcp_assoc_abuse`, `signaling_storm`.

### `manifest.json` — run provenance
`run_id`, `created`, `core` (open5gs/free5gc), `seed`, `git_sha`, `scenario`, `n_events`, `tool_versions`. This makes each dataset reproducible and self-describing.

## Feature ↔ label join

`scenarios/join.py` maps each capture window `[w_start, w_start+len)` to a class by **timestamp overlap** with the events:

- anomaly events beat `benign`;
- among overlapping anomalies, the largest overlap wins;
- windows covered by no event default to `benign`.

Result: a single mixed capture → a supervised, multi-class feature table the detector trains on directly. This will replace the filename-based labeling in `extract_features.py` (which stays as the fast path for single-class captures).

## Scenario model

A `Scenario` is an ordered list of `Step`s (`scenarios/library.py`). Each step is either:

- **benign** — a UERANSIM `nr-cli` control-plane action (register, PDU establish/release, deregister), or a passive window carrying idle user traffic; or
- **anomaly** — an `attacks/` script invocation (reusing the existing, guarded generators).

The runner plays steps in order, timestamps the window each occupies, and emits the sidecar. Fixed durations + a fixed `--seed` make runs replay identically.

## Benign realism — what's easy vs hard

| Benign flow | Feasibility in UERANSIM | Notes |
|---|---|---|
| Registration / deregistration | Easy | UE start = initial registration; `nr-cli deregister` |
| PDU session establish / release | Easy | `nr-cli ps-establish` / `ps-release-all` |
| Idle / light user traffic | Easy | passive window |
| Handover | Hard | needs a **≥2-gNB** topology; simulator fidelity is limited |
| Periodic TAU | Medium | timer-driven (T3512); long wall-clock |

Ship register/PDU/deregister first; treat handover and TAU as stretch profiles. State these limits plainly wherever the dataset is described — accurate realism claims matter for advisory credibility.

## Dataset packaging

- **Versioned releases** with a short datasheet: what's inside, how generated, known gaps.
- **Splits by run, not by window** — all windows from one injection event must land in the same split, or the detector leaks (adjacent windows are near-duplicates).
- **Validation step** asserting the label join recovered the expected event count per scenario.

## Gotchas designed around

- **One clock.** Run the generator and `capture/` on the **same host** so event timestamps and packet timestamps agree; otherwise interval labels drift.
- **Dropped-before-logged.** Some malformed packets are dropped so early they barely appear — verify each anomaly is observable on the wire before trusting its label.
- **Determinism.** Fixed seed + fixed schedule; store the seed in the manifest.

## Suggested sequencing

1. Sidecar schema (`schema.py`) — done (skeleton).
2. Interval join (`join.py`) — done (skeleton); wire into `extract_features.py` next.
3. Scenario orchestrator + benign/mixed scenarios (`runner.py`, `library.py`) — skeleton done; expand the library.
4. Multi-class supervised detector path in `detector/` (now that labels are clean).
5. Packaging: datasheet + run-based splits + validation.

See [`../TODO.md`](../TODO.md) for the running checklist.
