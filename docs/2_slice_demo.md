# Two-Slice Network Slicing — Demo Plan

A plan to extend the current single-slice lab into a **two-slice** deployment that visibly
separates user planes, so you can demo 5G network slicing to peers: two UEs, two slices, two
UPFs, two IP subnets — traffic physically isolated. It also sets up the security follow-on
(what happens to slice B when slice A is under attack).

This is an **additive** profile: the existing single-slice demo keeps working unchanged.

---

## 1. What we're demonstrating

5G identifies a slice by its **S-NSSAI** = SST (slice/service type) + SD (slice differentiator).
Slicing means one physical core serves multiple logical networks that are isolated from each
other. The convincing, visual proof of isolation is **separate user planes**: each slice gets
its own UPF, its own DNN, and its own UE IP subnet, so a UE on slice A literally cannot see
slice B's data path.

Today the lab runs a single slice (SST=1, no SD), so a UE is "slice-aware" but there's only one
slice to select — not a slicing demo. This plan adds a second, differentiated slice.

## 2. Target architecture

| Slice | S-NSSAI (SST / SD) | Profile | DNN | UE subnet | User plane |
|---|---|---|---|---|---|
| **A — eMBB** | 1 / 000001 | mobile broadband | `internet` | 10.45.0.0/16 | `upf-embb` (today's UPF) |
| **B — IoT/URLLC** | 2 / 000002 | IoT / low-latency | `iot` | 10.46.0.0/16 | `upf-iot` (new) |

Shared control plane (unchanged): NRF, SCP, AMF, **NSSF**, AUSF, UDM, UDR, PCF, BSF, MongoDB.
PLMN stays 999 / 70. The NSSF (already running) is the slice-selection function — this is the
first time we actually exercise it.

```
                         ┌──────── control plane (shared) ────────┐
   UE-A ─ gNB ─ N2 ─────►│  AMF · NSSF · SMF · NRF/SCP · UDM/UDR  │
   UE-B ─┘               └───────────────┬─────────────┬─────────┘
                                    N4 (PFCP)      N4 (PFCP)
                                         │             │
   slice A (internet, 10.45/16)  ◄─ N3 ─ upf-embb    upf-iot ─ N3 ─►  slice B (iot, 10.46/16)
```

## 3. Design decisions

- **Give each slice an explicit SD** (000001 / 000002) so the two are unambiguous end-to-end
  (the current lab uses SST=1 with no SD).
- **One SMF, two UPFs (recommended).** A single SMF advertises both S-NSSAI/DNN pairs and
  selects the UPF by DNN. Fewer moving parts than two SMFs, and it still yields two separate
  user planes — which is the whole point of the demo. *Alternative:* a dedicated SMF per slice
  for stronger control-plane isolation; note it if a peer asks, but it's not needed for the demo.
- **Reuse the arm64 image + entrypoint.** `deploy/open5gs/docker-entrypoint.sh` already
  parameterizes ogstun via `OGSTUN_ADDR` / `UE_SUBNET`, so `upf-iot` is the same image with
  `OGSTUN_ADDR=10.46.0.1/16` and `UE_SUBNET=10.46.0.0/16`.
- **Single NRF / NSSF, single NSI.** No multi-NRF network-slice-instance complexity — keep the
  demo readable.
- **Keep the base demo intact.** New config lives beside the current files; `upf-iot` is a new,
  optional compose service.

## 4. Components to add / change

**Core config**
- [ ] **AMF** — add the second S-NSSAI (1/000001 and 2/000002) to `plmn_support`; make both slices
      consistent across `plmn_support` / TAI / GUAMI.
- [ ] **NSSF** — register both S-NSSAI in the NSI/NRF mapping so slice selection resolves.
- [ ] **SMF** — advertise both S-NSSAI and both DNNs (`internet`, `iot`); define per-DNN session
      subnets (10.45.0.0/16, 10.46.0.0/16); add a second PFCP UPF peer and select UPF by DNN.
- [ ] **upf-iot** — new compose service from `open5gs:arm64`, on `open5gs-core`, with
      `OGSTUN_ADDR=10.46.0.1/16`, `UE_SUBNET=10.46.0.0/16`, N3/N4 published as needed.
- [ ] **Configs** — extract + run `scripts/dockerize_open5gs_configs.py` over the new/edited
      configs (service-name binding for the 2nd UPF's PFCP/GTP-U); extend it for the extra DNN/UPF.

**Subscribers**
- [ ] Provision subscriber(s) with **per-slice subscription data** — either one subscriber
      subscribed to both slices, or two subscribers (one per slice). Needs the slice-aware
      `open5gs-dbctl` path (or a direct Mongo document) since the basic `add` is single-slice.

**RAN**
- [ ] **gNB** — advertise both slices in its `slices:` list (sst1/sd000001, sst2/sd000002).
- [ ] **UE-A (`ue-embb`)** — `configured-nssai` sst1/sd000001; session `apn: internet`, slice sst1.
- [ ] **UE-B (`ue-iot`)** — `configured-nssai` sst2/sd000002; session `apn: iot`, slice sst2.
- [ ] Extend `deploy/ran/ueransim/run-containers.sh` + templates to launch a **second UE** with
      its own slice/DNN.

## 5. Build phases

1. **Core 2-slice config** — edit AMF / NSSF / SMF, add `upf-iot`, dockerize configs, bring up.
   Gate: both UPFs `Up`, both PFCP associations stable, SMF advertises both DNNs.
2. **Slice-aware subscriber provisioning** — add the slice subscription; verify in Mongo.
3. **RAN** — gNB with both slices; launch UE-A and UE-B.
4. **Verify isolation** — the proof (below).

## 6. Verifying isolation (the proof)

- **Addressing:** `docker exec ue-embb ip addr show uesimtun0` → 10.45.x; `ue-iot` → 10.46.x.
- **Per-UPF capture:** `nsenter` into each UPF netns and `tcpdump` — UE-A's GTP-U appears only on
  `upf-embb`, UE-B's only on `upf-iot`. No cross-slice user-plane traffic.
- **Independent egress:** both UEs reach the internet through their own UPF/NAT.

## 7. Demo flow (for peers)

1. **Frame** — what a slice is (S-NSSAI = SST+SD) and why isolation matters.
2. **Attach UE-A** → slice A → 10.45.x via `upf-embb`.
3. **Attach UE-B** → slice B → 10.46.x via `upf-iot`.
4. **Show isolation** — tcpdump each UPF; each slice's traffic lives only on its own user plane.
5. **Security tie-in** — flood slice A's UPF (the existing attack container, aimed at `upf-embb`);
   show slice B's user plane stays clean, and the detector run against each UPF gives a
   **per-slice** view of the anomaly.

## 8. Why this matters (security angle)

Slice isolation is a core 5G security property: a DoS or compromise in one slice must not bleed
into another. This extension lets you *demonstrate* isolation and then *stress* it — flood one
slice's N3 and show the other's user plane (and the GPU detector's per-UPF view) is unaffected.
That's a strong advisory story: slicing as a containment boundary, evidenced live.

## 9. Open5GS specifics to confirm during build (risk list)

- Exact **SMF** config for UPF-selection-by-DNN (vs. committing to two SMFs).
- **NSSF** config schema for multiple S-NSSAI in a single-NRF lab.
- **Subscriber** slice + DNN schema via `open5gs-dbctl` (the basic `add` is single-slice — may
  need the slice-aware sub-command or a direct Mongo insert).
- **UE `nssai` fields** must match the AMF's supported/allowed NSSAI exactly, or registration is
  rejected — the most common slicing bring-up failure.
- AMF consistency of the second S-NSSAI across `plmn_support` / `tai` / `guami`.

## 10. Effort, scope, rollback

**Effort:** moderate — one new container (`upf-iot`), config edits to AMF/NSSF/SMF, a second UE,
and slice-aware subscriber data. Realistically a focused session, plus iteration on the Open5GS
specifics in §9.

**Rollback / coexistence:** keep the two-slice config in its own service + config set so the
current single-slice demo runs exactly as today. Slicing is an add-on demo path, not a rewrite.

---

*5G Lab-in-a-Box · network slicing extension · builds on the DGX Spark all-Docker lab.*
