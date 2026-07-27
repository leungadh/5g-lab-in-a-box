# firewall/ — Juniper cSRX GTP-firewall testbed (Phase 1)

Drop a **cSRX** in-path and show it blocks the lab's GTP-U attacks: `attacker → cSRX (secure-wire) → target`. This is the enforcement half of the "firewall + AI" story — see [`../docs/FIREWALL.md`](../docs/FIREWALL.md) for the full design, the attack→mitigation mapping, and honest coverage notes.

> **You supply the cSRX image + license.** They're not in this repo — download from Juniper (60-day free eval, SKU `S-cSRX Container Firewall-A1`). Everything else here is a runnable scaffold with clear placeholders.

## Files

| File | Purpose |
|---|---|
| `setup.sh` | Create networks, launch cSRX (secure-wire), attach interfaces, start attacker + target |
| `csrx.conf` | Junos config template: secure-wire + GTP inspection profile + UDP-flood screen |
| `run_demo.sh` | Fire valid / malformed / flood GTP-U through the firewall and count what the target receives |

## Steps

```bash
# 0. Load the cSRX image you downloaded from Juniper, and point the scripts at it
docker load -i csrx.tar
export CSRX_IMAGE=csrx:<tag>

# 1. Stand up the testbed
./firewall/setup.sh

# 2. Load the firewall config into the running cSRX
docker exec -it csrx cli
#   configure
#   load set terminal        (paste the contents of csrx.conf, then Ctrl-D)
#   commit and-quit

# 3. Find the target's IP, then run the demo
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' fw-target
TARGET_IP=<that ip> ./firewall/run_demo.sh
```

## What you should see

| Traffic | Expected at the target | Why |
|---|---|---|
| valid GTP-U (N3) | passes (~all received) | well-formed, permitted |
| malformed GTP-U (N3) | ~0 received | GTP-U inspection drops invalid message types / headers |
| GTP-U flood (N3) | capped far below what was sent | UDP-flood screen rate-limits it |
| PFCP session flood (N4) | capped far below what was sent | same UDP-flood screen (PFCP is UDP/8805) — **volumetric** defense only |

> PFCP defense is rate-limiting only — SRX doesn't deep-inspect PFCP. Low-rate PFCP abuse (association/heartbeat) slips past the firewall and is caught by the ML detector instead.

Confirm the *why* on the cSRX: `show security gprs gtp counters`, `show security screen statistics zone untrust`.

**Before/after:** to show the contrast, first commit `csrx.conf` with the GTP profile removed from the policy (plain permit) — malformed traffic gets through — then add it back and watch it get blocked. That side-by-side is the demo money-shot.

## Teardown

```bash
docker rm -f csrx fw-attacker fw-target
docker network rm fw-mgmt fw-left fw-right
```

## Caveats

- cSRX Docker networking and Junos syntax are **version-specific** — validate against your image and the Juniper docs cited in `../docs/FIREWALL.md`.
- True L2 secure-wire wants both data segments in one subnet; Docker disallows overlapping bridge subnets, so follow Juniper's secure-wire-between-containers walkthrough, or use `CSRX_FORWARD_MODE="routing"` with the attacker routed to the target through the cSRX. `setup.sh` flags this.
- PFCP (N4) deep inspection on SRX is limited — this testbed focuses on the strong case, N3 GTP-U. The ML detector (`../detector/`) covers what the firewall can't.
