import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db.models import Count, Sum
from django.utils import timezone

from apps.analytics.models import DailyRevenue, LevelAnalytics
from apps.exams.models import Exam, ExamAttempt
from apps.levels.models import Level
from apps.payments.models import PaymentTransaction, Purchase
from core.constants import TaskConfig

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=TaskConfig.HEAVY_MAX_RETRIES,
    soft_time_limit=TaskConfig.HEAVY_SOFT_TIME_LIMIT,
    time_limit=TaskConfig.HEAVY_TIME_LIMIT,
)
def aggregate_daily_analytics(self):
    """
    Aggregate yesterday's data into DailyRevenue and LevelAnalytics.

    Runs daily via Celery Beat (typically at 01:00).
    """
    try:
        yesterday = timezone.localdate() - timedelta(days=1)

        # --- Daily Revenue ---
        txn_agg = PaymentTransaction.objects.filter(
            status=PaymentTransaction.Status.SUCCESS,
            created_at__date=yesterday,
        ).aggregate(
            total_revenue=Sum("amount"),
            total_transactions=Count("id"),
        )

        DailyRevenue.objects.update_or_create(
            date=yesterday,
            defaults={
                "total_revenue": txn_agg["total_revenue"] or 0,
                "total_transactions": txn_agg["total_transactions"] or 0,
            },
        )

        # --- Per-Level Analytics ---
        for level in Level.objects.filter(is_active=True):
            attempts = ExamAttempt.objects.filter(
                exam__level=level,
                exam__exam_type=Exam.ExamType.LEVEL_FINAL,
                submitted_at__date=yesterday,
            )
            total_attempts = attempts.count()
            total_passes = attempts.filter(is_passed=True).count()
            total_failures = attempts.filter(is_passed=False).count()

            purchases = Purchase.objects.filter(
                course__level=level,
                purchased_at__date=yesterday,
            )
            total_purchases = purchases.count()
            revenue = purchases.aggregate(total=Sum("amount_paid"))["total"] or 0

            LevelAnalytics.objects.update_or_create(
                level=level,
                date=yesterday,
                defaults={
                    "total_attempts": total_attempts,
                    "total_passes": total_passes,
                    "total_failures": total_failures,
                    "total_purchases": total_purchases,
                    "revenue": revenue,
                },
            )

        logger.info("Aggregated analytics for %s.", yesterday)
    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded while aggregating analytics.")
        raise
    except Exception as exc:
        logger.exception("Error aggregating daily analytics: %s", exc)
        raise self.retry(exc=exc) from exc
