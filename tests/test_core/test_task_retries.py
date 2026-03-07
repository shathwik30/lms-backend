"""
Tests for retry logic and error handling in all Celery email tasks from core/tasks.py.

Each task follows the same pattern:
  - Success: EmailService.send_X(...) is called, no exception
  - SoftTimeLimitExceeded: re-raised (not retried)
  - SMTPException / ConnectionError / OSError: triggers self.retry()

For retry tests we use CELERY_TASK_EAGER_PROPAGATES=False so that exhausted
retries result in FAILURE state rather than propagating the exception directly.
We verify that the mock was called max_retries+1 times (initial + retries),
which proves self.retry() was invoked.
"""

import smtplib
from unittest.mock import patch

from celery.exceptions import SoftTimeLimitExceeded
from django.test import TestCase, override_settings

from core.constants import TaskConfig
from core.tasks import (
    send_doubt_reply_task,
    send_exam_result_task,
    send_password_reset_task,
    send_purchase_confirmation_task,
    send_welcome_email_task,
)

# Each email task retries EMAIL_MAX_RETRIES times, so the mock is called
# 1 (initial) + EMAIL_MAX_RETRIES (retries) = total calls
EXPECTED_TOTAL_CALLS = TaskConfig.EMAIL_MAX_RETRIES + 1


def _assert_task_retried(test_case, result, mock_send):
    """Assert that an eager task exhausted retries and the service was called repeatedly."""
    test_case.assertEqual(result.state, "FAILURE")
    test_case.assertEqual(mock_send.call_count, EXPECTED_TOTAL_CALLS)


# ── Welcome Email ──


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class WelcomeEmailTaskRetryTests(TestCase):
    """Retry tests for send_welcome_email_task."""

    @patch("core.emails.EmailService.send_welcome")
    def test_success_path(self, mock_send):
        """Email sent successfully, no exception raised."""
        send_welcome_email_task("user@test.com", "Test User")
        mock_send.assert_called_once_with("user@test.com", "Test User")

    @patch("core.emails.EmailService.send_welcome", side_effect=SoftTimeLimitExceeded())
    def test_soft_time_limit_exceeded_reraises(self, mock_send):
        """SoftTimeLimitExceeded is re-raised, NOT retried (only called once)."""
        with self.assertRaises(SoftTimeLimitExceeded):
            send_welcome_email_task("user@test.com", "Test User")
        mock_send.assert_called_once()

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch("core.emails.EmailService.send_welcome", side_effect=smtplib.SMTPException("SMTP error"))
    def test_smtp_exception_triggers_retry(self, mock_send):
        """SMTPException triggers self.retry() -- mock called max_retries+1 times."""
        result = send_welcome_email_task.apply(args=["user@test.com", "Test User"])
        _assert_task_retried(self, result, mock_send)

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch("core.emails.EmailService.send_welcome", side_effect=ConnectionError("connection refused"))
    def test_connection_error_triggers_retry(self, mock_send):
        """ConnectionError triggers self.retry()."""
        result = send_welcome_email_task.apply(args=["user@test.com", "Test User"])
        _assert_task_retried(self, result, mock_send)

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch("core.emails.EmailService.send_welcome", side_effect=OSError("OS level error"))
    def test_os_error_triggers_retry(self, mock_send):
        """OSError triggers self.retry()."""
        result = send_welcome_email_task.apply(args=["user@test.com", "Test User"])
        _assert_task_retried(self, result, mock_send)


# ── Purchase Confirmation ──


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PurchaseConfirmationTaskRetryTests(TestCase):
    """Retry tests for send_purchase_confirmation_task."""

    ARGS = [
        "user@test.com",
        "Test User",
        "Level 1",
        "999.00",
        "2026-06-01T00:00:00",
    ]

    @patch("core.emails.EmailService.send_purchase_confirmation")
    def test_success_path(self, mock_send):
        send_purchase_confirmation_task(*self.ARGS)
        mock_send.assert_called_once()

    @patch(
        "core.emails.EmailService.send_purchase_confirmation",
        side_effect=SoftTimeLimitExceeded(),
    )
    def test_soft_time_limit_exceeded_reraises(self, mock_send):
        with self.assertRaises(SoftTimeLimitExceeded):
            send_purchase_confirmation_task(*self.ARGS)
        mock_send.assert_called_once()

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch(
        "core.emails.EmailService.send_purchase_confirmation",
        side_effect=smtplib.SMTPException("SMTP error"),
    )
    def test_smtp_exception_triggers_retry(self, mock_send):
        result = send_purchase_confirmation_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch(
        "core.emails.EmailService.send_purchase_confirmation",
        side_effect=ConnectionError("refused"),
    )
    def test_connection_error_triggers_retry(self, mock_send):
        result = send_purchase_confirmation_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch(
        "core.emails.EmailService.send_purchase_confirmation",
        side_effect=OSError("write error"),
    )
    def test_os_error_triggers_retry(self, mock_send):
        result = send_purchase_confirmation_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)


