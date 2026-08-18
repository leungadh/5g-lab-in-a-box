# Phase 2A run — Network slicing (two slices, two user planes)

A two-slice deployment built and validated on the DGX Spark (ARM64, all-Docker), with
**physical user-plane isolation proven**. Builds on the Phase 1 lab; companion to the
plan in [`2_slice_demo.md`](2_slice_demo.md) / [`Phase_2_Plan.md`](Phase_2_Plan.md).

## What was built

| | Slice A (existing) | Slice B (new) |
|---|---|---|
| S-NSSAI | SST=1 | SST=2 |
| DNN | `internet` | `iot` |
| UE subnet | 10.45.0.0/16 | 10.46.0.0/16 |
| UPF | `upf` | `upf-iot` |
| UE / IMSI | `ue` / `…001` | `ue-iot` / `…002` |

Shared control plane (unchanged): AMF, **NSSF**, SMF, NRF/SCP, UDM/UDR/AUSF/PCF, Mongo. One SMF
serves both slices, selecting the UPF by DNN.

## Config changes vs. single-slice

- **SMF** — DNN-tagged UPF peers (`upf`→internet, `upf-iot`→iot), a second session pool
  (10.46.0.0/16, dnn iot), and an `info` block advertising both slices+DNNs to the NRF (so the
  AMF can discover the SMF for either slice).
- **upf-iot** — new UPF container from the same `open5gs:arm64` image; the entrypoint reads
  `OGSTUN_ADDR=10.46.0.1/16` / `UE_SUBNET=10.46.0.0/16` to set up ogstun + NAT. Config mounted at
  the default `upf.yaml` path.
- **AMF** — `plmn_support.s_nssai` adds `sst: 2`.
- **NSSF** — `nsi` URI fixed from the loopback default (`127.0.0.10`) to the `nrf` service, and a
  second NSI entry added for SST=2.
- **Subscriber** — cloned `…001` → `…002` and retargeted its slice to SST=2 / DNN `iot`.
- **RAN** — gNB advertises SST 1+2; the UE template is parameterized (`UE_SUPI`/`UE_APN`/`UE_SST`
  via env), and `run-containers.sh` starts `ue` (slice 1) + `ue-iot` (slice 2).

## Validation

- **Control plane:** SMF holds a stable PFCP association to **both** UPFs; AMF/NSSF/SMF start clean
  with the slice config (no parse errors).
- **Attach + addressing:** `ue` → `uesimtun0 = 10.45.0.2` via `upf`; `ue-iot` → `10.46.0.2` via
  `upf-iot`. Both reach the internet through their own UPF (0% loss).
- **Isolation proof** — per-UPF capture on `ogstun` while both UEs pinged:

```
== upf ogstun (slice 1) — ONLY 10.45.x ==
IP 10.45.0.2 > 8.8.8.8: ICMP echo request ...
IP 8.8.8.8 > 10.45.0.2: ICMP echo reply ...
== upf-iot ogstun (slice 2) — ONLY 10.46.x ==
IP 10.46.0.2 > 8.8.8.8: ICMP echo request ...
IP 8.8.8.8 > 10.46.0.2: ICMP echo reply ...
```

Neither UPF ever saw the other slice's subnet → **the two slices ride physically separate user
planes.**

## Gotchas (folded into the notes)

- After changing SMF or UPF config, **recreate the SMF and both UPFs together**
  (`up -d --force-recreate upf upf-iot smf`) — recreating the SMF alone leaves a UPF holding a
  stale association to the dead SMF, and the new one's association retries fail until it times out.
- The **NSSF `nsi` URI defaults to loopback** (`127.0.0.10`), which never mattered single-slice
  (the AMF didn't query the NSSF); for multi-slice it must point at the `nrf` service.
- Kept **SST-only (no SD)** throughout for simplicity — consistent across AMF, NSSF, SMF,
  subscriber, gNB, and UE.

## Why this matters

Slicing is a **containment boundary**. This is the foundation for Phase 2B (MEC edge breakout) and
for the self-securing story: *flood one slice's UPF and show the other slice's user plane — and the
detector's per-UPF view — stays clean.*

## Reproduce (DGX)

```bash
# core with both UPFs
make up-dgx
docker compose -f deploy/open5gs/docker-compose.yml --env-file deploy/open5gs/.env up -d --force-recreate upf upf-iot smf
# subscriber …002 on slice 2 (one-time; persists in the mongo volume)
# RAN — two UEs on two slices
CORE_NET=open5gs-core deploy/ran/ueransim/run-containers.sh up
```
