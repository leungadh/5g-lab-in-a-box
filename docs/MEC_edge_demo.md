# MEC Edge-Breakout — Attack & Mitigation Demo Plan

A plan to extend the lab with a **distributed edge (MEC) UPF at local breakout**, then stage the
attacks that a MEC's exposed physical location invites — and demonstrate **layered mitigations**
against each. The story for peers: *the edge is the soft underbelly of a 5G network; here is what
that exposure looks like, and here is how you defend it.*

This is **additive** — the base single-slice demo and the two-slice plan (`docs/2_slice_demo.md`)
are unaffected, and it reuses the same "second UPF" mechanic.

---

## 1. Goal

Model a realistic MEC deployment — an **edge UPF + MEC app sitting at a less-trusted edge site**,
controlled from a central core over N4 — then (a) stage the MEC-specific attacks the location
enables and (b) show detection and mitigation in-lab, with the central core staying unaffected.

## 2. MEC in 5G — what we're modeling

The 5G control plane (AMF, SMF, PCF, NEF…) stays central and hardened. The **user plane is
distributed**: an operator places a **local/edge UPF** near the RAN so traffic for edge apps
**breaks out locally** (local N6 to the MEC host) instead of hauling back to a central UPF — that
is what buys the low latency. The edge UPF is still **controlled from the core over N4 (PFCP)**,
so the SMF sits in a data center while its N4 control link stretches across the **mid-haul** to a
box in a roadside cabinet or cell-site closet. MEC apps can also act as an **Application Function
(AF)** that influences routing via the **NEF/PCF** (`Nnef_TrafficInfluence`). The security problem:
the edge UPF and MEC host inherit the (low) trust of wherever they physically sit.

## 3. Target architecture (lab)

Two segments, so the trust boundary is explicit:

```
  ┌──────────── CORE segment (trusted, open5gs-core) ────────────┐
  │  AMF · SMF · NRF/SCP · UDM/UDR/AUSF/PCF/NSSF · Mongo          │
  │  upf-core  (DNN internet, 10.45.0.0/16)                      │
  └───────────────┬──────────────────────────────┬──────────────┘
             N2/N3 │                         N4 (PFCP) ← "mid-haul", crosses the boundary
  ┌───────────────┴──────── EDGE segment (less trusted, open5gs-edge) ┐
  │  upf-edge  (DNN mec, 10.47.0.0/16, local breakout)                │
  │  mec-app   (local N6 service)          [attacker foothold]        │
  └──────────────────────────────────────────────────────────────────┘
   UE on DNN "mec"  ──►  breaks out at upf-edge  ──►  mec-app  (low latency)
```

| Component | Segment | Role |
|---|---|---|
| `upf-core` | core (trusted) | central user plane — DNN `internet`, today's UPF |
| `upf-edge` | edge (less trusted) | **local-breakout UPF** — DNN `mec`, 10.47.0.0/16 |
| `mec-app` | edge | the edge application (HTTP/echo service) at local N6 |
| attacker | edge | models a foothold at the exposed edge site |
| SMF / AMF / NRF … | core | control plane, unchanged; SMF drives `upf-edge` over N4 |

## 4. Design decisions

- Put the edge on its **own docker network** (`open5gs-edge`) so the N3/N4 between the core-side
  SMF/gNB and `upf-edge` visibly **crosses the segment boundary** — that link is the mid-haul.
- Reuse the **arm64 Open5GS image + entrypoint** (`OGSTUN_ADDR`/`UE_SUBNET`) for `upf-edge`; it is
  the same second-UPF mechanic as `docs/2_slice_demo.md`, keyed to DNN `mec`.
- `mec-app` = a lightweight container (e.g. `nginx`/echo) reachable from the UE via local breakout.
- The **attacker foothold** = a container on `open5gs-edge` — i.e. "the attacker is already inside
  the edge site," which is the realistic MEC premise.
- Keep it additive and reversible.

## 5. Attack surface & risk staging

