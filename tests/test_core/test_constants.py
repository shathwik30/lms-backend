"""Tests for core constants, enums, and message formatters."""

from django.test import TestCase

from core.constants import (
    CertificateConstants,
    ErrorMessage,
    ExamConstants,
    HealthCheckConstants,
    HealthStatus,
    NextAction,
    NextActionMessage,
    PaymentConstants,
    ProgressConstants,
    SearchConstants,
    SuccessMessage,
    TaskConfig,
)


class NextActionEnumTests(TestCase):
    def test_all_values(self):
        self.assertEqual(NextAction.TAKE_ONBOARDING_EXAM, "take_onboarding_exam")
        self.assertEqual(NextAction.PURCHASE_LEVEL, "purchase_level")
        self.assertEqual(NextAction.COMPLETE_COURSES, "complete_courses")
        self.assertEqual(NextAction.TAKE_FINAL_EXAM, "take_final_exam")
        self.assertEqual(NextAction.REDO_LEVEL, "redo_level")
        self.assertEqual(NextAction.ALL_COMPLETE, "all_complete")
        self.assertEqual(NextAction.NO_LEVELS, "no_levels")

    def test_is_string_enum(self):
        self.assertIsInstance(NextAction.TAKE_ONBOARDING_EXAM, str)


class NextActionMessageTests(TestCase):
    def test_all_complete(self):
        self.assertIn("Congratulations", NextActionMessage.ALL_COMPLETE)

    def test_no_levels(self):
        self.assertIn("No levels", NextActionMessage.NO_LEVELS)

    def test_take_onboarding(self):
        msg = NextActionMessage.take_onboarding()
        self.assertIn("placement test", msg)

    def test_purchase_level(self):
        msg = NextActionMessage.purchase_level(3)
        self.assertIn("Level 3", msg)

    def test_complete_courses(self):
        msg = NextActionMessage.complete_courses(2)
        self.assertIn("Level 2", msg)

    def test_take_final_exam(self):
        msg = NextActionMessage.take_final_exam(1)
        self.assertIn("Level 1", msg)
        self.assertIn("final exam", msg)

    def test_redo_level(self):
        msg = NextActionMessage.redo_level(5)
        self.assertIn("Level 5", msg)
        self.assertIn("Redo", msg)


class ErrorMessageTests(TestCase):
    def test_all_messages_are_strings(self):
        for attr in dir(ErrorMessage):
            if attr.startswith("_"):
                continue
            val = getattr(ErrorMessage, attr)
            if isinstance(val, str):
                self.assertTrue(len(val) > 0, f"Empty message: {attr}")

    def test_key_messages_exist(self):
        self.assertTrue(ErrorMessage.NOT_FOUND)
        self.assertTrue(ErrorMessage.ACTIVE_LEVEL_PURCHASE_EXISTS)
        self.assertTrue(ErrorMessage.PAYMENT_VERIFICATION_FAILED)
        self.assertTrue(ErrorMessage.ONBOARDING_ALREADY_ATTEMPTED)
        self.assertTrue(ErrorMessage.FINAL_EXAM_ATTEMPTS_EXHAUSTED)
        self.assertTrue(ErrorMessage.SESSION_NOT_ACCESSIBLE)
        self.assertTrue(ErrorMessage.EXAM_NOT_PROCTORED)
        self.assertTrue(ErrorMessage.AMOUNT_MISMATCH)
        self.assertTrue(ErrorMessage.LEVEL_NOT_LINKED)


class SuccessMessageTests(TestCase):
    def test_key_messages_exist(self):
        self.assertTrue(SuccessMessage.LOGGED_OUT)
        self.assertTrue(SuccessMessage.PASSWORD_CHANGED)
        self.assertTrue(SuccessMessage.RESOURCE_SESSION_COMPLETED)


class ConstantValuesTests(TestCase):
    def test_payment_constants(self):
        self.assertEqual(PaymentConstants.DEFAULT_CURRENCY, "INR")

    def test_progress_constants(self):
        self.assertEqual(ProgressConstants.SESSION_COMPLETION_THRESHOLD, 0.9)
        self.assertEqual(ProgressConstants.DEFAULT_LEADERBOARD_LIMIT, 20)
        self.assertEqual(ProgressConstants.MAX_LEADERBOARD_LIMIT, 50)

    def test_search_constants(self):
        self.assertEqual(SearchConstants.MIN_QUERY_LENGTH, 2)

    def test_exam_constants(self):
        self.assertEqual(ExamConstants.SUBMISSION_GRACE_SECONDS, 30)
        self.assertEqual(ExamConstants.PERCENTAGE_DIVISOR, 100)

    def test_task_config(self):
        self.assertEqual(TaskConfig.EMAIL_MAX_RETRIES, 3)
        self.assertGreater(TaskConfig.HEAVY_SOFT_TIME_LIMIT, TaskConfig.EMAIL_SOFT_TIME_LIMIT)

    def test_health_check_constants(self):
        self.assertEqual(HealthCheckConstants.CACHE_KEY, "_health_check")
        self.assertEqual(HealthCheckConstants.CACHE_VALUE, "ok")

    def test_health_status_enum(self):
        self.assertEqual(HealthStatus.HEALTHY, "healthy")
        self.assertEqual(HealthStatus.DEGRADED, "degraded")

    def test_certificate_constants(self):
        self.assertEqual(CertificateConstants.NUMBER_PREFIX, "CERT-")
