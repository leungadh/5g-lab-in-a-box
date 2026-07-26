#!/usr/bin/env bash
# Start/stop UERANSIM gNB + UE using the configs in deploy/ran/ueransim.
# Assumes UERANSIM binaries (nr-gnb, nr-ue) are on PATH, or run via its docker image.
set -euo pipefail
ACTION="${1:-up}"
RANDIR="$(cd "$(dirname "$0")/../deploy/ran/ueransim" && pwd)"

start() {
  # Kill any stale gNB/UE from earlier runs — otherwise leftover processes hold
  # the RLS (4997) and GTP-U (2152) ports and the new gNB fails to bind them.
  echo "[ran] clearing any stale UERANSIM processes..."
  sudo pkill -9 -f nr-gnb 2>/dev/null || true
  sudo pkill -9 -f nr-ue  2>/dev/null || true
  sleep 1

  echo "[ran] starting gNB..."
  nr-gnb -c "$RANDIR/gnb.yaml" >/tmp/gnb.log 2>&1 &
  echo $! > /tmp/gnb.pid
  sleep 3
  echo "[ran] starting UE (needs sudo for tun device)..."
  sudo nr-ue -c "$RANDIR/ue.yaml" >/tmp/ue.log 2>&1 &
  echo $! > /tmp/ue.pid
  sleep 3
  echo "[ran] gNB log: /tmp/gnb.log   UE log: /tmp/ue.log"
  echo "[ran] look for a uesimtun0 interface with an IP in the UE subnet."
}

stop() {
  for p in /tmp/ue.pid /tmp/gnb.pid; do
    [ -f "$p" ] && sudo kill "$(cat "$p")" 2>/dev/null || true
    rm -f "$p"
  done
  # belt-and-suspenders: clear any strays not tracked by pid files
  sudo pkill -9 -f nr-gnb 2>/dev/null || true
  sudo pkill -9 -f nr-ue  2>/dev/null || true
  echo "[ran] stopped."
}

case "$ACTION" in
  up) start ;;
  down) stop ;;
  *) echo "usage: ran.sh [up|down]"; exit 1 ;;
esac
