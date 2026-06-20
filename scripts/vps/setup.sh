#!/usr/bin/env bash
# ============================================================
# TogoLM — VPS initial setup script
# Run ONCE as root on a fresh Ubuntu 22.04 / Debian 12 server.
#
# Usage:
#   ssh root@YOUR_VPS_IP
#   curl -sSL https://raw.githubusercontent.com/omarfarouk228/togolm/main/scripts/vps_setup.sh | bash
#   # OR copy the file and run: bash scripts/vps_setup.sh
# ============================================================
set -euo pipefail

REPO_URL="https://github.com/omarfarouk228/togolm.git"
APP_DIR="/opt/togolm"
APP_USER="togolm"

echo "==> [1/6] Installing Docker..."
apt-get update -qq
apt-get install -y --no-install-recommends ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker

echo "==> [2/6] Creating app user..."
id -u $APP_USER &>/dev/null || useradd --create-home --shell /bin/bash $APP_USER
usermod -aG docker $APP_USER

echo "==> [3/6] Cloning repository..."
if [ -d "$APP_DIR" ]; then
    echo "  Directory $APP_DIR already exists — pulling latest..."
    cd "$APP_DIR" && git pull origin main
else
    git clone "$REPO_URL" "$APP_DIR"
fi
chown -R $APP_USER:$APP_USER "$APP_DIR"

echo "==> [4/6] Creating .env.prod (fill in your secrets!)..."
cat > "$APP_DIR/.env.prod" << 'ENVEOF'
# ── PostgreSQL ──────────────────────────────────────────────
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=togolm
POSTGRES_USER=togolm
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD

# ── Gemini API (embeddings + generation) ───────────────────
GEMINI_API_KEY=CHANGE_ME_YOUR_GEMINI_KEY

# ── API security ───────────────────────────────────────────
API_SECRET_KEY=CHANGE_ME_RANDOM_64_HEX
API_ENV=production

# ── Celery ─────────────────────────────────────────────────
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
ENVEOF

echo ""
echo "  ⚠️  Edit $APP_DIR/.env.prod before continuing!"
echo "      nano $APP_DIR/.env.prod"
echo ""

echo "==> [5/6] Creating SSL certificate placeholder (replace with real certs)..."
mkdir -p "$APP_DIR/nginx/certs"
if [ ! -f "$APP_DIR/nginx/certs/fullchain.pem" ]; then
    # Self-signed cert for initial testing — replace with Let's Encrypt
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$APP_DIR/nginx/certs/privkey.pem" \
        -out "$APP_DIR/nginx/certs/fullchain.pem" \
        -subj "/CN=api.togolm.ai" 2>/dev/null
    echo "  ⚠️  Self-signed cert generated. Replace with Let's Encrypt!"
fi

echo "==> [6/6] Done. Next steps:"
echo ""
echo "  1. Edit secrets:     nano $APP_DIR/.env.prod"
echo "  2. Import DB dump:   bash $APP_DIR/scripts/db_import.sh /tmp/togolm.dump"
echo "  3. Start services:   cd $APP_DIR && docker compose -f docker-compose.prod.yml up -d"
echo "  4. Get TLS cert:     certbot certonly --standalone -d api.togolm.ai"
echo "     Then copy:        cp /etc/letsencrypt/live/api.togolm.ai/fullchain.pem $APP_DIR/nginx/certs/"
echo "                       cp /etc/letsencrypt/live/api.togolm.ai/privkey.pem $APP_DIR/nginx/certs/"
echo "     Then restart:     docker compose -f docker-compose.prod.yml restart nginx"
echo ""
echo "  GitHub Actions secrets to set:"
echo "    VPS_HOST  = $(curl -s ifconfig.me)"
echo "    VPS_USER  = $APP_USER (or root)"
echo "    VPS_SSH_KEY = (your private SSH key)"
