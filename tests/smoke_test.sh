#!/usr/bin/env bash
# End-to-end data-path check: the UE should reach the internet through the UPF.
set -euo pipefail

echo "[smoke] checking core containers..."
docker compose -f deploy/open5gs/docker-compose.yml ps || { echo "core not up? run 'make up'"; exit 1; }

echo "[smoke] looking for UE tun interface (uesimtun0)..."
if ip link show uesimtun0 >/dev/null 2>&1; then
  echo "[smoke] pinging 8.8.8.8 via uesimtun0..."
  ping -c 3 -I uesimtun0 8.8.8.8 && echo "[smoke] PASS: UE has data path." && exit 0
  echo "[smoke] FAIL: tun exists but no egress. Check UPF N6 NAT (scripts/bootstrap.sh)."
  exit 1
else
  echo "[smoke] FAIL: uesimtun0 not found. Is the UE up? run 'make ran-up' and check /tmp/ue.log"
  exit 1
fi
