#!/usr/bin/env bash
# Labeled-dataset capture for the ALL-DOCKER layout (e.g. DGX Spark).
#
# Captures N3 (GTP-U) + N4 (PFCP) from INSIDE the UPF network namespace (via nsenter,
# using the host's tcpdump) — the authoritative UPF-side view — while:
#   - generating a benign baseline from real UE traffic (ping over uesimtun0), then
#   - firing each attack class from a throwaway container at the UPF container.
# Each window is labeled by filename (<label>_<ts>.pcap) so extract_features.py builds
# a labeled dataset directly.
#
# Prereqs: core + RAN up, UE attached with working egress (ping 8.8.8.8 from the ue).
# Run:  sudo -v   # cache sudo once, avoids mid-run password prompts
#       capture/run_labeled_dataset_docker.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
NET="${CORE_NET:-open5gs-core}"
WIN="${WINDOW:-45}"                 # seconds per attack class (attack is sized to fill it)
BENIGN_WIN="${BENIGN_WINDOW:-120}"  # seconds of benign baseline
ACK="--i-own-this-lab"
PCAPS="$HERE/pcaps"; mkdir -p "$PCAPS"

# Resolve the UPF: pid (for nsenter) + IP (attack target).
UPF_CID="$(docker ps --filter name=upf --format '{{.ID}}' | head -1)"
[ -n "$UPF_CID" ] || { echo "UPF container not found (is the core up?)"; exit 1; }
UPF_PID="$(docker inspect -f '{{.State.Pid}}' "$UPF_CID")"
UPF_IP="$(docker run --rm --network "$NET" python:3.11-slim getent hosts upf | awk '{print $1}')"
[ -n "$UPF_IP" ] || { echo "could not resolve upf on network $NET"; exit 1; }
echo "[dataset] UPF pid=$UPF_PID ip=$UPF_IP net=$NET  attack-win=${WIN}s benign=${BENIGN_WIN}s"

cap() {  # cap <label> <seconds>  -> sets CAP_PID
  local label="$1" secs="$2" ts out
  ts="$(date +%Y%m%d-%H%M%S)"; out="$PCAPS/${label}_${ts}.pcap"
  echo "[dataset] capture $label for ${secs}s -> $(basename "$out")"
  sudo timeout "$secs" nsenter -t "$UPF_PID" -n tcpdump -Z root -i any -w "$out" \
    'udp port 2152 or udp port 8805' 2>/dev/null &
  CAP_PID=$!
  sleep 1   # let tcpdump come up before traffic starts
}
wait_cap() { wait "$CAP_PID" 2>/dev/null || true; }

atk() {  # atk <script-under-attacks/> [args...]
  docker run --rm --network "$NET" -v "$ROOT/attacks":/attacks:ro python:3.11-slim \
    python "/attacks/$1" --target "$UPF_IP" $ACK "${@:2}"
}

echo "== benign baseline (real UE traffic over uesimtun0) =="
cap benign "$BENIGN_WIN"
docker exec ue sh -c "timeout $BENIGN_WIN ping -i 0.2 -I uesimtun0 8.8.8.8 >/dev/null 2>&1" || true
wait_cap

echo "== gtpu_malformed =="
cap gtpu_malformed "$WIN"; atk gtpu/malformed_gtpu.py --rate 50 --count $((50*WIN)); wait_cap

echo "== gtpu_flood =="
cap gtpu_flood "$WIN"; atk gtpu/gtpu_flood.py --rate 200 --count $((200*WIN)); wait_cap

echo "== pfcp_session_flood =="
cap pfcp_session_flood "$WIN"; atk pfcp/pfcp_session_flood.py --rate 100 --count $((100*WIN)); wait_cap

echo "== pfcp_assoc_abuse =="
cap pfcp_assoc_abuse "$WIN"; atk pfcp/pfcp_association_abuse.py --rate 100 --count $((100*WIN)) --mode churn; wait_cap

echo "== done. Captured pcaps: =="
ls -1 "$PCAPS"/*.pcap
echo "== extract features: =="
echo "  python3 $HERE/extract_features.py $PCAPS/*.pcap -o $HERE/data/features.parquet --window 1.0"
