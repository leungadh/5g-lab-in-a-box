#!/usr/bin/env bash
# Fire representative N3/N4 traffic THROUGH the cSRX and count what the target receives.
# Run after setup.sh and after loading csrx.conf into the cSRX.
#
# Usage:  TARGET_IP=<fw-target ip> ./firewall/run_demo.sh
set -euo pipefail
TARGET_IP="${TARGET_IP:-}"
[ -n "$TARGET_IP" ] || { echo "set TARGET_IP=<fw-target ip>  (docker inspect fw-target)"; exit 1; }
ACK="--i-own-this-lab"
DUR=14

# tap <name> <udp-port>  : capture on the target for DUR seconds (background)
tap()   { docker exec fw-target sh -c "timeout $DUR tcpdump -ni any 'udp port $2' -w /tmp/$1.pcap 2>/dev/null"; }
count() { docker exec fw-target sh -c "tcpdump -nr /tmp/$1.pcap 2>/dev/null | wc -l"; }
fire()  { docker exec fw-attacker python3 "attacks/$1" --target "$TARGET_IP" $ACK "${@:2}"; }

echo "=== 1. VALID GTP-U  (N3, expect: PASSES) ==="
tap valid 2152 & sleep 1; fire gtpu/gtpu_flood.py --count 200 --rate 20 || true; wait
echo "    target received: $(count valid)  packets"

echo "=== 2. MALFORMED GTP-U  (N3, expect: BLOCKED, ~0) ==="
tap mal 2152 & sleep 1; fire gtpu/malformed_gtpu.py --count 200 --rate 20 || true; wait
echo "    target received: $(count mal)  packets   (GTP-U inspection drops these)"

echo "=== 3. GTP-U FLOOD  (N3, expect: RATE-LIMITED, capped << 5000) ==="
tap flood 2152 & sleep 1; fire gtpu/gtpu_flood.py --count 5000 --rate 500 || true; wait
echo "    target received: $(count flood)  packets   (UDP-flood screen caps this)"

echo "=== 4. PFCP SESSION FLOOD  (N4, expect: RATE-LIMITED, capped << 5000) ==="
tap pfcp 8805 & sleep 1; fire pfcp/pfcp_session_flood.py --count 5000 --rate 500 || true; wait
echo "    target received: $(count pfcp)  packets   (same UDP screen caps PFCP/8805)"

cat <<EOF

=== See WHY on the cSRX (drop evidence) ===
  docker exec -it csrx cli
  > show security gprs gtp counters                     # GTP-U inspection drops
  > show security screen statistics zone untrust        # UDP-flood drops (GTP-U + PFCP)
  > show security policies detail
  > show log messages | match "GTP|PFCP"                # traffic-logging

Interpretation:
  1 valid  -> ~full count            2 malformed -> ~0 (GTP inspection)
  3 flood  -> capped (UDP screen)    4 pfcp flood -> capped (UDP screen, port 8805)

Note: the PFCP defense is VOLUMETRIC (rate-limit only). SRX doesn't deep-inspect
PFCP, so low-rate PFCP abuse (assoc/heartbeat) slips past the firewall — that's
the ML detector's job. Firewall caps the floods; AI catches the subtle abuse.

"Before" comparison: raise the screen threshold above the attack rate (flood gets
through), then lower it to show the rate-limit engage.
EOF
