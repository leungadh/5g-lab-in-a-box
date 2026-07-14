# Roadmap

Milestones from empty host to a labeled dataset feeding Idea 2. Each phase has a definition of done (DoD) you can demo.

## Phase 0 — Host & bring-up (foundation)
- [ ] `make bootstrap` prepares an Ubuntu host: docker, `gtp5g` kernel module for the Open5GS UPF, `ip_forward`, N6 NAT.
- [ ] `make up` brings the Open5GS core + WebUI online; all NFs register with the NRF.
- [ ] `make provision-subscriber` adds the test IMSI/keys from `.env`.
- **DoD:** WebUI reachable, subscriber present, `docker compose ps` all healthy.

## Phase 1 — End-to-end data path
- [ ] `make ran-up` starts the UERANSIM gNB (N2 to AMF) then the UE.
- [ ] UE receives an IP on the PDU session; `make smoke-test` passes a ping through N6.
- **DoD:** one UE reaches the internet through the UPF. This is the "it's alive" demo.

## Phase 2 — Attack surface
- [ ] `attacks/gtpu/` — malformed GTP-U (bad message type, bogus TEID, extension-header abuse) and a tunnel flood.
- [ ] `attacks/pfcp/` — PFCP session-establishment flood and association abuse.
- [ ] `attacks/signaling/` — registration/auth storm via repeated UE attach.
- **DoD:** each script produces observable effect (logs, resource use, dropped/queued packets) captured in a short writeup per attack.

## Phase 3 — Capture & feature pipeline (bridge to Idea 2)
- [ ] `make capture` records N3/N4 pcaps with rotation.
- [ ] `capture/extract_features.py` turns pcaps into windowed feature rows.
- [ ] A capture harness runs benign + each attack in turn, tagging windows → **labeled dataset**.
- **DoD:** a `features.parquet` with a `label` column covering benign + every attack class.

## Phase 4 — IaC hardening & reproducibility
- [ ] Ansible playbook reproduces the host from scratch, idempotently.
- [ ] Terraform stub stands up the VM (cloud or libvirt) end-to-end.
- [ ] free5GC alternate profile validated with the same tooling.
- **DoD:** `terraform apply && make bootstrap && make up && make smoke-test` from nothing.

## Phase 5 — Handoff to Idea 2 (GTP/PFCP anomaly detector)
- [x] Dataset schema frozen and documented (`capture/FEATURES.md`).
- [x] Baseline model (IsolationForest + optional autoencoder) built in `detector/`, verified on synthetic data (ROC-AUC ~0.985) as a CPU sanity check.
- [ ] Run the baseline on **real** captures; tune threshold/contamination.
- [ ] Add an N2/NGAP registration-rate feature so `signaling_storm` becomes detectable (current known gap).
- [ ] Training moves to **DGX Spark**; heavier model (sequence/graph over flows) for signaling storms and session abuse.
- **DoD:** detector flags held-out attack windows above a benign baseline; becomes the AI-firewall demo asset.

> Running task checklist: see [`../TODO.md`](../TODO.md).

## Credibility / advisory deliverables (parallel track)
- [ ] Per-attack writeups (what it does, what a defender sees, mitigations).
- [ ] A short "how this maps to real MNO risk" note tying N3/N4 abuse to GSMA/3GPP security guidance.
- [ ] Recorded demo: bring-up → attack → detection.
