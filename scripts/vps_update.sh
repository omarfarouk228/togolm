#!/usr/bin/env bash
# =============================================================
# TogoLM — Run corpus update on the VPS
#
# Connects via SSH, finds the API container, and runs the full
# scrape → ingest → embed pipeline remotely.
#
# Usage:
#   bash scripts/vps_update.sh                        # all spiders
#   bash scripts/vps_update.sh inseed                 # one spider
#   bash scripts/vps_update.sh inseed togofirst       # multiple
#   VPS_USER=togolm bash scripts/vps_update.sh        # custom user
# =============================================================
set -euo pipefail

VPS_IP="${VPS_IP:?Error: set VPS_IP before running (e.g. VPS_IP=x.x.x.x bash scripts/vps_update.sh)}"
VPS_USER="${VPS_USER:-root}"
APP_DIR="${APP_DIR:-/opt/togolm}"
SPIDERS="${*}"  # all CLI args become spider list, empty = all

echo "==> TogoLM VPS Update"
echo "    Host    : ${VPS_USER}@${VPS_IP}"
echo "    App dir : ${APP_DIR}"
echo "    Spiders : ${SPIDERS:-all}"
echo ""

ssh "${VPS_USER}@${VPS_IP}" APP_DIR="${APP_DIR}" SPIDERS="${SPIDERS}" bash << 'REMOTE'
set -e

# ── Find the API container via Docker Compose ─────────────────
API=$(cd "$APP_DIR" && docker compose -f docker-compose.prod.yml ps -q api 2>/dev/null | head -1)
if [ -z "$API" ]; then
    echo "ERROR: No 'api' service container found in $APP_DIR."
    echo "Running containers:"
    docker ps --format '{{.Names}}'
    exit 1
fi
echo "Container : $(docker inspect --format '{{.Name}}' "$API" | sed 's|^/||')"
echo ""

# ── Build spider arguments ────────────────────────────────────
if [ -n "$SPIDERS" ]; then
    SPIDER_ARGS="--spiders $SPIDERS"
else
    SPIDER_ARGS=""
fi

# ── Run the pipeline ──────────────────────────────────────────
echo "==> Starting pipeline (scrape + ingest + embed)..."
docker exec "$API" python scripts/run_scrapers.py $SPIDER_ARGS

echo ""
echo "Corpus update complete."
REMOTE
