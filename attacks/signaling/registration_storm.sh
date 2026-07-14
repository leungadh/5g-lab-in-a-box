#!/usr/bin/env bash
# N2 signaling storm (label: signaling_storm).
# Repeatedly registers/deregisters UEs via UERANSIM to create registration/auth
# churn against the AMF. Uses nr-cli against a running UE, or restarts UEs.
#
# Lab-only: only run against your own lab AMF.
set -euo pipefail
COUNT="${1:-50}"
DELAY="${2:-0.2}"
UE_CONF="$(cd "$(dirname "$0")/../../deploy/ran/ueransim" && pwd)/ue.yaml"

command -v nr-ue >/dev/null 2>&1 || { echo "nr-ue not on PATH (install UERANSIM)"; exit 1; }

echo "[signaling_storm] $COUNT registration cycles, delay ${DELAY}s"
for i in $(seq 1 "$COUNT"); do
  # Bring a UE up briefly then kill it -> INITIAL REGISTRATION each time.
  sudo timeout 2 nr-ue -c "$UE_CONF" >/dev/null 2>&1 || true
  sleep "$DELAY"
  printf '\r[signaling_storm] cycle %d/%d' "$i" "$COUNT"
done
echo -e "\n[signaling_storm] done."
