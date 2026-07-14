#!/usr/bin/env bash
# Build a labeled dataset: capture a benign baseline, then each attack class in
# turn, tagging every capture window by the attack that was running. Output is a
# folder of labeled pcaps ready for extract_features.py.
#
# Assumes the core + RAN are up and a UE is passing benign traffic.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
WIN="${WINDOW:-60}"          # seconds per class
ACK="--i-own-this-lab"
T=127.0.0.1

cap() { "$HERE/capture.sh" "$WIN" "$1" & CAP_PID=$!; }
wait_cap() { wait "$CAP_PID" 2>/dev/null || true; }

echo "== benign baseline =="
cap benign; wait_cap

echo "== gtpu_malformed =="
cap gtpu_malformed; python3 "$ROOT/attacks/gtpu/malformed_gtpu.py" --target $T $ACK --count 3000 --rate 50; wait_cap

echo "== gtpu_flood =="
cap gtpu_flood; python3 "$ROOT/attacks/gtpu/gtpu_flood.py" --target $T $ACK --count 5000 --rate 200; wait_cap

echo "== pfcp_session_flood =="
cap pfcp_session_flood; python3 "$ROOT/attacks/pfcp/pfcp_session_flood.py" --target $T $ACK --count 3000 --rate 100; wait_cap

echo "== pfcp_assoc_abuse =="
cap pfcp_assoc_abuse; python3 "$ROOT/attacks/pfcp/pfcp_association_abuse.py" --target $T $ACK --count 3000 --rate 100 --mode churn; wait_cap

echo "== done. Extract features: =="
echo "  python3 $HERE/extract_features.py $HERE/pcaps/*.pcap -o $HERE/data/features.parquet --window 1.0"
