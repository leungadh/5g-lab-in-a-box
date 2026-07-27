# Firewall Enhancement — Juniper cSRX on the N3 Threat Surface

Insert a **Juniper cSRX** (containerized SRX firewall) in-path and show it **blocks the GTP-U attacks** the lab generates — the enforcement half of the "firewall + AI" story: the cSRX does deterministic, signature-based enforcement, and the ML detector (`detector/`) covers what the firewall can't (novel patterns, PFCP abuse, signaling storms). Defense in depth.

This document covers **Phase 1**: a standalone GTP-firewall testbed (`attacker → cSRX → target`) that proves the capability without touching the fragile 5G core. Phase 2 (inline on the live N3) is sketched at the end.

> **Not yet runnable as-is.** The cSRX container image and license are **not** in this repo — they're downloaded from Juniper with an account (60-day free eval, SKU `S-cSRX Container Firewall-A1`). The scaffold in [`../firewall/`](../firewall/) is a template with clear placeholders; drop in the image and license and it runs. Junos config syntax should be **verified against your cSRX version** — see the citations.

## Why cSRX fits

- Runs as a **Docker container** on a Linux host — same host as the lab.
- **60-day free evaluation license** — build the demo with no purchase.
- Two relevant modes: **Layer-2 secure-wire** (transparently bridges two interfaces, inspecting between them — ideal for dropping in-path) and **routed** (L3 gateway, 3 interfaces default).
- Mature **GTP firewall**: Junos GTP-U inspection does packet sanity checks, stateful inspection, sequence-number validation, end-user address checks, GTP-in-GTP checks, and **drops invalid GTP-U packets** — precisely the malformed-GTP-U case.

## Attack → mitigation mapping (be honest about coverage)

| Attack (from `attacks/`) | Interface | cSRX mechanism | Expected result |
|---|---|---|---|
| `malformed_gtpu` | N3 (GTP-U) | GTP-U inspection: packet sanity, message-type & sequence checks | **Blocked** — strong, purpose-built |
| `gtpu_flood` | N3 (GTP-U) | Screens (UDP flood threshold) + GTP rate limiting | **Rate-limited / mitigated** |
| `pfcp_session_flood` | N4 (PFCP) | UDP flood screen (SRX PFCP deep-inspection is limited) | **Partial** — volume capped, not deep-validated |
| `pfcp_assoc_abuse` | N4 (PFCP) | UDP flood screen | **Partial** |
| `signaling_storm` | N2 (NGAP) | — (not on the N3/N4 path) | **Out of scope** for this placement |

The honest split is the selling point: **the firewall cleanly stops the N3 GTP-U attacks; the ML detector catches the rest.** That's the layered "AI-firewall" narrative.

## Phase 1 topology — standalone testbed

Secure-wire (L2 transparent) between two containers — the documented cSRX pattern:

```
 ┌───────────┐   left net    ┌──────────────────┐   right net   ┌───────────┐
 │  attacker │───────────────│  cSRX (secure-wire)│──────────────│  target   │
 │ (attacks/)│   ge-0/0/0     │  GTP-U inspection  │   ge-0/0/1    │ (tcpdump) │
 └───────────┘                │  + UDP screens     │               └───────────┘
                              └──────────────────┘
                                       │ mgmt (eth0)
                                   Junos CLI
```

- **attacker** runs the repo's `attacks/gtpu/*.py` against the target's IP.
- **cSRX** bridges the two segments, inspecting GTP-U in the middle.
- **target** just records what arrives (`tcpdump`), so we can compare *sent vs. delivered*.

The demo compares three traffic types crossing the firewall:

1. **valid GTP-U** (low-rate `gtpu_flood`) → should pass (target receives it),
2. **malformed GTP-U** (`malformed_gtpu`) → should be dropped (target receives ~none),
3. **GTP-U flood** (high-rate `gtpu_flood`) → should be rate-limited (target receives a capped rate),

and reads the cSRX GTP/screen drop counters to show *why*.

## cSRX launch essentials

Launched via `docker run` with environment variables (not plain compose — data interfaces are attached with `docker network connect` after launch, per Juniper's method):

```bash
docker run -d --privileged --network=mgmt \
  -e CSRX_FORWARD_MODE="wire" \
  -e CSRX_SIZE="large" \
  -e CSRX_ROOT_PASSWORD="<pw>" \
  --name csrx <csrx-image>
docker network connect left  csrx     # becomes ge-0/0/0
docker network connect right csrx     # becomes ge-0/0/1
```

`scripts/setup.sh` in the firewall module wraps this. Follow Juniper's "secure wire between two containers" guide for the exact networking, since cSRX's interface mapping is version-specific.

## Config approach (Junos)

The template [`../firewall/csrx.conf`](../firewall/csrx.conf) sets up: the secure-wire binding the two data interfaces, security zones, a **GTP inspection profile** applied via policy, and a **UDP-flood screen**. Enable, at minimum: packet sanity checking, sequence-number validation, GTP-U inspection, dropping of unknown/invalid message types, and traffic logging. **Verify the exact statements against your Junos version** using the GTP/SCTP guide.

## Phase 2 (later) — inline on the live N3

Once Phase 1 works, re-plumb the real N3 so traffic flows **gNB → cSRX → UPF**, then:
- run the attacks against the live core and show they're blocked before reaching the UPF, and
- run `capture/` + `detector/` on the **post-firewall** traffic to show what still gets through — quantifying the firewall+AI layering.

This is more involved on the current native-UPF (Path B) setup (N3 is on loopback today; it would need to move onto a bridged segment cSRX can sit in). Treat it as a follow-on.

## Caveats

- Config syntax and cSRX Docker networking are **version-specific** — validate against your image and the Juniper docs.
- SRX **PFCP** deep inspection is limited; N4 coverage here is volumetric (screens), not protocol-deep.
- The eval license expires after **60 days**.

## Sources

- [cSRX deployment guide (private/public cloud)](https://www.juniper.net/documentation/us/en/software/csrx/csrx-consolidated-deployment-guide/index.html)
- [cSRX on bare-metal Linux (Docker)](https://www.juniper.net/documentation/us/en/software/csrx/csrx-linux-deployment/topics/concept/security-csrx-docker-overview.html)
- [cSRX environment variables](https://www.juniper.net/documentation/us/en/software/csrx/csrx-consolidated-deployment-guide/csrx-linux-deployment/topics/concept/security-csrx-environment-variables.html)
- [cSRX secure-wire between two containers (walkthrough)](https://iosonounrouter.wordpress.com/2019/06/10/securing-traffic-between-two-containers-using-a-csrx-in-secure-wire-mode/)
- [Junos GTP-U inspection](https://www.juniper.net/documentation/en_US/junos12.1x47/topics/concept/security-gtp-u-inspection-understanding.html)
- [Junos OS: Securing GTP and SCTP Traffic (config reference)](https://www.juniper.net/documentation/us/en/software/junos/gtp-sctp/gtp-sctp.pdf)
