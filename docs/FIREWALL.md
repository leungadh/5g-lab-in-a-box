# Firewall Enhancement — cSRX + the ML Detector (defense in depth)

Add a Juniper **cSRX** firewall to the lab so it **enforces** against the attacks the lab generates, alongside the **ML detector** that **detects** them. The two cover different things — and knowing which is which is the whole point.

> **Correction (important):** an earlier draft of this doc claimed cSRX could deep-inspect GTP. **It can't.** cSRX is a lightweight container firewall (stateful policy, DoS **screens**, IPS, AppSecure). The carrier-grade **GTP/SCTP ALG** — the thing that validates and drops malformed GTP-U — lives on **vSRX and physical SRX**, not cSRX. The scaffold and this doc have been corrected to match.

## What each layer actually does

| Attack (`attacks/`) | cSRX can… | Result on cSRX | Who really catches it |
|---|---|---|---|
| `gtpu_flood` (N3) | UDP-flood **screen** | **rate-limited** ✓ | **cSRX** (volumetric) |
| `pfcp_session_flood` (N4) | UDP-flood **screen** | **rate-limited** ✓ | **cSRX** (volumetric) |
| `malformed_gtpu` (N3) | — (no GTP ALG) | passes through | **ML detector** (or vSRX later) |
| `pfcp_assoc_abuse` (N4) | screen only if high-volume | partial | **ML detector** |
| `signaling_storm` (N2) | — (not on this path) | — | **ML detector** |

**The honest story:** cSRX caps the **volumetric floods**; the **ML detector** catches the **malformed and protocol-abuse** traffic the firewall can't inspect. Firewall enforces the obvious, AI catches the subtle. Full deep GTP inspection is a **vSRX** job (see below).

## Part 1 — standalone flood-firewall testbed (routed mode) ✅ built

Container-native, no hypervisor. cSRX as an L3 gateway between two Docker subnets:

```
 attacker 10.10.1.10 ──[ge-0/0/0 10.10.1.2] cSRX [ge-0/0/1 10.10.2.2]── target 10.10.2.10
        (untrust / fw-left)     routes + UDP-flood screen      (trust / fw-right)
```

Files in [`../firewall/`](../firewall/): `setup.sh` (networks, cSRX in **routing** mode, attacker routed to target via cSRX), `csrx.conf` (L3 interfaces, zones, UDP-flood screen, permit policy — **no GTP**), `run_demo.sh` (fires valid / GTP-U flood / PFCP flood / malformed and counts what reaches the target). Load steps in [`../firewall/README.md`](../firewall/README.md) and [`../firewall/csrx_loading.md`](../firewall/csrx_loading.md).

**Expected demo result:** valid passes; GTP-U flood and PFCP flood **rate-limited** by the screen; malformed GTP-U **passes** cSRX (proving it's the detector's job).

**Why routed, not secure-wire:** cSRX secure-wire (`wire` mode) is a transparent passthrough where you can't attach zones/screens to the interfaces (they're not configurable under `[interfaces]`). Routed mode gives cSRX real L3 interfaces where screens and policies apply — the reliable way to demo the flood rate-limiting.

## Part 2 — integrate cSRX into the live 5G lab (planned)

Once Part 1 works, put cSRX **inline on the real N3/N4** of the running core so it screens actual gNB↔UPF / SMF↔UPF traffic, then run `capture/` + `detector/` on the **post-firewall** traffic to quantify the layering (what the firewall stopped vs. what still needs the detector).

**Caveat up front:** the lab runs the UPF **natively on the host (Path B)** with N3 on loopback, so there's no clean L2/L3 segment to drop cSRX into. Integration will need re-plumbing N3/N4 onto Docker networks the cSRX can route between — non-trivial, which is exactly why Part 1 is standalone first. Detailed design is TBD in this section.

## If you want real GTP inspection later — vSRX (separate host)

To actually **drop malformed GTP-U** (deep GTP-U/GTP-C validation, message-type/sequence checks) you need **vSRX** or a physical SRX — they have the GTP ALG cSRX lacks. vSRX is a **full KVM/qemu VM**, so wedging it into this Docker lab means bridging container networks to VM taps and running a hypervisor next to Docker — heavy and fiddly on a host that's already fought us on kernel networking. **Recommendation:** keep vSRX as a *future, dedicated-host* effort (replay captured GTP through a standalone vSRX), not something to force into the container lab. For now, the ML detector covers the malformed case.

## Caveats

- cSRX config and Docker interface mapping are **version-specific** (image here is `csrx:26.2R1.7`) — validate against the Juniper docs.
- The UDP-flood screen is **volumetric** — it rate-limits by packet rate, it does not validate protocol contents.
- The interface→network mapping depends on Docker attach order; verify `ge-0/0/0 = 10.10.1.2` after `commit` and swap if needed.

## Sources

- [cSRX deployment guide](https://www.juniper.net/documentation/us/en/software/csrx/csrx-consolidated-deployment-guide/index.html)
- [cSRX on bare-metal Linux (Docker)](https://www.juniper.net/documentation/us/en/software/csrx/csrx-linux-deployment/topics/concept/security-csrx-docker-overview.html)
- [cSRX environment variables](https://www.juniper.net/documentation/us/en/software/csrx/csrx-consolidated-deployment-guide/csrx-linux-deployment/topics/concept/security-csrx-environment-variables.html)
- [SRX screens (DoS/flood protection)](https://www.juniper.net/documentation/us/en/software/junos/denial-of-service/index.html)
- [GTP inspection is vSRX/SRX (Securing GTP and SCTP)](https://www.juniper.net/documentation/us/en/software/junos/gtp-sctp/gtp-sctp.pdf)
