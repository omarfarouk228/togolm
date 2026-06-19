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
SPIDERS="${*:-}"  # all CLI args become spider list, empty = all

echo "==> TogoLM VPS Update"
echo "    Host    : ${VPS_USER}@${VPS_IP}"
echo "    App dir : ${APP_DIR}"
echo "    Spiders : ${SPIDERS:-all}"
echo ""

ssh "${VPS_USER}@${VPS_IP}" APP_DIR="${APP_DIR}" SPIDERS="${SPIDERS}" bash << 'REMOTE'
set -e

# ── Find the API container (supports plain Docker Compose and Coolify) ───
API=$(cd "$APP_DIR" && docker compose -f docker-compose.prod.yml ps -q api 2>/dev/null | head -1)
if [ -z "$API" ]; then
    # Coolify names containers like "api-<hash>-<id>"; match by prefix, exclude celery
    API=$(docker ps --format '{{.Names}}' | grep -E '^api-' | grep -vE 'celery|beat|worker' | head -1)
fi
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

# ── Run the pipeline detached from the SSH session ───────────
# nohup ensures the process survives SSH timeout or disconnection.
# Output is streamed to /tmp/togolm_pipeline.log and tailed here;
# closing the terminal is safe — the pipeline keeps running.
LOG=/tmp/togolm_pipeline.log
echo "==> Starting pipeline (scrape + ingest + embed)..."
echo "    Log : $LOG"
echo "    (safe to close terminal — pipeline will keep running)"
echo ""

nohup docker exec "$API" python scripts/run_scrapers.py $SPIDER_ARGS > "$LOG" 2>&1 &
BGPID=$!
echo "Pipeline PID : $BGPID"
echo ""

# Stream the log until the process finishes
tail -f "$LOG" &
TAILPID=$!
wait "$BGPID"
STATUS=$?
kill "$TAILPID" 2>/dev/null || true

echo ""
if [ "$STATUS" -eq 0 ]; then
    echo "Corpus update complete."
else
    echo "Pipeline exited with status $STATUS — check $LOG for details."
fi
REMOTE
