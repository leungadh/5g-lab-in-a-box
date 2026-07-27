#!/usr/bin/env bash
# Capture N3 (GTP-U) + N4 (PFCP) traffic for the detector.
# Usage: capture.sh [DURATION_SECONDS] [LABEL]
#
# Default interface is 'any' so it works for BOTH layouts:
#   - all-Docker: traffic is on the open5gs-core bridge
#   - native UPF (Path B): N3 rides loopback (gNB 127.0.0.1 <-> UPF 127.0.0.7),
#     the attacks hit 127.0.0.1, and N4/PFCP crosses to the host IP
# Override with CAPTURE_IFACE=<iface> for a specific interface.
set -euo pipefail
DURATION="${1:-120}"
LABEL="${2:-benign}"
IFACE="${CAPTURE_IFACE:-any}"
OUTDIR="$(cd "$(dirname "$0")" && pwd)/pcaps"
mkdir -p "$OUTDIR"

TS="$(date +%Y%m%d-%H%M%S)"
OUT="$OUTDIR/${LABEL}_${TS}.pcap"
echo "[capture] iface=$IFACE dur=${DURATION}s label=$LABEL -> $OUT"

# GTP-U 2152, PFCP 8805.
sudo timeout "$DURATION" tcpdump -i "$IFACE" -w "$OUT" \
  'udp port 2152 or udp port 8805' 2>/dev/null || true

echo "[capture] wrote $OUT"
echo "$OUT"
