import sentry_sdk

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])  # noqa: F405
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405

# ── Railway support ──
# Railway health checks use hostname "healthcheck.railway.app".
ALLOWED_HOSTS.append("healthcheck.railway.app")

# Railway sets RAILWAY_PUBLIC_DOMAIN when a domain is assigned to the service.
RAILWAY_PUBLIC_DOMAIN = env("RAILWAY_PUBLIC_DOMAIN", default="")  # noqa: F405
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_PUBLIC_DOMAIN}")

SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]  # Railway health probes may not send X-Forwarded-Proto
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

# ── WhiteNoise — serve static files without nginx ──
# Inserted after SecurityMiddleware (index 1) as recommended by WhiteNoise docs.
MIDDLEWARE.insert(2, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ── Database connection pooling ──
# Keep connections alive across requests to avoid reconnect overhead.
# CONN_HEALTH_CHECKS ensures stale connections are recycled transparently.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=600)  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

# Use Redis for cache in production (required for OTP)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("CACHE_LOCATION", default=REDIS_URL),  # noqa: F405
    }
}

# ── Sentry error tracking ──
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),  # noqa: F405
        profiles_sample_rate=env.float("SENTRY_PROFILES_SAMPLE_RATE", default=0.1),  # noqa: F405
        send_default_pii=False,
    )

# ── Structured logging for production ──
LOGGING["formatters"]["structured"] = {  # type: ignore[index]  # noqa: F405
    "format": "{levelname} {asctime} {name} {module} {process:d} {thread:d} {message}",
    "style": "{",
}
LOGGING["handlers"]["console"]["formatter"] = "structured"  # type: ignore[index]  # noqa: F405

# Override apps logger to INFO in production (no DEBUG)
LOGGING["loggers"]["apps"]["level"] = "INFO"  # type: ignore[index]  # noqa: F405

# CORS — open to all origins for now (frontend team testing)
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Upload size limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB

# Allow anyone to view API docs (frontend team testing)
SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.AllowAny"]  # noqa: F405

# ── Required secrets validation ──
import logging as _logging  # noqa: E402

_prod_logger = _logging.getLogger("config.settings.production")
if not RAZORPAY_KEY_ID:  # noqa: F405
    _prod_logger.warning("RAZORPAY_KEY_ID is not set — payment features will not work.")
if not RAZORPAY_KEY_SECRET:  # noqa: F405
    _prod_logger.warning("RAZORPAY_KEY_SECRET is not set — payment features will not work.")
if not RAZORPAY_WEBHOOK_SECRET:  # noqa: F405
    _prod_logger.warning("RAZORPAY_WEBHOOK_SECRET is not set — webhook verification disabled.")
