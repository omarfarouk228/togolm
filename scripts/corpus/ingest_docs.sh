#!/usr/bin/env bash
# =============================================================
# TogoLM — Convert local files (PDF/TXT/MD) to corpus JSONL
#
# Runs local_ingestor.py on a file or folder and writes a JSONL
# ready to be sent to the VPS with vps/ingest_docs.sh.
#
# Usage:
#   bash scripts/corpus/ingest_docs.sh mon_dossier/
#   bash scripts/corpus/ingest_docs.sh rapport.pdf
#   bash scripts/corpus/ingest_docs.sh mon_dossier/ --source "ministere-finance.tg" --category legal
#   bash scripts/corpus/ingest_docs.sh mon_dossier/ --output corpus/datasets/custom.jsonl
#
# Options:
#   --source   Source identifier  (default: local)
#   --category Corpus category    (default: legal)
#   --output   Output JSONL path  (default: corpus/datasets/<input_name>.jsonl)
# =============================================================
set -euo pipefail

# ── Arguments ────────────────────────────────────────────────
INPUT="${1:?Usage: bash scripts/corpus/ingest_docs.sh <file_or_folder> [--source X] [--category X] [--output X]}"
shift

SOURCE="local"
CATEGORY="legal"
OUTPUT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)   SOURCE="$2";   shift 2 ;;
        --category) CATEGORY="$2"; shift 2 ;;
        --output)   OUTPUT="$2";   shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Default output path ───────────────────────────────────────
if [ -z "$OUTPUT" ]; then
    BASENAME=$(basename "${INPUT%/}")
    STEM="${BASENAME%.*}"
    OUTPUT="corpus/datasets/${STEM}.jsonl"
fi

# ── Validate input ────────────────────────────────────────────
if [ ! -e "$INPUT" ]; then
    echo "ERROR: '${INPUT}' not found."
    exit 1
fi

echo "==> TogoLM — Local Document Ingestion"
echo "    Input    : ${INPUT}"
echo "    Source   : ${SOURCE}"
echo "    Category : ${CATEGORY}"
echo "    Output   : ${OUTPUT}"
echo ""

uv run python -m corpus.processors.local_ingestor "${INPUT}" \
    --source "${SOURCE}" \
    --category "${CATEGORY}" \
    --output "${OUTPUT}"

echo ""
echo "==> Done. JSONL ready at: ${OUTPUT}"
echo "    Next step:"
echo "    VPS_IP=x.x.x.x bash scripts/vps/ingest_docs.sh ${OUTPUT} --source '${SOURCE}'"
