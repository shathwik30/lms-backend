import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction
from django.utils import timezone

from apps.exams.models import ExamAttempt
from apps.exams.services import ExamService
from core.constants import ExamConstants, TaskConfig

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=TaskConfig.HEAVY_MAX_RETRIES,
    soft_time_limit=TaskConfig.HEAVY_SOFT_TIME_LIMIT,
    time_limit=TaskConfig.HEAVY_TIME_LIMIT,
)
def auto_submit_timed_out_exams(self):
    """
    Auto-submit exam attempts that exceeded their duration.

    Finds IN_PROGRESS attempts where started_at + duration has passed,
    evaluates any answers already saved, then marks them as TIMED_OUT.
    """
    count = 0
    try:
        in_progress = ExamAttempt.objects.filter(
            status=ExamAttempt.Status.IN_PROGRESS,
        ).select_related("exam")

        now = timezone.now()

        for attempt in in_progress:
            deadline = attempt.started_at + timedelta(minutes=attempt.exam.duration_minutes)
            if now <= deadline:
                continue

            with transaction.atomic():
                # Lock row and re-check status to prevent race with manual submission
                try:
                    attempt = (
                        ExamAttempt.objects.select_for_update()
                        .select_related("exam")
                        .get(
                            pk=attempt.pk,
                            status=ExamAttempt.Status.IN_PROGRESS,
                        )
                    )
                except ExamAttempt.DoesNotExist:
                    continue

                # Score any answers that were saved before timeout
                total_score = ExamService._score_timed_out_attempt(attempt)

                attempt.status = ExamAttempt.Status.TIMED_OUT
                attempt.submitted_at = deadline  # Use actual deadline, not current time
                attempt.score = total_score
                pass_score = (attempt.exam.passing_percentage / ExamConstants.PERCENTAGE_DIVISOR) * attempt.total_marks
                attempt.is_passed = total_score >= pass_score
                attempt.save(update_fields=["status", "submitted_at", "score", "is_passed"])

                logger.info(
                    "Auto-submitted attempt %d for student %d (score=%d/%d)",
                    attempt.pk,
                    attempt.student_id,
                    total_score,
                    attempt.total_marks,
                )
                count += 1

        logger.info("Auto-submitted %d timed-out exams.", count)
        return count
    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded while auto-submitting exams (processed %d so far).", count)
        raise
    except Exception as exc:
        logger.exception("Error auto-submitting timed-out exams: %s", exc)
        raise self.retry(exc=exc) from exc