Each threat below is stageable with the lab's existing tooling (attack scripts hit N3 2152 / N4
8805; capture is `nsenter` inside the target UPF's netns).

| # | Threat | Where | How we stage it in the lab | Impact |
|---|---|---|---|---|
| 1 | **Edge N3 GTP-U flood** | N3 @ `upf-edge` | `gtpu_flood.py` from the edge attacker → `upf-edge:2152` | edge UPF resource exhaustion; MEC app DoS |
| 2 | **Edge N3 malformed GTP-U** | N3 @ `upf-edge` | `malformed_gtpu.py` → `upf-edge` | parser stress / user-plane instability |
| 3 | **Edge N4 PFCP session flood** | N4 @ `upf-edge` | `pfcp_session_flood.py` → `upf-edge:8805` | control-plane exhaustion at the edge |
| 4 | **Spoofed / rogue PFCP on the mid-haul** | N4 mid-haul | rogue container spoofs the SMF → `upf-edge` (assoc release / session delete) | session teardown, DoS, potential hijack |
| 5 | **Local-breakout N6 eavesdrop / modify** | N6 @ edge | a sniffer / compromised `mec-app` `tcpdump`s local-breakout traffic | user-data confidentiality & integrity loss |
| 6 | **Traffic-influence redirect (rogue AF)** | NEF/PCF → SMF | *(partial/conceptual)* simulate a steering-rule change redirecting a flow to the attacker | user-plane redirection |
| 7 | **Physical / tamper foothold** | edge site | modeled as "attacker present on `open5gs-edge`" — the premise for 1–5 | full local compromise |

## 6. Mitigations & how we demo them

Defence-in-depth: no single control is enough at the edge. Each layer below states what it stops
and how to *show* it working in the lab.

**L1 — Segmentation + N4 source ACL.** Keep edge and core on separate networks; on `upf-edge`, add
an `iptables` rule that accepts PFCP (8805) **only from the SMF's address** and GTP-U from expected
peers. *Stops:* threat 4 (spoofed PFCP), and unexpected-source floods. *Demo:* fire spoofed PFCP
from the rogue container → dropped (watch the `iptables` drop counters climb); legitimate SMF↔UPF
N4 unaffected.

**L2 — Volumetric rate-limiting at edge ingress.** A firewall screen / rate-limit on N3/N4 at the
edge. *Stops:* threats 1, 3 (floods). *Demo:* flood with and without the limit; show the cap.
*Note:* the cSRX firewall (`docs/FIREWALL.md`) is x86-only today, so on the ARM DGX use an
`iptables` `hashlimit`/`limit` rule on `upf-edge` as an ARM-native stand-in for the screen.

**L3 — Anomaly detection at the edge UPF.** Point the existing detector at `upf-edge` (capture via
`nsenter` there). *Stops (detects):* threats 1–4, including malformed/structural and behavioural
anomalies a rate-limit misses. *Demo:* capture at `upf-edge`, run `detector/baseline.py` — the
edge gets its **own** anomaly view, independent of the core.

**L4 — N4 integrity/confidentiality over the mid-haul.** Real deployments run **IPsec** on N4.
*Stops:* threat 4 (spoof/MITM). *Demo:* IPsec isn't wired into the lab, so we represent the control
with the **L1 source-ACL** (authenticate-by-source as a stand-in) and *describe* the IPsec upgrade —
honest about what is demonstrated vs. asserted.

**L5 — App/host hardening + N6 monitoring.** Isolate `mec-app`; run **TLS end-to-end** so local
breakout traffic is ciphertext. *Stops:* threat 5 (N6 eavesdrop/modify). *Demo:* sniff N6 with the
app on plain HTTP (readable) vs. HTTPS (ciphertext) — the sniffer sees nothing useful.

**L6 — AF authorization at the NEF.** Authenticate/authorize traffic-influence requests. *Stops:*
threat 6. *Conceptual* — Open5GS NEF traffic-influence is limited; described, not fully staged.

