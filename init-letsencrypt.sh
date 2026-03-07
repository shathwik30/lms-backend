#!/bin/bash
# Run this ONCE on a fresh VPS before starting the full stack.
# Usage: ./init-letsencrypt.sh yourdomain.com you@email.com
set -e

DOMAIN="${1:?Usage: $0 <domain> <email>}"
EMAIL="${2:?Usage: $0 <domain> <email>}"
CERT_PATH="./certbot/conf/live/$DOMAIN"

# ── 1. Update nginx/default.conf with actual domain ──
if grep -q "example.com" nginx/default.conf; then
    sed -i "s/example\.com/$DOMAIN/g" nginx/default.conf
    echo "Updated nginx/default.conf with domain: $DOMAIN"
fi

# ── 2. Create a temporary self-signed cert so nginx can start ──
echo "Creating temporary self-signed certificate..."
mkdir -p "$CERT_PATH"
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "$CERT_PATH/privkey.pem" \
    -out    "$CERT_PATH/fullchain.pem" \
    -subj "/CN=$DOMAIN" 2>/dev/null

# ── 3. Start nginx (needs a cert to exist to load the SSL config) ──
echo "Starting nginx with temporary certificate..."
docker compose up -d nginx db redis

# Give nginx a moment to start
sleep 3

# ── 4. Request the real certificate from Let's Encrypt ──
echo "Requesting Let's Encrypt certificate for $DOMAIN..."
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

# ── 5. Reload nginx with the real certificate ──
echo "Reloading nginx..."
docker compose exec nginx nginx -s reload

echo ""
echo "SSL certificate issued successfully for $DOMAIN."
echo "Run 'docker compose up -d' to start all services."
