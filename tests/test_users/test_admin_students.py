from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.exams.models import ExamAttempt
from apps.progress.models import SessionProgress
from core.test_utils import TestFactory

ADMIN_STUDENTS_URL = "/api/v1/auth/admin/students/"


class AdminStudentEnrichedFieldsTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=3)

    def test_response_has_all_enriched_fields(self):
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student = response.data["results"][0]
        for field in ["validity_till", "exam_status", "streak", "last_active", "account_status"]:
            self.assertIn(field, student, f"Missing field: {field}")

    def test_account_status_active(self):
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertEqual(student["account_status"], "active")

    def test_account_status_inactive(self):
        self.user.is_active = False
        self.user.save()
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertEqual(student["account_status"], "inactive")

    def test_validity_till_with_purchase(self):
        self.factory.create_purchase(self.profile, self.data["level"])
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertIsNotNone(student["validity_till"])

    def test_validity_till_without_purchase(self):
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertIsNone(student["validity_till"])

    def test_exam_status_not_attempted(self):
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertEqual(student["exam_status"], "not_attempted")

    def test_exam_status_passed(self):
        ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
            status=ExamAttempt.Status.SUBMITTED,
            is_passed=True,
            score=15,
            submitted_at=timezone.now(),
        )
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertEqual(student["exam_status"], "passed")

    def test_exam_status_failed(self):
        ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
            status=ExamAttempt.Status.SUBMITTED,
            is_passed=False,
            score=5,
            submitted_at=timezone.now(),
        )
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertEqual(student["exam_status"], "failed")

    def test_exam_status_in_progress(self):
        ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
            status=ExamAttempt.Status.IN_PROGRESS,
        )
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertEqual(student["exam_status"], "in_progress")

    def test_last_active_with_progress(self):
        session = self.data["sessions"][0]
        self.factory.complete_session(self.profile, session)
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertIsNotNone(student["last_active"])

    def test_last_active_without_progress(self):
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertIsNone(student["last_active"])

    def test_streak_zero_without_activity(self):
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertEqual(student["streak"], 0)

    def test_streak_with_today_activity(self):
        session = self.data["sessions"][0]
        SessionProgress.objects.create(
            student=self.profile,
            session=session,
            watched_seconds=100,
        )
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertEqual(student["streak"], 1)

    def test_streak_consecutive_days(self):
        sessions = self.data["sessions"]
        # Create progress for today
        SessionProgress.objects.create(
            student=self.profile,
            session=sessions[0],
            watched_seconds=100,
        )
        # Create progress for yesterday
        sp2 = SessionProgress.objects.create(
            student=self.profile,
            session=sessions[1],
            watched_seconds=100,
        )
        SessionProgress.objects.filter(pk=sp2.pk).update(updated_at=timezone.now() - timedelta(days=1))
        response = self.admin_client.get(ADMIN_STUDENTS_URL)
        student = response.data["results"][0]
        self.assertEqual(student["streak"], 2)
