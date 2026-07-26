#!/usr/bin/env bash
# Seed (or reset) the Open5GS WebUI admin account.
#
# The WebUI only auto-creates admin/1423 if it can write to Mongo AND the
# accounts collection is empty at startup. On a compose cold start the webui
# often boots before Mongo is ready, silently skips seeding, and login then
# fails with "wrong password". This script inserts a correct account directly.
#
# Usage: ./scripts/create_webui_admin.sh [core] [username] [password]
#        core defaults to open5gs; credentials default to admin / 1423.
set -euo pipefail

CORE="${1:-open5gs}"
USER="${2:-admin}"
PASS="${3:-1423}"
COMPOSE="docker compose -f deploy/${CORE}/docker-compose.yml"

command -v python3 >/dev/null 2>&1 || { echo "python3 required to compute the password hash"; exit 1; }

# passport-local-mongoose defaults used by the Open5GS WebUI:
#   digest=sha256, iterations=25000, keylen=512, salt=32-byte hex string (used as-is)
read -r SALT HASH < <(python3 - "$PASS" <<'PY'
import hashlib, os, sys
pw = sys.argv[1].encode()
salt = os.urandom(32).hex()
h = hashlib.pbkdf2_hmac('sha256', pw, salt.encode(), 25000, dklen=512).hex()
print(salt, h)
PY
)

echo "[webui-admin] upserting account '${USER}' into MongoDB..."
$COMPOSE exec -T mongo mongosh open5gs --quiet --eval \
  "db.accounts.updateOne({username:'${USER}'},{\$set:{username:'${USER}',salt:'${SALT}',hash:'${HASH}',roles:['admin'],__v:0}},{upsert:true})"

COUNT=$($COMPOSE exec -T mongo mongosh open5gs --quiet --eval 'db.accounts.countDocuments({})' | tr -d '\r')
echo "[webui-admin] done. accounts in DB: ${COUNT}. Log in at http://localhost:9999 with ${USER} / ${PASS}"
