#!/usr/bin/env bash
# Part 1 cSRX flood-firewall testbed — ROUTED mode.
#
#   attacker 10.10.1.10 ──[ge-0/0/0 10.10.1.2] cSRX [ge-0/0/1 10.10.2.2]── target 10.10.2.10
#            (untrust / fw-left)                              (trust / fw-right)
#
# cSRX routes untrust->trust; a UDP-flood screen rate-limits the GTP-U / PFCP floods.
# (cSRX has no GTP ALG, so malformed GTP-U is NOT dropped here — that's the detector's job.)
#
# PREREQ: cSRX image loaded + licensed (see csrx_loading.md).  export CSRX_IMAGE=csrx:<tag>
set -euo pipefail
CSRX_IMAGE="${CSRX_IMAGE:-csrx:latest}"
CSRX_PW="${CSRX_PW:-Juniper123}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

echo "[fw] cleaning any prior testbed..."
docker rm -f csrx fw-attacker fw-target 2>/dev/null || true
docker network rm fw-mgmt fw-left fw-right 2>/dev/null || true

echo "[fw] networks (explicit subnets so we control addressing)..."
docker network create fw-mgmt >/dev/null
docker network create --subnet 10.10.1.0/24 fw-left  >/dev/null
docker network create --subnet 10.10.2.0/24 fw-right >/dev/null

echo "[fw] launching cSRX in ROUTED mode..."
docker run -d --privileged --network=fw-mgmt \
  -e CSRX_FORWARD_MODE="routing" \
  -e CSRX_SIZE="large" \
  -e CSRX_ROOT_PASSWORD="$CSRX_PW" \
  --name csrx "$CSRX_IMAGE" >/dev/null
sleep 6
# attach data interfaces with FIXED IPs. Order matters: first = ge-0/0/0.
docker network connect --ip 10.10.1.2 fw-left  csrx   # ge-0/0/0 (untrust)
docker network connect --ip 10.10.2.2 fw-right csrx   # ge-0/0/1 (trust)

echo "[fw] launching target (trust side, records what gets through)..."
docker run -d --name fw-target --network fw-right --ip 10.10.2.10 \
  nicolaka/netshoot sleep infinity >/dev/null

echo "[fw] launching attacker (untrust side, routes to target via cSRX)..."
docker run -d --name fw-attacker --network fw-left --ip 10.10.1.10 \
  --cap-add NET_ADMIN -v "$REPO":/repo -w /repo python:3.11-slim sleep infinity >/dev/null
docker exec fw-attacker sh -c "apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq iproute2 >/dev/null 2>&1" || true
docker exec fw-attacker ip route add 10.10.2.0/24 via 10.10.1.2

echo
echo "[fw] up. Next:"
echo "  1. Load config:  grep -E '^set ' firewall/csrx.conf > /tmp/csrx.set"
echo "                   docker cp /tmp/csrx.set csrx:/tmp/csrx.set"
echo "                   docker exec -it csrx cli  ->  configure; load set /tmp/csrx.set; commit"
echo "  2. Verify ports: docker exec -it csrx cli -c 'show interfaces terse' | grep ge-"
echo "                   (ge-0/0/0 should be 10.10.1.2; if swapped, swap addresses in csrx.conf)"
echo "  3. Demo:         ./firewall/run_demo.sh"
docker ps --filter "name=csrx" --filter "name=fw-" --format '  {{.Names}}\t{{.Status}}'
