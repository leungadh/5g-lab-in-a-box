# Attack / test scripts (lab-only)

Red-team traffic generators for the N3 (GTP-U) and N4 (PFCP) interfaces of the local lab core. Each is a **labeled traffic source** for the capture pipeline: run one, capture the window, and you have a labeled sample of that attack class for Idea 2.

> **Guardrail.** Every script imports `_common.assert_lab_target()`, which refuses to send unless the destination is loopback or an RFC-1918 lab address **and** you pass `--i-own-this-lab`. This is deliberate friction. Do not remove it. See `../docs/THREAT-MODEL.md`.

## Dependencies
```bash
pip3 install --break-system-packages scapy
# some GTP/PFCP layers live in scapy.contrib; recent scapy includes them.
```

## Inventory

| Script | Interface | Class label | What it emits |
|---|---|---|---|
| `gtpu/malformed_gtpu.py` | N3 | `gtpu_malformed` | GTP-U packets with invalid message types, reserved bits set, bogus TEIDs, malformed extension headers |
| `gtpu/gtpu_flood.py` | N3 | `gtpu_flood` | High-rate G-PDU injection to a target TEID |
| `pfcp/pfcp_session_flood.py` | N4 | `pfcp_session_flood` | Rapid PFCP Session Establishment Requests |
| `pfcp/pfcp_association_abuse.py` | N4 | `pfcp_assoc_abuse` | Repeated/forged Association Setup + heartbeat manipulation |
| `signaling/registration_storm.sh` | N2 | `signaling_storm` | Many UE registrations via UERANSIM (attach churn) |

## Typical use
```bash
# capture a benign baseline first (no attack running)
make capture DURATION=120

# then capture an attack window
make attack ATTACK=gtpu/malformed_gtpu.py &   # or run directly with flags
make capture DURATION=120
```

The capture harness in `../capture/run_labeled_dataset.sh` automates benign + each attack in sequence and tags the windows.
