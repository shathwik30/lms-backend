from datetime import timedelta
from pathlib import Path

import dj_database_url
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# ──────────────────────────────────────────────
# Apps
# ──────────────────────────────────────────────

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "django_prometheus",
]

LOCAL_APPS = [
    "core",
    "apps.users",
    "apps.levels",
    "apps.courses",
    "apps.exams",
    "apps.payments",
    "apps.progress",
    "apps.doubts",
    "apps.feedback",
    "apps.analytics",
    "apps.notifications",
    "apps.home",
    "apps.search",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ──────────────────────────────────────────────
# Middleware
# ──────────────────────────────────────────────

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.TrailingSlashMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

APPEND_SLASH = False

# ──────────────────────────────────────────────
# URL / WSGI
# ──────────────────────────────────────────────

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ──────────────────────────────────────────────
# Templates
# ──────────────────────────────────────────────

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────

DATABASES = {
    "default": dj_database_url.config(default="sqlite:///db.sqlite3"),
}

# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ──────────────────────────────────────────────
# DRF
# ──────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",
        "user": "120/minute",
        "login": "5/minute",
        "payment": "10/minute",
        "exam_submit": "30/hour",
        "search": "60/minute",
        "doubt_create": "10/minute",
        "feedback": "20/minute",
        "progress_update": "120/minute",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
}

# ──────────────────────────────────────────────
# OpenAPI / Swagger
# ──────────────────────────────────────────────

SPECTACULAR_SETTINGS = {
    "TITLE": "LMS API",
    "DESCRIPTION": "IIT/JEE Preparation LMS — level-based course progression with exams, payments, and analytics.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v1/",
    "ENUM_NAME_OVERRIDES": {
        "PurchaseStatusEnum": "apps.payments.models.Purchase.Status",
        "TransactionStatusEnum": "apps.payments.models.PaymentTransaction.Status",
        "ExamAttemptStatusEnum": "apps.exams.models.ExamAttempt.Status",
        "DoubtStatusEnum": "apps.doubts.models.DoubtTicket.Status",
        "LevelProgressStatusEnum": "apps.progress.models.LevelProgress.Status",
    },
    "TAGS": [
        {"name": "Auth", "description": "Registration, login, logout, token refresh"},
        {"name": "Levels", "description": "Level & week management"},
        {"name": "Courses", "description": "Courses, sessions, and resources"},
        {"name": "Exams", "description": "Exams, questions, attempts"},
        {"name": "Payments", "description": "Payment initiation, verification, purchases"},
        {"name": "Progress", "description": "Student dashboard & session progress"},
        {"name": "Doubts", "description": "Doubt threads and replies"},
        {"name": "Feedback", "description": "Session feedback"},
        {"name": "Analytics", "description": "Revenue & level analytics (admin)"},
        {"name": "Notifications", "description": "User notifications"},
        {"name": "Home", "description": "Banners and featured content"},
        {"name": "Search", "description": "Global search"},
    ],
}

# ──────────────────────────────────────────────
# JWT
# ──────────────────────────────────────────────

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# ──────────────────────────────────────────────
# i18n / Timezone
# ──────────────────────────────────────────────

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ──────────────────────────────────────────────
# Static & Media
# ──────────────────────────────────────────────

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ──────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

# ──────────────────────────────────────────────
# Upload size limits
# ──────────────────────────────────────────────

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5 MB

# ──────────────────────────────────────────────
# Cache & Celery
# ──────────────────────────────────────────────

CACHES = {
    "default": {
        "BACKEND": env(
            "CACHE_BACKEND",
            default="django.core.cache.backends.locmem.LocMemCache",
        ),
        "LOCATION": env("CACHE_LOCATION", default="lms-cache"),
    }
}

# Cache timeouts (seconds)
CACHE_TTL_SHORT = 60  # 1 min  — leaderboard, featured courses
CACHE_TTL_MEDIUM = 300  # 5 min  — level list, course list
CACHE_TTL_LONG = 3600  # 1 hour — rarely changing data

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = env.bool("CELERY_TASK_EAGER_PROPAGATES", default=False)
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# Upstash / any rediss:// URL needs ssl_cert_reqs for Celery
if CELERY_BROKER_URL.startswith("rediss://") and "ssl_cert_reqs" not in CELERY_BROKER_URL:
    _sep = "&" if "?" in CELERY_BROKER_URL else "?"
    CELERY_BROKER_URL += f"{_sep}ssl_cert_reqs=CERT_REQUIRED"
if CELERY_RESULT_BACKEND.startswith("rediss://") and "ssl_cert_reqs" not in CELERY_RESULT_BACKEND:
    _sep = "&" if "?" in CELERY_RESULT_BACKEND else "?"
    CELERY_RESULT_BACKEND += f"{_sep}ssl_cert_reqs=CERT_REQUIRED"


# ──────────────────────────────────────────────
# Razorpay
# ──────────────────────────────────────────────

RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="")

# ──────────────────────────────────────────────
# Google OAuth (via Firebase)
# ──────────────────────────────────────────────

GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")

# Firebase Admin credentials — supply ONE of:
#   FIREBASE_CREDENTIALS_PATH : filesystem path to the service account JSON
#   FIREBASE_CREDENTIALS_JSON : raw JSON string (preferred in containers / CI)
FIREBASE_CREDENTIALS_PATH = env("FIREBASE_CREDENTIALS_PATH", default="")
FIREBASE_CREDENTIALS_JSON = env("FIREBASE_CREDENTIALS_JSON", default="")

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# ──────────────────────────────────────────────
# Email
# ──────────────────────────────────────────────

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="core.email_backends.ResendEmailBackend",
)
RESEND_API_KEY = env("RESEND_API_KEY", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="onboarding@resend.dev")

FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

PASSWORD_RESET_TIMEOUT = 3600  # 1 hour

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
