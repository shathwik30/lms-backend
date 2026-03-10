import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db.models import Case, Count, IntegerField, Sum, When
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
        active_levels = list(Level.objects.filter(is_active=True))
        active_level_ids = [level.id for level in active_levels]

        attempt_stats = {
            row["exam__level_id"]: row
            for row in ExamAttempt.objects.filter(
                exam__level_id__in=active_level_ids,
                exam__exam_type=Exam.ExamType.LEVEL_FINAL,
                submitted_at__date=yesterday,
            )
            .values("exam__level_id")
            .annotate(
                total_attempts=Count("id"),
                total_passes=Count(Case(When(is_passed=True, then=1), output_field=IntegerField())),
                total_failures=Count(Case(When(is_passed=False, then=1), output_field=IntegerField())),
            )
        }

        purchase_stats = {
            row["level_id"]: row
            for row in Purchase.objects.filter(
                level_id__in=active_level_ids,
                purchased_at__date=yesterday,
            )
            .values("level_id")
            .annotate(
                total_purchases=Count("id"),
                revenue=Sum("amount_paid"),
            )
        }

        for level in active_levels:
            level_attempt_stats = attempt_stats.get(level.id, {})
            level_purchase_stats = purchase_stats.get(level.id, {})
            LevelAnalytics.objects.update_or_create(
                level=level,
                date=yesterday,
                defaults={
                    "total_attempts": level_attempt_stats.get("total_attempts", 0),
                    "total_passes": level_attempt_stats.get("total_passes", 0),
                    "total_failures": level_attempt_stats.get("total_failures", 0),
                    "total_purchases": level_purchase_stats.get("total_purchases", 0),
                    "revenue": level_purchase_stats.get("revenue") or 0,
                },
            )

        logger.info("Aggregated analytics for %s.", yesterday)
    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded while aggregating analytics.")
        raise
    except Exception as exc:
        logger.exception("Error aggregating daily analytics: %s", exc)
        raise self.retry(exc=exc) from exc
