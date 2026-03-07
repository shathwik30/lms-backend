"""
Tests for retry logic and error handling in apps/exams/tasks.py.

Covers:
  - auto_submit_timed_out_exams: SoftTimeLimitExceeded (re-raised, not retried)
  - auto_submit_timed_out_exams: generic Exception triggers self.retry()
  - auto_submit_timed_out_exams: ExamAttempt.DoesNotExist during select_for_update (skipped)
"""

from datetime import timedelta
from unittest.mock import patch

from celery.exceptions import SoftTimeLimitExceeded
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.exams.models import ExamAttempt
from apps.exams.tasks import auto_submit_timed_out_exams
from core.constants import TaskConfig
from core.test_utils import TestFactory

HEAVY_EXPECTED_TOTAL_CALLS = TaskConfig.HEAVY_MAX_RETRIES + 1


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class AutoSubmitRetryTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1)
        self.exam = self.data["exam"]

    def _create_timed_out_attempt(self):
        """Create an IN_PROGRESS attempt that has exceeded its duration."""
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            status=ExamAttempt.Status.IN_PROGRESS,
            total_marks=self.exam.total_marks,
        )
        started_at = timezone.now() - timedelta(minutes=120)
        ExamAttempt.objects.filter(pk=attempt.pk).update(started_at=started_at)
        attempt.refresh_from_db()
        return attempt

    def test_soft_time_limit_exceeded_reraises(self):
        """SoftTimeLimitExceeded is re-raised, NOT retried."""
        self._create_timed_out_attempt()
        with (
            patch(
                "apps.exams.tasks.ExamService._score_timed_out_attempt",
                side_effect=SoftTimeLimitExceeded(),
            ),
            self.assertRaises(SoftTimeLimitExceeded),
        ):
            auto_submit_timed_out_exams()

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    def test_generic_exception_triggers_retry(self):
        """Generic Exception during processing triggers self.retry()."""
        call_count = 0

        def failing_filter(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("DB connection lost")

        with patch(
            "apps.exams.tasks.ExamAttempt.objects",
        ) as mock_objects:
            mock_objects.filter.side_effect = failing_filter
            result = auto_submit_timed_out_exams.apply()
            self.assertEqual(result.state, "FAILURE")
            # Called once initially + HEAVY_MAX_RETRIES retries
            self.assertEqual(call_count, HEAVY_EXPECTED_TOTAL_CALLS)

    def test_does_not_exist_during_select_for_update_skips(self):
        """
        If the attempt is manually submitted between the initial query
        and the select_for_update lock, DoesNotExist is caught and
        the attempt is skipped (count stays 0).
        """
        self._create_timed_out_attempt()

        with patch("apps.exams.tasks.ExamAttempt.objects.select_for_update") as mock_sfu:
            mock_qs = mock_sfu.return_value
            mock_qs.select_related.return_value.get.side_effect = ExamAttempt.DoesNotExist()

            count = auto_submit_timed_out_exams()
            self.assertEqual(count, 0)

    def test_success_path_returns_count(self):
        """Successful auto-submit returns count of submitted attempts."""
        self._create_timed_out_attempt()
        count = auto_submit_timed_out_exams()
        self.assertEqual(count, 1)

    def test_no_timed_out_attempts_returns_zero(self):
        """When no attempts are timed out, returns 0."""
        count = auto_submit_timed_out_exams()
        self.assertEqual(count, 0)
