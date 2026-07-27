#!/usr/bin/env bash
# Fire representative N3 traffic THROUGH the cSRX and count what the target receives.
# Run after setup.sh and after loading csrx.conf into the cSRX.
#
# Usage:  TARGET_IP=<fw-target ip> ./firewall/run_demo.sh
set -euo pipefail
TARGET_IP="${TARGET_IP:-}"
[ -n "$TARGET_IP" ] || { echo "set TARGET_IP=<fw-target ip>  (docker inspect fw-target)"; exit 1; }
ACK="--i-own-this-lab"
DUR=14

# capture on the target for DUR seconds (background), returns after DUR
tap() { docker exec fw-target sh -c "timeout $DUR tcpdump -ni any 'udp port 2152' -w /tmp/$1.pcap 2>/dev/null"; }
count() { docker exec fw-target sh -c "tcpdump -nr /tmp/$1.pcap 2>/dev/null | wc -l"; }
fire() { docker exec fw-attacker python3 "attacks/$1" --target "$TARGET_IP" $ACK "${@:2}"; }

echo "=== 1. VALID GTP-U  (expect: PASSES) ==="
tap valid & sleep 1; fire gtpu/gtpu_flood.py --count 200 --rate 20 || true; wait
echo "    target received: $(count valid)  packets"

echo "=== 2. MALFORMED GTP-U  (expect: BLOCKED, ~0) ==="
tap mal & sleep 1; fire gtpu/malformed_gtpu.py --count 200 --rate 20 || true; wait
echo "    target received: $(count mal)  packets   (GTP-U inspection should drop these)"

echo "=== 3. GTP-U FLOOD  (expect: RATE-LIMITED, capped well below 5000) ==="
tap flood & sleep 1; fire gtpu/gtpu_flood.py --count 5000 --rate 500 || true; wait
echo "    target received: $(count flood)  packets   (UDP-flood screen should cap this)"

cat <<EOF

=== See WHY on the cSRX (drop evidence) ===
  docker exec -it csrx cli
  > show security gprs gtp counters
  > show security screen statistics zone untrust
  > show security policies detail
  > show log messages | match GTP        (traffic-logging)

Interpretation: valid traffic count should be ~full; malformed ~0; flood capped.
For a "before" comparison, remove the GTP profile from the policy in csrx.conf
(permit plain GTP), commit, and re-run — the malformed traffic then gets through.
EOF
