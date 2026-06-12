#!/usr/bin/env bash
# ============================================================
# TogoLM — Export local DB and import on VPS
#
# Run this on your LOCAL machine after embedding is complete.
#
# Usage:
#   bash scripts/db_export.sh YOUR_VPS_IP
#   bash scripts/db_export.sh YOUR_VPS_IP your_ssh_user   # default: root
# ============================================================
set -euo pipefail

VPS_IP="${1:?Usage: bash scripts/db_export.sh VPS_IP [VPS_USER]}"
VPS_USER="${2:-root}"
DUMP_FILE="togolm_$(date +%Y%m%d_%H%M).dump"

# ── Local DB settings (from .env) ────────────────────────────
set -a; source "$(dirname "$0")/../.env"; set +a
PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
PG_USER="${POSTGRES_USER:-postgres}"
PG_DB="${POSTGRES_DB:-togolm}"

echo "==> [1/4] Dumping local DB '$PG_DB' on $PG_HOST:$PG_PORT..."
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h "$PG_HOST" \
    -p "$PG_PORT" \
    -U "$PG_USER" \
    -d "$PG_DB" \
    -Fc \
    --no-owner \
    --no-acl \
    -f "$DUMP_FILE"

SIZE=$(du -sh "$DUMP_FILE" | cut -f1)
echo "  Done: $DUMP_FILE ($SIZE)"

echo "==> [2/4] Copying dump to VPS ($VPS_USER@$VPS_IP)..."
scp "$DUMP_FILE" "${VPS_USER}@${VPS_IP}:/tmp/$DUMP_FILE"

echo "==> [3/4] Importing on VPS..."
ssh "${VPS_USER}@${VPS_IP}" bash << REMOTE
set -e

DUMP="/tmp/$DUMP_FILE"
APP_DIR="/opt/togolm"

# Load prod env vars
set -a; source "\$APP_DIR/.env.prod"; set +a

echo "  Starting DB container if not running..."
cd "\$APP_DIR"
docker compose -f docker-compose.prod.yml up -d db
echo "  Waiting for PostgreSQL to be ready..."
sleep 10

echo "  Creating extensions..."
docker compose -f docker-compose.prod.yml exec -T db \
    psql -U "\$POSTGRES_USER" -d "\$POSTGRES_DB" \
    -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" \
    2>/dev/null || true

echo "  Restoring dump (~1 GB, may take a few minutes)..."
docker compose -f docker-compose.prod.yml exec -T db \
    pg_restore \
    -U "\$POSTGRES_USER" \
    -d "\$POSTGRES_DB" \
    --no-owner \
    --no-acl \
    -Fc \
    < "\$DUMP"

echo "  Cleaning up dump file..."
rm -f "\$DUMP"

echo "  Verifying restore..."
docker compose -f docker-compose.prod.yml exec -T db \
    psql -U "\$POSTGRES_USER" -d "\$POSTGRES_DB" \
    -c "SELECT COUNT(*) AS docs FROM documents; SELECT COUNT(*) AS chunks FROM chunks WHERE embedding IS NOT NULL;"

echo "  DB restored successfully!"
REMOTE

echo "==> [4/4] Cleanup local dump..."
rm -f "$DUMP_FILE"

echo ""
echo "✅ Done! Now start all services on VPS:"
echo "   ssh ${VPS_USER}@${VPS_IP}"
echo "   cd /opt/togolm"
echo "   docker compose -f docker-compose.prod.yml up -d"
