#!/usr/bin/env bash
# =============================================================
# TogoLM — Push corpus to HuggingFace from the VPS
#
# Runs push_dataset.py inside the API container on the server.
#
# Usage:
#   HF_TOKEN=hf_xxx VPS_IP=x.x.x.x bash scripts/vps_push_dataset.sh
#   HF_TOKEN=hf_xxx VPS_IP=x.x.x.x bash scripts/vps_push_dataset.sh --private
# =============================================================
set -euo pipefail

VPS_IP="${VPS_IP:?Error: set VPS_IP before running (e.g. VPS_IP=x.x.x.x bash scripts/vps_push_dataset.sh)}"
VPS_USER="${VPS_USER:-root}"
APP_DIR="${APP_DIR:-/opt/togolm}"
HF_TOKEN="${HF_TOKEN:?Error: set HF_TOKEN before running (e.g. HF_TOKEN=hf_xxx ...)}"
EXTRA_ARGS="${*:-}"

echo "==> TogoLM — Push Dataset to HuggingFace"
echo "    Host : ${VPS_USER}@${VPS_IP}"
echo ""

ssh "${VPS_USER}@${VPS_IP}" APP_DIR="${APP_DIR}" HF_TOKEN="${HF_TOKEN}" EXTRA_ARGS="${EXTRA_ARGS}" bash << 'REMOTE'
set -e

API=$(cd "$APP_DIR" && docker compose -f docker-compose.prod.yml ps -q api 2>/dev/null | head -1)
if [ -z "$API" ]; then
    API=$(docker ps --format '{{.Names}}' | grep -E '^api-' | grep -vE 'celery|beat|worker' | head -1)
fi
if [ -z "$API" ]; then
    echo "ERROR: No API container found."
    exit 1
fi
echo "Container : $API"
echo ""

docker exec -e HF_TOKEN="$HF_TOKEN" "$API" python scripts/push_dataset.py $EXTRA_ARGS
REMOTE
