#!/usr/bin/env bash
# Capture N3 (GTP-U) + N4 (PFCP) traffic on the Open5GS core bridge.
# Usage: capture.sh [DURATION_SECONDS] [LABEL]
set -euo pipefail
DURATION="${1:-120}"
LABEL="${2:-benign}"
OUTDIR="$(cd "$(dirname "$0")" && pwd)/pcaps"
mkdir -p "$OUTDIR"

# Find the docker bridge interface for the 'open5gs-core' network.
NETID="$(docker network inspect open5gs-core -f '{{.Id}}' 2>/dev/null | cut -c1-12 || true)"
IFACE="br-${NETID}"
if ! ip link show "$IFACE" >/dev/null 2>&1; then
  echo "[capture] bridge $IFACE not found; falling back to 'any'."
  IFACE="any"
fi

TS="$(date +%Y%m%d-%H%M%S)"
OUT="$OUTDIR/${LABEL}_${TS}.pcap"
echo "[capture] iface=$IFACE dur=${DURATION}s label=$LABEL -> $OUT"

# GTP-U 2152, PFCP 8805. Rotating not needed for short windows.
sudo timeout "$DURATION" tcpdump -i "$IFACE" -w "$OUT" \
  'udp port 2152 or udp port 8805' 2>/dev/null || true

echo "[capture] wrote $OUT"
echo "$OUT"
