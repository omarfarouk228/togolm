#!/usr/bin/env bash
# =============================================================
# TogoLM — Upload a JSONL and ingest + embed it on the VPS
#
# Copies a local JSONL into the API container, runs ingestor.py,
# then embed_missing.py to generate pgvector embeddings.
#
# Usage:
#   VPS_IP=x.x.x.x bash scripts/vps/ingest_docs.sh corpus/datasets/mes_docs.jsonl
#   VPS_IP=x.x.x.x bash scripts/vps/ingest_docs.sh corpus/datasets/mes_docs.jsonl --source "ministere-finance.tg"
#   VPS_USER=togolm VPS_IP=x.x.x.x bash scripts/vps/ingest_docs.sh corpus/datasets/mes_docs.jsonl
# =============================================================
set -euo pipefail

VPS_IP="${VPS_IP:?Error: set VPS_IP before running (e.g. VPS_IP=x.x.x.x bash scripts/vps/ingest_docs.sh ...)}"
VPS_USER="${VPS_USER:-root}"
JSONL="${1:?Usage: VPS_IP=x.x.x.x bash scripts/vps/ingest_docs.sh <file.jsonl> [--source X]}"
shift

SOURCE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --source) SOURCE="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Validate local JSONL ──────────────────────────────────────
if [ ! -f "$JSONL" ]; then
    echo "ERROR: '${JSONL}' not found."
    exit 1
fi

FILENAME=$(basename "$JSONL")
REMOTE_TMP="/tmp/${FILENAME}"
CONTAINER_PATH="corpus/datasets/${FILENAME}"

EMBED_ARGS=""
if [ -n "$SOURCE" ]; then
    EMBED_ARGS="--source ${SOURCE}"
fi

echo "==> TogoLM — VPS Document Ingest & Embed"
echo "    Host   : ${VPS_USER}@${VPS_IP}"
echo "    File   : ${JSONL}"
echo "    Source : ${SOURCE:-all (no filter)}"
echo ""

# ── 1. Upload JSONL to VPS ────────────────────────────────────
echo "==> [1/4] Uploading ${FILENAME} to VPS..."
scp "${JSONL}" "${VPS_USER}@${VPS_IP}:${REMOTE_TMP}"
echo "    Done."
echo ""

# ── 2-4. Find container, copy file, ingest, embed ────────────
ssh "${VPS_USER}@${VPS_IP}" \
    REMOTE_TMP="${REMOTE_TMP}" \
    CONTAINER_PATH="${CONTAINER_PATH}" \
    FILENAME="${FILENAME}" \
    EMBED_ARGS="${EMBED_ARGS}" \
    bash << 'REMOTE'
set -e

# Find API container (supports plain Compose and Coolify)
API=$(docker ps --format '{{.Names}}' | grep -E '^api-' | grep -vE 'celery|beat|worker' | head -1)
if [ -z "$API" ]; then
    echo "ERROR: No API container found. Running containers:"
    docker ps --format '{{.Names}}'
    exit 1
fi
echo "==> [2/4] Container : $API"
echo ""

# Copy JSONL into container
echo "==> [2/4] Copying ${FILENAME} into container..."
docker cp "$REMOTE_TMP" "$API:/app/${CONTAINER_PATH}"
rm -f "$REMOTE_TMP"
echo "    Done."
echo ""

# Ingest into PostgreSQL (text only, fast)
echo "==> [3/4] Ingesting into PostgreSQL..."
docker exec -e PYTHONUNBUFFERED=1 "$API" \
    python -m corpus.processors.ingestor "${CONTAINER_PATH}" --no-embed
echo ""

# Generate embeddings
echo "==> [4/4] Generating embeddings..."
docker exec -e PYTHONUNBUFFERED=1 "$API" \
    python scripts/corpus/embed_missing.py $EMBED_ARGS
echo ""

echo "==> All done. Documents are live in the corpus."
REMOTE
