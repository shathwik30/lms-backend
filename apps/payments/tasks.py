import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

from apps.payments.models import Purchase
from core.constants import TaskConfig

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=TaskConfig.HEAVY_MAX_RETRIES,
    soft_time_limit=TaskConfig.HEAVY_SOFT_TIME_LIMIT,
    time_limit=TaskConfig.HEAVY_TIME_LIMIT,
)
def expire_purchases(self):
    """Mark purchases past their expiry date as EXPIRED."""
    try:
        expired = Purchase.objects.filter(
            status=Purchase.Status.ACTIVE,
            expires_at__lte=timezone.now(),
        )
        count = expired.update(status=Purchase.Status.EXPIRED)
        logger.info("Expired %d purchases.", count)
        return count
    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded while expiring purchases.")
        raise
    except Exception as exc:
        logger.exception("Error expiring purchases: %s", exc)
        raise self.retry(exc=exc) from exc