**L7 — Physical / platform.** Secure boot, disk encryption, remote attestation at the edge site.
*Stops:* threat 7. Out-of-band controls — noted, not lab-demoed.

**Threat → primary mitigation summary**

| Threat | Primary | Secondary |
|---|---|---|
| 1 Edge N3 flood | L2 rate-limit | L3 detection |
| 2 Edge malformed | L3 detection | L2 |
| 3 Edge PFCP flood | L2 rate-limit | L1 ACL, L3 |
| 4 Spoofed PFCP | L1 N4 ACL | L4 IPsec, L3 |
| 5 N6 eavesdrop | L5 TLS/isolation | segmentation |
| 6 Rogue AF redirect | L6 NEF authz | monitoring |
| 7 Physical foothold | L7 platform | L1 segmentation |

## 7. Build phases

1. **Edge topology** — add `open5gs-edge` network, `upf-edge` (DNN `mec`, 10.47.0.0/16), and
   `mec-app`; steer DNN `mec` → `upf-edge` in the SMF. Gate: a UE PDU session on `mec` reaches
   `mec-app` via local breakout, and `upf-edge` holds a stable PFCP association to the SMF.
2. **Attack** — add the edge attacker container; reproduce threats 1–4; capture at `upf-edge`.
3. **Mitigate** — add L1 segmentation + N4 source ACL, L2 rate-limit, L3 detector-at-edge, L5 TLS.
4. **Validate / demo** — attack → show impact → enable mitigation → attack blocked or detected,
   with the **core UPF unaffected** throughout.

## 8. Demo flow (for peers)

1. **Frame** — MEC = user plane pushed to the edge for latency; the edge site is less trusted.
2. **Edge works** — UE on DNN `mec` reaches `mec-app` locally (show the low-latency local breakout).
3. **Attack the edge** — from the edge foothold, flood / malform / spoof at `upf-edge`; show the
   impact (app degraded, detector lighting up) — while the **core stays clean**.
4. **Defend** — turn on the layers: N4 ACL drops the spoofed PFCP, the rate-limit caps the flood,
   the detector flags the malformed traffic, TLS blinds the N6 sniffer.
5. **Contrast** — the edge is contained; the central core never saw it. That is the MEC security story.

## 9. Detection / validation

- Capture at `upf-edge` (`nsenter`), extract features, run the detector → an **edge-scoped** anomaly
  view distinct from the core.
- Prove each mitigation concretely: `iptables` drop counters (L1), rate-limit caps (L2), detector
  scores (L3), plaintext-vs-ciphertext on N6 (L5).

## 10. Risks / specifics to confirm during build

- Open5GS **local-breakout / ULCL** or per-DNN PSA config to select `upf-edge` by DNN `mec`.
- **PFCP spoofing** feasibility: by default the edge UPF accepts unauthenticated PFCP from any
  reachable peer — which is exactly the exposure; the L1 ACL is the demonstrable countermeasure.
- **Traffic-influence (threat 6)** is limited in the Open5GS NEF — keep it conceptual.
- **cSRX is x86-only** on ARM today, so L2 uses `iptables` rate-limiting as the ARM stand-in.
- **IPsec on N4** is not natively wired — represented by the L1 source-ACL, with IPsec described.

## 11. Effort, scope, rollback

**Effort:** moderate-plus — one edge network, `upf-edge` + `mec-app` + attacker containers, plus
the mitigation layers. Realistically two focused sessions (topology first, then attack+mitigate).
**Rollback / coexistence:** all new services and the `open5gs-edge` network are additive; the base
and slicing demos run exactly as before. Slicing (`docs/2_slice_demo.md`) and this MEC plan share
the second-UPF plumbing, so building one accelerates the other.

---

*5G Lab-in-a-Box · MEC edge-breakout attack & mitigation · builds on the DGX Spark all-Docker lab.
Maps to ETSI MEC, 3GPP SBA, and GSMA edge-security guidance: edge trust boundary, N4 protection,
and local-breakout monitoring.*
