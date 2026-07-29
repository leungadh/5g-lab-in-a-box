#!/usr/bin/env bash
# Part 1 demo (routed mode): send traffic through the cSRX, count what the target gets.
# Shows the UDP-flood screen rate-limiting the GTP-U and PFCP floods.
# Run after setup.sh and after loading csrx.conf into the cSRX.
#
# Usage:  ./firewall/run_demo.sh          (target defaults to 10.10.2.10 from setup.sh)
set -euo pipefail
TARGET_IP="${TARGET_IP:-10.10.2.10}"
ACK="--i-own-this-lab"
DUR=16

tap()   { docker exec fw-target sh -c "timeout $DUR tcpdump -ni any 'udp port $2' -w /tmp/$1.pcap 2>/dev/null"; }
count() { docker exec fw-target sh -c "tcpdump -nr /tmp/$1.pcap 2>/dev/null | wc -l"; }
fire()  { docker exec fw-attacker python3 "attacks/$1" --target "$TARGET_IP" $ACK "${@:2}"; }

echo "=== 1. VALID GTP-U, low rate  (baseline — expect: PASSES) ==="
tap valid 2152 & sleep 1; fire gtpu/gtpu_flood.py --count 200 --rate 20 || true; wait
echo "    sent ~200, target received: $(count valid)"

echo "=== 2. GTP-U FLOOD  (N3 — expect: RATE-LIMITED by UDP screen) ==="
tap flood 2152 & sleep 1; fire gtpu/gtpu_flood.py --count 20000 --rate 2000 || true; wait
echo "    sent ~20000, target received: $(count flood)   (capped near screen threshold)"

echo "=== 3. PFCP SESSION FLOOD  (N4 — expect: RATE-LIMITED by same UDP screen) ==="
tap pfcp 8805 & sleep 1; fire pfcp/pfcp_session_flood.py --count 20000 --rate 2000 || true; wait
echo "    sent ~20000, target received: $(count pfcp)   (capped)"

echo "=== 4. MALFORMED GTP-U  (expect: PASSES cSRX — no GTP inspection) ==="
tap mal 2152 & sleep 1; fire gtpu/malformed_gtpu.py --count 200 --rate 20 || true; wait
echo "    sent ~200, target received: $(count mal)   (cSRX doesn't inspect GTP — this is the DETECTOR's job)"

cat <<EOF

=== See WHY on the cSRX ===
  docker exec -it csrx cli
  > show security screen statistics zone untrust     # UDP-flood drop counters
  > show security flow session summary
  > show security policies detail

Reading it:
  1 valid   -> ~full (passes)          2 gtpu flood -> capped (screen)
  3 pfcp flood -> capped (screen)      4 malformed  -> passes (firewall can't inspect; detector catches it)

The story: cSRX caps the volumetric FLOODS; the ML detector (../detector/) catches the
malformed / protocol-abuse traffic the firewall can't see. Firewall + AI, layered.

Tune: the UDP-flood screen threshold (csrx.conf) must be BELOW the attack rate to engage.
EOF
