from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from apps.exams.models import ExamAttempt
from apps.progress.models import CourseProgress, LevelProgress
from core.test_utils import TestFactory


def _detail_url(level_pk):
    return f"/api/v1/analytics/levels/{level_pk}/detail/"


class AdminLevelAnalyticsDetailTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=3)

    def test_returns_all_fields(self):
        response = self.admin_client.get(_detail_url(self.data["level"].pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in [
            "level_id",
            "level_name",
            "students_enrolled",
            "completion_rate",
            "exam_pass_rate",
            "average_score",
            "student_activity",
            "module_completion_rate",
        ]:
            self.assertIn(key, response.data, f"Missing key: {key}")

    def test_students_enrolled(self):
        level = self.data["level"]
        self.factory.create_purchase(self.profile, level)
        user2, profile2 = self.factory.create_student(email="s2@test.com")
        self.factory.create_purchase(profile2, level)
        response = self.admin_client.get(_detail_url(level.pk))
        self.assertEqual(response.data["students_enrolled"], 2)

    def test_completion_rate(self):
        level = self.data["level"]
        # 2 students with level progress, 1 passed
        LevelProgress.objects.create(
            student=self.profile,
            level=level,
            status=LevelProgress.Status.EXAM_PASSED,
            completed_at=timezone.now(),
        )
        user2, profile2 = self.factory.create_student(email="s2@test.com")
        LevelProgress.objects.create(
            student=profile2,
            level=level,
            status=LevelProgress.Status.IN_PROGRESS,
        )
        response = self.admin_client.get(_detail_url(level.pk))
        self.assertEqual(response.data["completion_rate"], 50.0)

    def test_completion_rate_null_with_no_students(self):
        response = self.admin_client.get(_detail_url(self.data["level"].pk))
        self.assertIsNone(response.data["completion_rate"])

    def test_exam_pass_rate(self):
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
        response = self.admin_client.get(_detail_url(self.data["level"].pk))
        self.assertEqual(response.data["exam_pass_rate"], 50.0)

    def test_average_score(self):
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
        response = self.admin_client.get(_detail_url(self.data["level"].pk))
        self.assertEqual(response.data["average_score"], 8.0)

    def test_student_activity_default_30_days(self):
        level = self.data["level"]
        session = self.data["sessions"][0]
        self.factory.complete_session(self.profile, session)
        response = self.admin_client.get(_detail_url(level.pk))
        activity = response.data["student_activity"]
        self.assertIsInstance(activity, list)
        self.assertGreaterEqual(len(activity), 1)
        entry = activity[0]
        self.assertIn("date", entry)
        self.assertIn("active_students", entry)

    def test_student_activity_custom_days(self):
        level = self.data["level"]
        session = self.data["sessions"][0]
        self.factory.complete_session(self.profile, session)
        response = self.admin_client.get(_detail_url(level.pk) + "?days=7")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        activity = response.data["student_activity"]
        self.assertIsInstance(activity, list)

    def test_module_completion_rate(self):
        level = self.data["level"]
        course = self.data["course"]
        # Create course progress for 2 students, 1 completed
        CourseProgress.objects.create(
            student=self.profile,
            course=course,
            status=CourseProgress.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        user2, profile2 = self.factory.create_student(email="s2@test.com")
        CourseProgress.objects.create(
            student=profile2,
            course=course,
            status=CourseProgress.Status.IN_PROGRESS,
        )
        response = self.admin_client.get(_detail_url(level.pk))
        modules = response.data["module_completion_rate"]
        self.assertIsInstance(modules, list)
        self.assertGreaterEqual(len(modules), 1)
        mod = modules[0]
        self.assertIn("course_id", mod)
        self.assertIn("course_title", mod)
        self.assertIn("completion_rate", mod)
        self.assertIn("total_students", mod)
        self.assertIn("completed_students", mod)
        self.assertEqual(mod["total_students"], 2)
        self.assertEqual(mod["completed_students"], 1)
        self.assertEqual(mod["completion_rate"], 50.0)

    def test_404_for_invalid_level(self):
        response = self.admin_client.get(_detail_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_forbidden(self):
        student_client = self.factory.get_auth_client(self.user)
        response = student_client.get(_detail_url(self.data["level"].pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
