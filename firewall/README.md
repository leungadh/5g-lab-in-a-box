# firewall/ — cSRX flood-firewall testbed (Part 1, routed mode)

Stand up a **cSRX** as an L3 firewall between an attacker and a target and show it **rate-limits the flood attacks** the lab generates: `attacker → cSRX (routed) → target`. This is the *enforcement* half of the "firewall + AI" story — see [`../docs/FIREWALL.md`](../docs/FIREWALL.md) for the full design and the honest layer split.

> **cSRX has no GTP ALG.** It can rate-limit volumetric **floods** (via DoS screens) but cannot deep-inspect / drop **malformed** GTP-U — that needs vSRX/SRX. Malformed and protocol-abuse traffic is caught by the **ML detector** instead. Details in `../docs/FIREWALL.md`.

> **You supply the cSRX image + license** (Juniper, 60-day eval). See [`csrx_loading.md`](csrx_loading.md).

## Files

| File | Purpose |
|---|---|
| `csrx_loading.md` | Load the cSRX image (`docker load`) and apply the eval license |
| `setup.sh` | Networks + cSRX in **routing** mode + attacker/target, attacker routed to target via cSRX |
| `csrx.conf` | Junos config: L3 interfaces, zones, **UDP-flood screen**, permit policy (no GTP) |
| `run_demo.sh` | Fire valid / GTP-U flood / PFCP flood / malformed and count what the target receives |

## Steps

```bash
# 0. Load + name the image (see csrx_loading.md); export in THIS shell
export CSRX_IMAGE="csrx:26.2R1.7"

# 1. Stand up the testbed (fixed addressing: attacker 10.10.1.10, target 10.10.2.10, cSRX .2)
./firewall/setup.sh

# 2. Load the config into cSRX
grep -E '^set ' firewall/csrx.conf > /tmp/csrx.set
docker cp /tmp/csrx.set csrx:/tmp/csrx.set
docker exec -it csrx cli        # then: configure ; load set /tmp/csrx.set ; commit

# 3. Verify the interface mapping (ge-0/0/0 should be 10.10.1.2; swap in csrx.conf if reversed)
docker exec -it csrx cli -c "show interfaces terse" | grep ge-

# 4. Apply the eval license if not done (Junos CLI): request system license add terminal

# 5. Run the demo
./firewall/run_demo.sh
```

## What you should see

| Traffic | Expected at the target | Why |
|---|---|---|
| valid GTP-U (N3) | passes (~all received) | well-formed, permitted, under the rate threshold |
| GTP-U flood (N3) | capped far below what was sent | UDP-flood screen rate-limits it |
| PFCP session flood (N4) | capped far below what was sent | same UDP-flood screen (PFCP is UDP/8805) |
| malformed GTP-U (N3) | **passes through** | cSRX has no GTP inspection — **this is the ML detector's job** |

Confirm the *why* on the cSRX: `show security screen statistics zone untrust` (flood drops), `show security flow session summary`.

**Before/after for the floods:** raise the screen threshold above the attack rate (flood gets through), commit, run; then lower it and re-run to watch the rate-limit engage. That side-by-side is the demo money-shot.

## Teardown

```bash
docker rm -f csrx fw-attacker fw-target
docker network rm fw-mgmt fw-left fw-right
```

## Caveats

- cSRX config and Docker interface mapping are **version-specific** (`csrx:26.2R1.7` here) — validate against the Juniper docs.
- The screen is **volumetric** (rate-limit only), not protocol inspection.
- cSRX **secure-wire** mode can't attach zones/screens to its interfaces, which is why this uses **routed** mode.
