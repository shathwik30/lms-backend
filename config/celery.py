import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("lms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# ── Beat schedule (periodic tasks) ──

app.conf.beat_schedule = {
    "expire-purchases-daily": {
        "task": "apps.payments.tasks.expire_purchases",
        "schedule": crontab(hour=0, minute=30),
    },
    "reconcile-pending-payments": {
        "task": "apps.payments.tasks.reconcile_pending_payments",
        "schedule": crontab(minute="*/5"),
    },
    "auto-submit-timed-out-exams": {
        "task": "apps.exams.tasks.auto_submit_timed_out_exams",
        "schedule": crontab(minute="*/5"),
    },
    "aggregate-daily-analytics": {
        "task": "apps.analytics.tasks.aggregate_daily_analytics",
        "schedule": crontab(hour=1, minute=0),
    },
}
