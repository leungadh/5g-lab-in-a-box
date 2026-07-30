#!/usr/bin/env bash
# Run UERANSIM gNB + UE as containers ON the Open5GS core docker network (all-Docker
# path, e.g. the DGX Spark). N2 (->amf) and N3 (->upf) use container addressing, so
# there's no host<->container GTP-U port conflict. Container TUN must work (uesimtun0).
#
#   deploy/ran/ueransim/run-containers.sh up     # build (if needed) + start gnb, ue
#   deploy/ran/ueransim/run-containers.sh down   # stop + remove gnb, ue
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
IMG="${UERANSIM_IMAGE:-ueransim:arm64}"
ACTION="${1:-up}"

down() {
  docker rm -f ue gnb 2>/dev/null || true
  echo "[ran] stopped."
}

up() {
  NET="${CORE_NET:-$(docker network ls --format '{{.Name}}' | grep -E '_core$' | head -1)}"
  [ -n "$NET" ] || { echo "core network not found — set CORE_NET=<name> (see: docker network ls)"; exit 1; }
  echo "[ran] image=$IMG  network=$NET"
  docker image inspect "$IMG" >/dev/null 2>&1 || { echo "[ran] building $IMG..."; docker build -t "$IMG" "$DIR"; }
  docker rm -f ue gnb 2>/dev/null || true

  echo "[ran] starting gNB..."
  docker run -d --name gnb --network "$NET" "$IMG" gnb
  sleep 4
  echo "[ran] starting UE..."
  docker run -d --name ue --network "$NET" --cap-add NET_ADMIN --device /dev/net/tun "$IMG" ue
  sleep 5

  echo "==== gNB log ===="; docker logs --tail 25 gnb || true
  echo "==== UE log ===="; docker logs --tail 25 ue || true
  echo "==== UE data interface ===="
  docker exec ue ip -brief addr show uesimtun0 2>/dev/null \
    || echo "(uesimtun0 not up yet — check the UE log above for PDU session status)"
}

case "$ACTION" in
  up) up ;;
  down) down ;;
  *) echo "usage: run-containers.sh [up|down]"; exit 1 ;;
esac
