import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils import timezone

from apps.payments.models import PaymentTransaction, Purchase
from apps.payments.services import PaymentService
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


@shared_task(
    bind=True,
    max_retries=TaskConfig.HEAVY_MAX_RETRIES,
    soft_time_limit=TaskConfig.HEAVY_SOFT_TIME_LIMIT,
    time_limit=TaskConfig.HEAVY_TIME_LIMIT,
)
def reconcile_pending_payments(self):
    """Fulfill payments that were captured at Razorpay but never hit /verify/.

    Window: transactions older than 5 min (give the browser its chance) and
    newer than 24 h (abandoned after that). Dev orders are skipped.
    """
    if not settings.RAZORPAY_KEY_ID:
        return 0

    from core.services.razorpay import RazorpayService

    now = timezone.now()
    pending = (
        PaymentTransaction.objects.filter(
            status=PaymentTransaction.Status.PENDING,
            created_at__lte=now - timedelta(minutes=5),
            created_at__gte=now - timedelta(hours=24),
        )
        .exclude(razorpay_order_id__startswith="dev_")
        .only("id", "razorpay_order_id")
    )

    fulfilled = 0
    for txn in pending:
        try:
            payments = RazorpayService.get_order_payments(txn.razorpay_order_id)
        except SoftTimeLimitExceeded:
            raise
        except Exception as exc:
            logger.warning("Reconcile: fetch failed for order %s: %s", txn.razorpay_order_id, exc)
            continue

        captured = next((p for p in payments if p.get("status") == "captured"), None)
        if not captured:
            continue

        try:
            if PaymentService.fulfill_captured_payment(txn.razorpay_order_id, captured["id"]):
                fulfilled += 1
        except Exception as exc:
            logger.exception("Reconcile: fulfillment failed for order %s: %s", txn.razorpay_order_id, exc)

    logger.info("Reconciled %d pending payment(s).", fulfilled)
    return fulfilled
