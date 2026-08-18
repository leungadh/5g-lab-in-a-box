#!/usr/bin/env bash
# Run UERANSIM gNB + UE(s) as containers ON the Open5GS core docker network (all-Docker
# path, e.g. the DGX Spark). N2 (->amf) and N3 (->upf) use container addressing, so
# there's no host<->container GTP-U port conflict. Container TUN must work (uesimtun0).
#
# Phase 2A: two UEs on two slices —
#   ue     : SUPI ...001, DNN internet, SST 1  -> upf     (10.45.0.0/16)
#   ue-iot : SUPI ...002, DNN iot,      SST 2  -> upf-iot (10.46.0.0/16)
#
#   run-containers.sh up     # build (if needed) + start gnb, ue, ue-iot
#   run-containers.sh down   # stop + remove them
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
IMG="${UERANSIM_IMAGE:-ueransim:arm64}"
ACTION="${1:-up}"

down() {
  docker rm -f ue ue-iot gnb 2>/dev/null || true
  echo "[ran] stopped."
}

up() {
  NET="${CORE_NET:-$(docker network ls --format '{{.Name}}' | grep -E '[-_]core$' | head -1)}"
  [ -n "$NET" ] || { echo "core network not found — set CORE_NET=<name> (see: docker network ls)"; exit 1; }
  echo "[ran] image=$IMG  network=$NET"
  docker image inspect "$IMG" >/dev/null 2>&1 || { echo "[ran] building $IMG..."; docker build -t "$IMG" "$DIR"; }
  docker rm -f ue ue-iot gnb 2>/dev/null || true

  echo "[ran] starting gNB (advertises SST 1 + 2)..."
  docker run -d --name gnb --network "$NET" "$IMG" gnb
  sleep 4

  echo "[ran] starting UE-A (slice 1 / internet)..."
  docker run -d --name ue --network "$NET" --cap-add NET_ADMIN --device /dev/net/tun "$IMG" ue

  echo "[ran] starting UE-B (slice 2 / iot)..."
  docker run -d --name ue-iot --network "$NET" --cap-add NET_ADMIN --device /dev/net/tun \
    -e UE_SUPI=999700000000002 -e UE_APN=iot -e UE_SST=2 "$IMG" ue
  sleep 6

  echo "==== UE-A (slice 1) uesimtun0 — expect 10.45.x ===="
  docker exec ue     ip -brief addr show uesimtun0 2>/dev/null || echo "(ue: no uesimtun0 yet — docker logs ue)"
  echo "==== UE-B (slice 2 / iot) uesimtun0 — expect 10.46.x ===="
  docker exec ue-iot ip -brief addr show uesimtun0 2>/dev/null || echo "(ue-iot: no uesimtun0 yet — docker logs ue-iot)"
}

case "$ACTION" in
  up) up ;;
  down) down ;;
  *) echo "usage: run-containers.sh [up|down]"; exit 1 ;;
esac
