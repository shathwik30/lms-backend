import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction
from django.utils import timezone

from apps.exams.models import ExamAttempt
from core.constants import ExamConstants, TaskConfig

logger = logging.getLogger(__name__)


def _score_attempt(attempt):
    """Evaluate submitted answers and compute score for a timed-out attempt."""
    total_score = 0
    attempt_questions = list(
        attempt.attempt_questions.select_related("question").prefetch_related("question__options", "selected_options")
    )

    for aq in attempt_questions:
        if aq.selected_option_id:
            # MCQ — check if selected option is correct
            option = next((o for o in aq.question.options.all() if o.pk == aq.selected_option_id), None)
            if option:
                aq.is_correct = option.is_correct
                aq.marks_awarded = aq.question.marks if option.is_correct else -aq.question.negative_marks
            else:
                aq.is_correct = False
                aq.marks_awarded = -aq.question.negative_marks
        elif any(True for _ in aq.selected_options.all()):
            # MULTI_MCQ — compare sets
            correct_ids = {o.id for o in aq.question.options.all() if o.is_correct}
            selected_ids = {o.id for o in aq.selected_options.all()}
            aq.is_correct = selected_ids == correct_ids
            aq.marks_awarded = aq.question.marks if aq.is_correct else -aq.question.negative_marks
        elif aq.text_answer:
            # FILL_BLANK
            correct = (aq.question.correct_text_answer or "").strip()
            aq.is_correct = aq.text_answer.strip().lower() == correct.lower()
            aq.marks_awarded = aq.question.marks if aq.is_correct else -aq.question.negative_marks
        else:
            aq.is_correct = None
            aq.marks_awarded = 0

        total_score += aq.marks_awarded

    from apps.exams.models import AttemptQuestion

    AttemptQuestion.objects.bulk_update(attempt_questions, ["is_correct", "marks_awarded"])
    return total_score


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
    try:
        in_progress = ExamAttempt.objects.filter(
            status=ExamAttempt.Status.IN_PROGRESS,
        ).select_related("exam")

        now = timezone.now()
        count = 0

        for attempt in in_progress:
            deadline = attempt.started_at + timedelta(minutes=attempt.exam.duration_minutes)
            if now <= deadline:
                continue

            with transaction.atomic():
                # Re-fetch with lock to prevent race with manual submission
                try:
                    locked = ExamAttempt.objects.select_for_update(skip_locked=True).get(
                        pk=attempt.pk,
                        status=ExamAttempt.Status.IN_PROGRESS,
                    )
                except ExamAttempt.DoesNotExist:
                    continue

                # Score any answers that were saved before timeout
                total_score = _score_attempt(locked)

                locked.status = ExamAttempt.Status.TIMED_OUT
                locked.submitted_at = deadline  # Use actual deadline, not current time
                locked.score = total_score
                pass_score = (locked.exam.passing_percentage / ExamConstants.PERCENTAGE_DIVISOR) * locked.total_marks
                locked.is_passed = total_score >= pass_score
                locked.save()

                logger.info(
                    "Auto-submitted attempt %d for student %d (score=%d/%d)",
                    locked.pk,
                    locked.student_id,
                    total_score,
                    locked.total_marks,
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
