#!/bin/sh
set -e

echo "[start] Migrating database..."
python -u manage.py migrate --noinput 2>&1
echo "[start] Migrations done."

echo "[start] Collecting static files..."
python -u manage.py collectstatic --noinput 2>&1
echo "[start] Static files done."

echo "[start] Starting gunicorn on port ${PORT:-8000}..."
exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --forwarded-allow-ips "*"
