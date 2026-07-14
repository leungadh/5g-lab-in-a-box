# TODO — 5G Lab-in-a-Box

Next steps, in priority order. The theme: turn the scaffold into a **running lab with real traffic**. Nothing downstream is real until the lab stands up (step 2).

Status legend: `[ ]` open · `[~]` in progress · `[x]` done.

## 0. Ship what's pending
- [ ] Push local commits (detector, diagrams, PLATFORM.md, CI) to GitHub.
- [ ] Add repo **description** and **topics** on GitHub (`5g`, `open5gs`, `free5gc`, `ueransim`, `network-security`, `gtp`, `pfcp`, `infrastructure-as-code`, `anomaly-detection`).

## 1. Stand up the lab — Roadmap Phase 0→1  ← the gate
- [ ] Prepare the Intel Ubuntu host per [`docs/PLATFORM.md`](docs/PLATFORM.md): `make bootstrap`, build/load `gtp5g`.
- [ ] Populate the Open5GS NF configs (still TODO stubs): pull upstream defaults, reconcile with `.env` (PLMN, TAC, SST/SD, subnet).
- [ ] Install UERANSIM; reconcile `gnb.yaml` / `ue.yaml` with `.env`.
- [ ] `make up → provision-subscriber → ran-up → smoke-test`.
- [ ] **DoD:** one UE reaches the internet through the UPF.

## 2. Exercise the attacks — Phase 2
- [ ] Run each `attacks/` script against the live core; harden bodies from stubs to reliable generators.
- [ ] Confirm each produces an observable effect (logs, resource use, dropped/queued packets).
- [ ] Write a short per-attack note (what it does, what a defender sees, mitigations).

## 3. Capture real data — Phase 3
- [ ] `capture/run_labeled_dataset.sh` → benign + each attack, labeled.
- [ ] `capture/extract_features.py` → real `features.parquet` (replaces synthetic).
- [ ] **DoD:** a labeled feature set covering benign + every attack class.

## 4. Re-run the baseline detector on real captures — Phase 5
- [x] Build baseline detector (`detector/`): IsolationForest + optional autoencoder, verified on synthetic data (ROC-AUC ~0.985).
- [ ] Run on **real** captures: `make detector-train DATA=capture/data/features.parquet`.
- [ ] Tune threshold / contamination; record which classes hold up (expect messier-than-synthetic numbers).

## 5. Close the signaling-storm gap
- [ ] Add an N2/NGAP registration-rate feature to `extract_features.py` (capture NGAP/SCTP).
- [ ] Confirm `signaling_storm` becomes detectable (currently only weakly flagged).

## 6. Harden & prove it out — Phase 4 + advisory track
- [ ] Validate the Ansible playbook reproduces a host from scratch, idempotently.
- [ ] Smoke-test the **free5GC** alternate profile with the same tooling.
- [ ] Record a bring-up → attack → detection demo (the credibility artifact).
- [ ] Short "how this maps to real MNO risk" note tying N3/N4 abuse to GSMA/3GPP guidance.

## 7. Scale the detector — DGX Spark (post-baseline)
- [ ] Sequence model over consecutive windows (temporal structure the per-window baseline misses).
- [ ] Graph model over TEID/session relationships (slow session abuse, signaling storms).

---

**Most valuable next move:** step 1 — a live lab unblocks everything else.
