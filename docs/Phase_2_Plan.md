# Phase 2 Plan — Network Slicing & MEC Security

Two future expansions of the lab: **(1) network slicing** and **(2) a MEC security demo**. This
plan gives the feasibility verdict, why the current lab is ready, how the two scenarios relate,
and a combined roadmap. Detailed build steps live in the companion plans it links to.

---

> **Status:** Phase **2A (network slicing) is BUILT and validated** on the DGX — two slices, two
> UPFs, isolation proven. See [`2A_slicing_run.md`](2A_slicing_run.md). Phase 2B (MEC) is next.

## Feasibility verdict

**Both are feasible, and both are additive** — the single-slice lab and the self-securing detector
keep working unchanged. Crucially, the two scenarios share one building block — **a second UPF
selected by DNN** — so building slicing first lays most of the groundwork for MEC.

## Why the lab is already ready for this

The Phase 1 lab (running end-to-end on the DGX Spark, ARM64, all-Docker) provides the enablers:

| Enabler (already built) | What it unlocks for Phase 2 |
|---|---|
| **NSSF** already running among the 12 NFs | slice selection — exercised for the first time in slicing |
| arm64 Open5GS image + **parameterized entrypoint** (`OGSTUN_ADDR` / `UE_SUBNET`) | spin up a second/edge UPF with its own subnet + NAT, no new image |
| Containerized **UERANSIM** harness (`run-containers.sh`) | add a second UE / slice-aware UE by extending templates |
| Detector captures from a **UPF's network namespace** (`nsenter`) | works per-UPF → per-slice / per-edge detection for free |
| Attack containers on the **core docker network** | aim the same attacks at any UPF (edge included) |
| `docker network` segmentation | model a less-trusted **edge segment** vs. the trusted core |

So Phase 2 is configuration and topology work on a proven base — not new core capability.

## Scenario 1 — Network slicing

**Goal:** run two slices with visibly separate user planes (e.g. eMBB `SST=1` and IoT `SST=2`),
each with its own UPF, DNN, and IP subnet, and prove traffic isolation between them.

**Adds:** a second S-NSSAI on the AMF, NSSF slice mapping, a second UPF (DNN `mec`/`iot`,
`10.46.0.0/16`), slice-aware subscriber data, and a second UE. **Detailed build:**
[`docs/2_slice_demo.md`](2_slice_demo.md).

**Security value:** slicing is a containment boundary — the setup that lets you later show an
attack in one slice leaving the other untouched.

## Scenario 2 — MEC security demo

**Goal:** model a distributed **edge (MEC) UPF at local breakout** sitting in a less-trusted
segment, stage the attacks its exposed location invites, and demonstrate layered mitigations —
with the central core staying clean.

**Adds:** an `open5gs-edge` docker network (the "mid-haul" boundary), an edge UPF + a `mec-app`,
an attacker foothold, and mitigations (N4 source ACL, ingress rate-limit, detector-at-edge, TLS).
Seven staged threats and L1–L7 mitigations are enumerated in
[`docs/MEC_edge_demo.md`](MEC_edge_demo.md).

**Security value:** demonstrates the edge as the "soft underbelly," then shows containment — the
strongest advisory story and a direct extension of the self-securing loop.

## How the two fit together

Both scenarios stand up a **second UPF keyed by DNN**. Slicing uses it for *isolation between two
peer slices*; MEC uses it as an *edge breakout UPF in a less-trusted segment*. That shared
plumbing is why the recommended order is **slicing first, then MEC**: slicing proves the
multi-UPF / multi-DNN / NSSF path, and MEC then specializes the second UPF into an edge node and
adds the attack/mitigation layer.

```
Phase 1 (done): core + RAN + detector + SRX, single slice
        │
        ▼
Phase 2A — Slicing : add 2nd UPF/DNN + NSSF + 2nd UE  →  prove isolation
        │  (reuses the second-UPF plumbing)
        ▼
Phase 2B — MEC     : edge UPF on a less-trusted segment + attacks + mitigations
```

## Combined roadmap

**Phase 2A — Network slicing**
1. Core config: 2nd S-NSSAI on AMF, NSSF mapping, 2nd UPF (DNN + subnet), SMF UPF-by-DNN.
2. Provision slice-aware subscriber(s).
3. Extend the UERANSIM harness for a second, slice-specific UE.
4. **Gate:** UE-A → slice 1 subnet via UPF-A; UE-B → slice 2 subnet via UPF-B; isolation shown
   (per-UPF `nsenter` tcpdump — traffic only on its own user plane).

**Phase 2B — MEC security**
1. Add `open5gs-edge` network + edge UPF (DNN `mec`) + `mec-app`; steer the DNN to the edge UPF.
2. Add the edge attacker; reproduce the N3/N4 + spoofed-PFCP threats; capture at the edge UPF.
3. Add mitigations: segmentation + N4 source ACL, ingress rate-limit (iptables stand-in for
   cSRX on ARM), detector-at-edge, TLS on `mec-app`.
4. **Gate:** attack the edge → show impact + detection → enable mitigations → attack contained,
   **core unaffected**.

## Effort & dependencies

| Item | Effort | Depends on |
|---|---|---|
| 2A core slicing config (AMF/NSSF/SMF + 2nd UPF) | Moderate | Phase 1 lab up |
| 2A slice subscriber + 2nd UE | Low–Moderate | 2A core config |
| 2B edge UPF + mec-app + segmentation | Moderate | 2A (second-UPF plumbing) |
| 2B attacks at edge | Low | existing attack containers |
| 2B mitigations (ACL, rate-limit, detector-at-edge, TLS) | Moderate | edge topology |

Rough sizing: **2A ≈ one focused session** (plus Open5GS slicing config iteration); **2B ≈ one to
two sessions** on top of 2A.

## Risks / open questions

- Open5GS specifics to confirm during build: **SMF UPF-selection-by-DNN** (vs. two SMFs), the
  **NSSF** config schema for multiple S-NSSAI, and **slice-aware subscriber provisioning** (the
  basic `open5gs-dbctl add` is single-slice — may need the slice sub-command or a direct insert).
- **UE NSSAI must match** the AMF's supported/allowed NSSAI exactly, or registration is rejected —
  the most common slicing bring-up failure.
- **cSRX is x86-only on ARM today**, so the MEC volumetric mitigation (L2) uses an `iptables`
  rate-limit as the ARM-native stand-in; **N4 IPsec** is represented by the source-ACL.
- **Traffic-influence / rogue-AF** (MEC threat) is limited in the Open5GS NEF → kept conceptual.

## Success criteria

- **Slicing:** two UEs attach to two slices, receive addresses from two different subnets via two
  different UPFs, and per-UPF capture shows each slice's traffic only on its own user plane.
- **MEC:** a UE reaches the edge app via local breakout; an attack on the edge UPF degrades the
  edge and lights up the (edge-scoped) detector while the central core is untouched; enabling the
  mitigation layer blocks/contains the attack (visible in iptables drops, rate-limit caps, detector
  scores).

## Coexistence & rollback

All new services and networks are additive; the base single-slice demo and the detector run
exactly as today. New config lives beside the current files, and the second UPF is an optional
compose service — so any Phase 2 piece can be brought up or torn down without disturbing Phase 1.

---

*Phase 2 of 5G Lab-in-a-Box · builds on the DGX Spark all-Docker lab · companion plans:
[`docs/2_slice_demo.md`](2_slice_demo.md), [`docs/MEC_edge_demo.md`](MEC_edge_demo.md).*
