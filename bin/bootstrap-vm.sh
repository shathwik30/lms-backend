#!/bin/bash
set -euo pipefail

DOMAIN="${1:?Usage: $0 <domain> <email>}"
EMAIL="${2:?Usage: $0 <domain> <email>}"
APP_DIR="${APP_DIR:-$PWD}"

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This bootstrap script currently supports Debian/Ubuntu VMs only."
    exit 1
fi

echo "[bootstrap] Updating apt metadata..."
sudo apt-get update

if ! command -v docker >/dev/null 2>&1; then
    echo "[bootstrap] Installing Docker..."
    sudo apt-get install -y docker.io
    sudo systemctl enable docker
    sudo systemctl start docker
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "[bootstrap] Installing Docker Compose plugin..."
    sudo apt-get install -y docker-compose-plugin
fi

if ! command -v git >/dev/null 2>&1; then
    echo "[bootstrap] Installing git..."
    sudo apt-get install -y git
fi

if ! groups "$USER" | grep -q '\bdocker\b'; then
    echo "[bootstrap] Adding $USER to docker group..."
    sudo usermod -aG docker "$USER"
    echo "[bootstrap] Re-login required for docker group membership. Run this script again after reconnecting."
    exit 0
fi

cd "$APP_DIR"

if [ ! -f .env.docker ]; then
    echo "[bootstrap] Creating .env.docker from template..."
    cp .env.docker.example .env.docker
fi

if ! grep -q '^SECRET_KEY=' .env.docker || grep -q '^SECRET_KEY=change-me' .env.docker; then
    GENERATED_SECRET="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
)"
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${GENERATED_SECRET}|" .env.docker
    echo "[bootstrap] Generated Django SECRET_KEY."
fi

echo "[bootstrap] Starting TLS bootstrap for ${DOMAIN}..."
chmod +x ./init-letsencrypt.sh
./init-letsencrypt.sh "$DOMAIN" "$EMAIL"

echo "[bootstrap] Building and starting the full stack..."
docker compose up -d --build

echo "[bootstrap] Active containers:"
docker compose ps

echo "[bootstrap] Done. Test https://${DOMAIN}"
