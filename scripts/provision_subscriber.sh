#!/usr/bin/env bash
# Add the test subscriber to the core's subscriber DB.
# Open5GS: uses the open5gs-dbctl helper against the mongo container.
set -euo pipefail
CORE="${1:-open5gs}"

# Load .env from repo root
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a; [ -f "$ROOT/.env" ] && . "$ROOT/.env"; set +a
: "${IMSI:?set IMSI in .env}"; : "${KI:?}"; : "${OPC:?}"; : "${APN:=internet}"

if [ "$CORE" = "open5gs" ]; then
  echo "[provision] adding IMSI=${IMSI} to Open5GS..."
  # open5gs-dbctl talks to the mongo container; fetch it if not present.
  if ! command -v open5gs-dbctl >/dev/null 2>&1; then
    curl -fsSL https://raw.githubusercontent.com/open5gs/open5gs/main/misc/db/open5gs-dbctl \
      -o /tmp/open5gs-dbctl && chmod +x /tmp/open5gs-dbctl
    DBCTL=/tmp/open5gs-dbctl
  else
    DBCTL=open5gs-dbctl
  fi
  export DB_URI="mongodb://127.0.0.1/open5gs"
  "$DBCTL" add "$IMSI" "$KI" "$OPC"
  echo "[provision] done. Verify in WebUI → http://localhost:${WEBUI_PORT:-9999}"
else
  echo "[provision] CORE=$CORE not implemented yet."
  echo "            free5GC: provision via its WebConsole or Mongo schema (see deploy/free5gc/README.md)."
  exit 1
fi
