from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from apps.exams.models import ExamAttempt, ProctoringViolation
from core.test_utils import TestFactory

ADMIN_ATTEMPTS_URL = "/api/v1/exams/admin/attempts/"


def _stats_url(exam_pk):
    return f"/api/v1/exams/admin/{exam_pk}/stats/"


class AdminAttemptListViewTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=3)

    def test_list_includes_student_name(self):
        ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=8,
            is_passed=False,
            submitted_at=timezone.now(),
        )
        response = self.admin_client.get(ADMIN_ATTEMPTS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("student_name", response.data["results"][0])
        self.assertEqual(response.data["results"][0]["student_name"], self.user.full_name)

    def test_list_includes_violations_count(self):
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=10,
            is_passed=True,
            submitted_at=timezone.now(),
        )
        ProctoringViolation.objects.create(
            attempt=attempt,
            violation_type="tab_switch",
            warning_number=1,
        )
        ProctoringViolation.objects.create(
            attempt=attempt,
            violation_type="full_screen_exit",
            warning_number=2,
        )
        response = self.admin_client.get(ADMIN_ATTEMPTS_URL)
        self.assertEqual(response.data["results"][0]["violations_count"], 2)

    def test_list_violations_count_zero(self):
        ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=10,
            is_passed=True,
            submitted_at=timezone.now(),
        )
        response = self.admin_client.get(ADMIN_ATTEMPTS_URL)
        self.assertEqual(response.data["results"][0]["violations_count"], 0)

    def test_list_includes_attempt_number(self):
        ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=5,
            is_passed=False,
            submitted_at=timezone.now(),
        )
        ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=10,
            is_passed=True,
            submitted_at=timezone.now(),
        )
        response = self.admin_client.get(ADMIN_ATTEMPTS_URL)
        # Most recent attempt first (order_by -started_at)
        numbers = [r["attempt_number"] for r in response.data["results"]]
        self.assertIn(1, numbers)
        self.assertIn(2, numbers)

    def test_student_cannot_access_admin_attempts(self):
        student_client = self.factory.get_auth_client(self.user)
        response = student_client.get(ADMIN_ATTEMPTS_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminExamStatsViewTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=3)

    def test_stats_endpoint_returns_correct_data(self):
        exam = self.data["exam"]
        ExamAttempt.objects.create(
            student=self.profile,
            exam=exam,
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=10,
            is_passed=True,
            submitted_at=timezone.now(),
        )
        user2, profile2 = self.factory.create_student(email="s2@test.com")
        ExamAttempt.objects.create(
            student=profile2,
            exam=exam,
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=3,
            is_passed=False,
            submitted_at=timezone.now(),
        )
        response = self.admin_client.get(_stats_url(exam.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_attempts"], 2)
        self.assertIsNotNone(response.data["pass_rate"])
        self.assertEqual(response.data["pass_rate"], 50.0)

    def test_stats_pass_rate_null_with_no_attempts(self):
        exam = self.data["exam"]
        response = self.admin_client.get(_stats_url(exam.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["pass_rate"])
        self.assertEqual(response.data["total_attempts"], 0)

    def test_stats_average_score(self):
        exam = self.data["exam"]
        ExamAttempt.objects.create(
            student=self.profile,
            exam=exam,
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=10,
            is_passed=True,
            submitted_at=timezone.now(),
        )
        user2, profile2 = self.factory.create_student(email="s2@test.com")
        ExamAttempt.objects.create(
            student=profile2,
            exam=exam,
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=6,
            is_passed=False,
            submitted_at=timezone.now(),
        )
        response = self.admin_client.get(_stats_url(exam.pk))
        self.assertEqual(response.data["average_score"], 8.0)

    def test_stats_total_violations(self):
        exam = self.data["exam"]
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=exam,
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=10,
            is_passed=True,
            submitted_at=timezone.now(),
        )
        ProctoringViolation.objects.create(
            attempt=attempt,
            violation_type="tab_switch",
            warning_number=1,
        )
        ProctoringViolation.objects.create(
            attempt=attempt,
            violation_type="tab_switch",
            warning_number=2,
        )
        ProctoringViolation.objects.create(
            attempt=attempt,
            violation_type="full_screen_exit",
            warning_number=3,
        )
        response = self.admin_client.get(_stats_url(exam.pk))
        self.assertEqual(response.data["total_violations"], 3)

    def test_stats_404_for_invalid_exam(self):
        response = self.admin_client.get(_stats_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_cannot_access_stats(self):
        student_client = self.factory.get_auth_client(self.user)
        response = student_client.get(_stats_url(self.data["exam"].pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