# ── Exam Result ──


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class ExamResultTaskRetryTests(TestCase):
    """Retry tests for send_exam_result_task."""

    ARGS = ["user@test.com", "Test User", "Final Exam", 18, 20, True]

    @patch("core.emails.EmailService.send_exam_result")
    def test_success_path(self, mock_send):
        send_exam_result_task(*self.ARGS)
        mock_send.assert_called_once_with(*self.ARGS)

    @patch("core.emails.EmailService.send_exam_result", side_effect=SoftTimeLimitExceeded())
    def test_soft_time_limit_exceeded_reraises(self, mock_send):
        with self.assertRaises(SoftTimeLimitExceeded):
            send_exam_result_task(*self.ARGS)
        mock_send.assert_called_once()

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch(
        "core.emails.EmailService.send_exam_result",
        side_effect=smtplib.SMTPException("SMTP error"),
    )
    def test_smtp_exception_triggers_retry(self, mock_send):
        result = send_exam_result_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch(
        "core.emails.EmailService.send_exam_result",
        side_effect=ConnectionError("refused"),
    )
    def test_connection_error_triggers_retry(self, mock_send):
        result = send_exam_result_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch("core.emails.EmailService.send_exam_result", side_effect=OSError("disk error"))
    def test_os_error_triggers_retry(self, mock_send):
        result = send_exam_result_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)


# ── Password Reset ──


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PasswordResetTaskRetryTests(TestCase):
    """Retry tests for send_password_reset_task."""

    ARGS = ["user@test.com", "Test User", "https://example.com/reset/abc123"]

    @patch("core.emails.EmailService.send_password_reset")
    def test_success_path(self, mock_send):
        send_password_reset_task(*self.ARGS)
        mock_send.assert_called_once_with(*self.ARGS)

    @patch("core.emails.EmailService.send_password_reset", side_effect=SoftTimeLimitExceeded())
    def test_soft_time_limit_exceeded_reraises(self, mock_send):
        with self.assertRaises(SoftTimeLimitExceeded):
            send_password_reset_task(*self.ARGS)
        mock_send.assert_called_once()

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch(
        "core.emails.EmailService.send_password_reset",
        side_effect=smtplib.SMTPException("SMTP error"),
    )
    def test_smtp_exception_triggers_retry(self, mock_send):
        result = send_password_reset_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch(
        "core.emails.EmailService.send_password_reset",
        side_effect=ConnectionError("refused"),
    )
    def test_connection_error_triggers_retry(self, mock_send):
        result = send_password_reset_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch("core.emails.EmailService.send_password_reset", side_effect=OSError("OS error"))
    def test_os_error_triggers_retry(self, mock_send):
        result = send_password_reset_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)


# ── Doubt Reply ──


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class DoubtReplyTaskRetryTests(TestCase):
    """Retry tests for send_doubt_reply_task."""

    ARGS = ["user@test.com", "Test User", "Calculus Doubt", "Admin", "Here is the solution..."]

    @patch("core.emails.EmailService.send_doubt_reply")
    def test_success_path(self, mock_send):
        send_doubt_reply_task(*self.ARGS)
        mock_send.assert_called_once_with(*self.ARGS)

    @patch("core.emails.EmailService.send_doubt_reply", side_effect=SoftTimeLimitExceeded())
    def test_soft_time_limit_exceeded_reraises(self, mock_send):
        with self.assertRaises(SoftTimeLimitExceeded):
            send_doubt_reply_task(*self.ARGS)
        mock_send.assert_called_once()

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch(
        "core.emails.EmailService.send_doubt_reply",
        side_effect=smtplib.SMTPException("SMTP error"),
    )
    def test_smtp_exception_triggers_retry(self, mock_send):
        result = send_doubt_reply_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch(
        "core.emails.EmailService.send_doubt_reply",
        side_effect=ConnectionError("refused"),
    )
    def test_connection_error_triggers_retry(self, mock_send):
        result = send_doubt_reply_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @patch("core.emails.EmailService.send_doubt_reply", side_effect=OSError("write error"))
    def test_os_error_triggers_retry(self, mock_send):
        result = send_doubt_reply_task.apply(args=self.ARGS)
        _assert_task_retried(self, result, mock_send)
