from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

# Disable throttling in dev/test to avoid flaky tests
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}  # noqa: F405

# Console email in dev/test (no API key needed)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Run Celery tasks synchronously in dev/test
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable view-level caching in dev/test to avoid cross-test cache pollution
# (LocMemCache from base.py is still used for OTP)
CACHE_TTL_SHORT = 0
CACHE_TTL_MEDIUM = 0
CACHE_TTL_LONG = 0
