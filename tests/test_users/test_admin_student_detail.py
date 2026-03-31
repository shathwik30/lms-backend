from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from apps.exams.models import ExamAttempt
from core.test_utils import TestFactory

ADMIN_STUDENT_DETAIL_URL = "/api/v1/auth/admin/students/"


def _detail_url(pk):
    return f"{ADMIN_STUDENT_DETAIL_URL}{pk}/"


class AdminStudentDetailGetTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=3)

    def test_detail_includes_account_status_active(self):
        response = self.admin_client.get(_detail_url(self.profile.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["account_status"], "active")

    def test_detail_includes_account_status_inactive(self):
        self.user.is_active = False
        self.user.save()
        response = self.admin_client.get(_detail_url(self.profile.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["account_status"], "inactive")

    def test_detail_includes_validity_till(self):
        self.factory.create_purchase(self.profile, self.data["level"])
        response = self.admin_client.get(_detail_url(self.profile.pk))
        self.assertIsNotNone(response.data["validity_till"])

    def test_detail_validity_null_without_purchase(self):
        response = self.admin_client.get(_detail_url(self.profile.pk))
        self.assertIsNone(response.data["validity_till"])

    def test_detail_includes_days_remaining(self):
        self.factory.create_purchase(self.profile, self.data["level"], days_valid=30)
        response = self.admin_client.get(_detail_url(self.profile.pk))
        self.assertIsNotNone(response.data["days_remaining"])
        # Should be roughly 29-30 days
        self.assertGreaterEqual(response.data["days_remaining"], 28)
        self.assertLessEqual(response.data["days_remaining"], 30)

    def test_detail_days_remaining_zero_when_expired(self):
        self.factory.create_expired_purchase(self.profile, self.data["level"])
        response = self.admin_client.get(_detail_url(self.profile.pk))
        self.assertEqual(response.data["days_remaining"], 0)

    def test_detail_includes_curriculum_progress(self):
        self.profile.current_level = self.data["level"]
        self.profile.save()
        # Complete one of the sessions
        self.factory.complete_session(self.profile, self.data["sessions"][0])
        response = self.admin_client.get(_detail_url(self.profile.pk))
        progress = response.data["curriculum_progress"]
        self.assertIsNotNone(progress)
        self.assertIn("overall_completion", progress)
        self.assertIn("video_completion", progress)
        self.assertIn("practice_completion", progress)
        self.assertIn("feedback_submitted", progress)
        self.assertGreater(progress["overall_completion"], 0)

    def test_detail_curriculum_progress_null_without_level(self):
        # Ensure current_level is None
        self.profile.current_level = None
        self.profile.save()
        response = self.admin_client.get(_detail_url(self.profile.pk))
        self.assertIsNone(response.data["curriculum_progress"])

    def test_detail_includes_exam_history(self):
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
        response = self.admin_client.get(_detail_url(self.profile.pk))
        history = response.data["exam_history"]
        self.assertIsInstance(history, list)
        self.assertEqual(len(history), 1)
        self.assertIn("exam_title", history[0])
        self.assertIn("score", history[0])
        self.assertIn("is_passed", history[0])

    def test_detail_exam_history_attempt_number(self):
        exam = self.data["exam"]
        ExamAttempt.objects.create(
            student=self.profile,
            exam=exam,
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=5,
            is_passed=False,
            submitted_at=timezone.now(),
        )
        ExamAttempt.objects.create(
            student=self.profile,
            exam=exam,
            total_marks=12,
            status=ExamAttempt.Status.SUBMITTED,
            score=10,
            is_passed=True,
            submitted_at=timezone.now(),
        )
        response = self.admin_client.get(_detail_url(self.profile.pk))
        history = response.data["exam_history"]
        self.assertEqual(len(history), 2)
        numbers = [h["attempt_number"] for h in history]
        self.assertIn(1, numbers)
        self.assertIn(2, numbers)

    def test_patch_still_works(self):
        level = self.data["level"]
        response = self.admin_client.patch(
            _detail_url(self.profile.pk),
            data={"current_level": level.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_level_id, level.pk)
