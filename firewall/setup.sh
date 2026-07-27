#!/usr/bin/env bash
# Phase 1 cSRX GTP-firewall testbed:  attacker -> cSRX (secure-wire) -> target
#
# PREREQ: the cSRX image must be loaded locally and licensed (60-day eval).
#   docker load -i csrx.tar        # image you downloaded from Juniper
#   export CSRX_IMAGE=csrx:<tag>   # then run this script
#
# See firewall/README.md for the full flow (config load, demo, teardown).
set -euo pipefail
CSRX_IMAGE="${CSRX_IMAGE:-csrx:latest}"          # TODO: set to your loaded image
CSRX_PW="${CSRX_PW:-Juniper123}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "[fw] creating networks (mgmt + two data segments)..."
docker network create fw-mgmt  2>/dev/null || true
docker network create fw-left  2>/dev/null || true
docker network create fw-right 2>/dev/null || true
# NOTE: true L2 secure-wire expects both data segments in the SAME subnet so the
# attacker and target are L2-adjacent through the firewall. Docker won't allow two
# bridges with overlapping subnets, so follow Juniper's secure-wire-between-
# containers walkthrough (docs/FIREWALL.md sources) for the exact networking, or
# switch to CSRX_FORWARD_MODE="routing" and give each side its own subnet with the
# attacker routed to the target via the cSRX. Left as a deliberate TODO.

echo "[fw] launching cSRX in secure-wire mode..."
docker rm -f csrx 2>/dev/null || true
docker run -d --privileged --network=fw-mgmt \
  -e CSRX_FORWARD_MODE="wire" \
  -e CSRX_SIZE="large" \
  -e CSRX_ROOT_PASSWORD="$CSRX_PW" \
  --name csrx "$CSRX_IMAGE"
sleep 6
echo "[fw] attaching data interfaces (become ge-0/0/0 and ge-0/0/1)..."
docker network connect fw-left  csrx
docker network connect fw-right csrx

echo "[fw] launching target (records what gets through)..."
docker rm -f fw-target 2>/dev/null || true
docker run -d --name fw-target --network=fw-right nicolaka/netshoot sleep infinity

echo "[fw] launching attacker (runs the repo's attacks/)..."
docker rm -f fw-attacker 2>/dev/null || true
docker run -d --name fw-attacker --network=fw-left \
  -v "$REPO":/repo -w /repo python:3.11-slim sleep infinity

echo
echo "[fw] up. Next:"
echo "  1. Load the firewall config:  docker exec -it csrx cli   (then: configure; load set terminal < csrx.conf; commit)"
echo "  2. Target IP:  docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' fw-target"
echo "  3. Run the demo:  TARGET_IP=<that ip> ./firewall/run_demo.sh"
docker ps --filter "name=csrx" --filter "name=fw-" --format '  {{.Names}}\t{{.Status}}'
