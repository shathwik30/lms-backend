"""Tests for custom exception classes."""

from django.test import TestCase
from rest_framework.exceptions import APIException

from core.exceptions import (
    FinalExamAttemptsExhausted,
    LevelExpired,
    LevelLocked,
    OnboardingAlreadyAttempted,
    PurchaseRequired,
    SessionNotAccessible,
    SyllabusIncomplete,
)


class ExceptionTests(TestCase):
    def test_level_locked(self):
        exc = LevelLocked()
        self.assertEqual(exc.status_code, 403)
        self.assertIn("prerequisite", str(exc.detail))
        self.assertIsInstance(exc, APIException)

    def test_syllabus_incomplete(self):
        exc = SyllabusIncomplete()
        self.assertEqual(exc.status_code, 403)
        self.assertIn("syllabus", str(exc.detail))

    def test_level_expired(self):
        exc = LevelExpired()
        self.assertEqual(exc.status_code, 403)
        self.assertIn("expired", str(exc.detail))

    def test_purchase_required(self):
        exc = PurchaseRequired()
        self.assertEqual(exc.status_code, 402)
        self.assertIn("purchase", str(exc.detail))

    def test_onboarding_already_attempted(self):
        exc = OnboardingAlreadyAttempted()
        self.assertEqual(exc.status_code, 403)
        self.assertIn("placement test", str(exc.detail))

    def test_final_exam_attempts_exhausted(self):
        exc = FinalExamAttemptsExhausted()
        self.assertEqual(exc.status_code, 403)
        self.assertIn("attempts", str(exc.detail))

    def test_session_not_accessible(self):
        exc = SessionNotAccessible()
        self.assertEqual(exc.status_code, 403)
        self.assertIn("prior sessions", str(exc.detail).lower())

    def test_all_have_default_code(self):
        exceptions = [
            LevelLocked,
            SyllabusIncomplete,
            LevelExpired,
            PurchaseRequired,
            OnboardingAlreadyAttempted,
            FinalExamAttemptsExhausted,
            SessionNotAccessible,
        ]
        for exc_class in exceptions:
            exc = exc_class()
            self.assertTrue(exc.default_code, f"{exc_class.__name__} missing default_code")
