#!/bin/bash
# Run this ONCE on a fresh VPS before starting the full stack.
# Usage: ./init-letsencrypt.sh yourdomain.com you@email.com
set -e

DOMAIN="${1:?Usage: $0 <domain> <email>}"
EMAIL="${2:?Usage: $0 <domain> <email>}"
CERT_PATH="./certbot/conf/live/$DOMAIN"

mkdir -p ./certbot/conf ./certbot/www

set_env() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" .env.docker; then
        sed -i "s|^${key}=.*|${key}=${value}|" .env.docker
    else
        printf '%s=%s\n' "$key" "$value" >> .env.docker
    fi
}

# ── 1. Ensure .env.docker exists and knows the domain ──
if [ ! -f .env.docker ]; then
    cp .env.docker.example .env.docker
    echo "Created .env.docker from .env.docker.example"
fi

set_env "DOMAIN" "$DOMAIN"
set_env "LETSENCRYPT_EMAIL" "$EMAIL"
set_env "ALLOWED_HOSTS" "$DOMAIN"
set_env "CSRF_TRUSTED_ORIGINS" "https://$DOMAIN"
set_env "FRONTEND_URL" "https://$DOMAIN"
set_env "SECURE_SSL_REDIRECT" "True"
set_env "SECURE_HSTS_SECONDS" "31536000"
set_env "SESSION_COOKIE_SECURE" "True"
set_env "CSRF_COOKIE_SECURE" "True"

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

# ── 4. Delete temp self-signed cert so certbot doesn't prompt ──
echo "Removing temporary self-signed certificate..."
docker compose run --rm --entrypoint "sh -c 'rm -rf /etc/letsencrypt/live/$DOMAIN /etc/letsencrypt/archive/$DOMAIN /etc/letsencrypt/renewal/$DOMAIN.conf'" certbot

# ── 5. Request the real certificate from Let's Encrypt ──
echo "Requesting Let's Encrypt certificate for $DOMAIN..."
docker compose run --rm --entrypoint certbot certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --non-interactive \
    -d "$DOMAIN"

# ── 6. Reload nginx with the real certificate ──
echo "Reloading nginx..."
docker compose exec nginx nginx -s reload

echo ""
echo "SSL certificate issued successfully for $DOMAIN."
echo "Run 'docker compose up -d' to start all services."
