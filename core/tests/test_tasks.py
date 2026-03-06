from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from core.tasks import (
    send_doubt_reply_task,
    send_exam_result_task,
    send_purchase_confirmation_task,
    send_welcome_email_task,
)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class EmailTaskTests(TestCase):
    def test_welcome_email_task_sends_email(self):
        send_welcome_email_task("user@test.com", "Test User")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("user@test.com", mail.outbox[0].to)

    def test_purchase_confirmation_task_sends_email(self):
        send_purchase_confirmation_task(
            "user@test.com",
            "Test User",
            "Level 1 Course",
            "999.00",
            "2026-06-01T00:00:00",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("user@test.com", mail.outbox[0].to)

    def test_exam_result_task_sends_email(self):
        send_exam_result_task(
            "user@test.com",
            "Test User",
            "Level 1 Exam",
            15,
            20,
            True,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("user@test.com", mail.outbox[0].to)

    def test_doubt_reply_task_sends_email(self):
        send_doubt_reply_task(
            "user@test.com",
            "Test User",
            "Calculus Doubt",
            "Admin",
            "Here is the solution...",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("user@test.com", mail.outbox[0].to)

    def test_welcome_email_contains_name(self):
        send_welcome_email_task("user@test.com", "John Doe")
        self.assertIn("John Doe", mail.outbox[0].body)

    def test_exam_result_email_contains_score(self):
        send_exam_result_task(
            "user@test.com",
            "Test User",
            "Final Exam",
            18,
            20,
            True,
        )
        self.assertIn("18", mail.outbox[0].body)

    @patch("core.emails.EmailService.send_welcome")
    def test_welcome_task_calls_service(self, mock_send):
        send_welcome_email_task("user@test.com", "Test User")
        mock_send.assert_called_once_with("user@test.com", "Test User")

    @patch("core.emails.EmailService.send_doubt_reply")
    def test_doubt_reply_task_calls_service(self, mock_send):
        send_doubt_reply_task(
            "user@test.com",
            "Test User",
            "My Doubt",
            "Admin",
            "Reply text",
        )
        mock_send.assert_called_once_with(
            "user@test.com",
            "Test User",
            "My Doubt",
            "Admin",
            "Reply text",
        )
