# Session Handoff

_Last updated: 2026-07-31. A resume point so we can pick up quickly next time._

## Where the lab stands

The lab is **fully ported to the NVIDIA DGX Spark (GB10, ARM64)** and runs end-to-end,
all in Docker on the `open5gs-core` network:

- **5G core** — Open5GS built from source for arm64 (`deploy/open5gs/Dockerfile`); all 12 NFs
  healthy through SCP/NRF; stable SMF↔UPF PFCP. Configs are dockerized for the container network
  via `scripts/dockerize_open5gs_configs.py`. The UPF datapath (ogstun + egress NAT) is set up
  automatically by `deploy/open5gs/docker-entrypoint.sh`.
- **RAN** — containerized UERANSIM (`deploy/ran/ueransim/`, run via `run-containers.sh up`,
  `CORE_NET=open5gs-core`). UE attaches, `uesimtun0` gets a 10.45.0.0/16 address, and internet
  egress works.
- **Attacks + capture** — attacker containers hit the UPF on N3/N4; capture is from inside the
  UPF network namespace (`capture/run_labeled_dataset_docker.sh`).
- **Detection on the GPU** — labeled dataset of 585 windows; IsolationForest **0.989** and the
  autoencoder **1.000 on the GB10**, 100% recall on all four attack classes. The autoencoder now
  has CUDA support (`detector/models.py`). Recorded in `docs/DGX_detection_run.md`.

## Key docs produced this session

- `docs/DGX_ARM_PORTING.md` — the verified arm64/DGX bring-up (the ground-truth recipe).
- `docs/DGX_detection_run.md` — the first ARM64/GPU detection run + results.
- `docs/decks/5g-gpu-detection.pptx` — teaching deck on the GPU detection (data → training → proof → interpretation).
- `docs/5g-lab-demo-runbook.docx` — live demo runbook (prep + 5-beat flow + commands + fallback).
- `docs/2_slice_demo.md` — plan for a two-slice network slicing extension (not built yet).

## Git status at handoff

- One local commit not yet on GitHub: `69d06fe` (the two-slice demo plan). **Run
  `git push origin main` from the Mac** to save it. Everything else is pushed.
- Reminder: on the DGX, pull new files surgically (`git fetch` + `git checkout origin/main -- <path>`)
  because the DGX has machine-specific local edits to `deploy/open5gs/configs/*.yaml` (dockerized)
  and its `.env`. Do NOT re-clone on the DGX.

## To bring the lab back up (DGX)

```bash
cd ~/Projects/5g-lab-in-a-box
docker compose -f deploy/open5gs/docker-compose.yml --env-file deploy/open5gs/.env up -d \
  mongo nrf scp amf ausf udm udr pcf bsf nssf smf upf
CORE_NET=open5gs-core deploy/ran/ueransim/run-containers.sh up
docker exec ue ping -c3 -I uesimtun0 8.8.8.8      # confirm data path
```
Data persists (Mongo volume, pcaps, features) — no re-provision or re-capture needed.

## Candidate next steps

1. **Build the two-slice slicing demo** per `docs/2_slice_demo.md` (Phase 1 first: core config +
   `upf-iot`, validate both UPFs before touching the RAN).
2. **Scale the detector** — larger/noisier captures + the Phase-5 sequence/graph models that
   actually stress the GB10 GPU; stress with subtler (low-and-slow) attacks; tune the operating
   threshold to a target false-alarm budget.
3. **cSRX firewall on ARM** — the one remaining x86-only piece, pending a Juniper arm64 image
   (see `docs/FIREWALL.md` / `docs/DGX_ARM_PORTING.md`).
