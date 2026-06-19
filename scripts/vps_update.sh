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

VPS_IP="${VPS_IP:-62.169.27.133}"
VPS_USER="${VPS_USER:-root}"
SPIDERS="${*}"  # all CLI args become spider list, empty = all

echo "==> TogoLM VPS Update"
echo "    Host    : ${VPS_USER}@${VPS_IP}"
echo "    Spiders : ${SPIDERS:-all}"
echo ""

ssh "${VPS_USER}@${VPS_IP}" SPIDERS="${SPIDERS}" bash << 'REMOTE'
set -e

# ── Find the API container ────────────────────────────────────
API=$(docker ps --format '{{.Names}}' | grep -iE 'api' | grep -viE 'celery|beat' | head -1)
if [ -z "$API" ]; then
    echo "ERROR: No API container found. Running containers:"
    docker ps --format '{{.Names}}'
    exit 1
fi
echo "Container : $API"
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
