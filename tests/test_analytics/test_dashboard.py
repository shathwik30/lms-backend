from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.doubts.models import DoubtTicket
from apps.exams.models import ExamAttempt
from apps.progress.models import SessionProgress
from core.test_utils import TestFactory

DASHBOARD_URL = "/api/v1/analytics/dashboard/"


class AdminDashboardTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.data = self.factory.setup_full_level(order=1, num_questions=5)
        self.user, self.profile = self.factory.create_student()
        self.factory.create_purchase(self.profile, self.data["level"])

    def test_dashboard_returns_all_fields(self):
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in [
            "total_students",
            "total_revenue",
            "active_users",
            "exams_passed_today",
            "open_doubts",
            "recent_doubts",
            "daily_active_users",
            "streak_retention",
        ]:
            self.assertIn(key, response.data, f"Missing key: {key}")

    def test_total_students_count(self):
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.data["total_students"], 1)

    def test_total_revenue(self):
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertGreater(float(response.data["total_revenue"]), 0)

    def test_active_users_with_recent_activity(self):
        session = self.data["sessions"][0]
        self.factory.complete_session(self.profile, session)
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.data["active_users"], 1)

    def test_active_users_excludes_old_activity(self):
        session = self.data["sessions"][0]
        sp = SessionProgress.objects.create(
            student=self.profile,
            session=session,
            watched_seconds=100,
            is_completed=False,
        )
        # Backdate to 10 days ago
        SessionProgress.objects.filter(pk=sp.pk).update(updated_at=timezone.now() - timedelta(days=10))
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.data["active_users"], 0)

    def test_exams_passed_today(self):
        ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
            status=ExamAttempt.Status.SUBMITTED,
            is_passed=True,
            score=15,
            submitted_at=timezone.now(),
        )
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.data["exams_passed_today"], 1)

    def test_exams_passed_yesterday_not_counted(self):
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
            status=ExamAttempt.Status.SUBMITTED,
            is_passed=True,
            score=15,
        )
        ExamAttempt.objects.filter(pk=attempt.pk).update(submitted_at=timezone.now() - timedelta(days=1))
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.data["exams_passed_today"], 0)

    def test_open_doubts_count(self):
        DoubtTicket.objects.create(
            student=self.profile,
            title="Test doubt",
            description="desc",
            context_type="topic",
            status="open",
        )
        DoubtTicket.objects.create(
            student=self.profile,
            title="Closed doubt",
            description="desc",
            context_type="topic",
            status="closed",
        )
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.data["open_doubts"], 1)

    def test_recent_doubts_returns_latest(self):
        DoubtTicket.objects.create(
            student=self.profile,
            title="Recent doubt",
            description="desc",
            context_type="topic",
        )
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(len(response.data["recent_doubts"]), 1)
        self.assertEqual(response.data["recent_doubts"][0]["title"], "Recent doubt")
        self.assertIn("student_name", response.data["recent_doubts"][0])

    def test_daily_active_users_graph_data(self):
        session = self.data["sessions"][0]
        self.factory.complete_session(self.profile, session)
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertIsInstance(response.data["daily_active_users"], list)
        if response.data["daily_active_users"]:
            entry = response.data["daily_active_users"][0]
            self.assertIn("date", entry)
            self.assertIn("count", entry)

    def test_streak_retention_buckets(self):
        response = self.admin_client.get(DASHBOARD_URL)
        sr = response.data["streak_retention"]
        self.assertIn("0_days", sr)
        self.assertIn("1_3_days", sr)
        self.assertIn("4_7_days", sr)
        self.assertIn("8_plus_days", sr)
        # Total should equal total students
        total = sr["0_days"] + sr["1_3_days"] + sr["4_7_days"] + sr["8_plus_days"]
        self.assertEqual(total, response.data["total_students"])

    def test_streak_retention_with_active_streak(self):
        session = self.data["sessions"][0]
        sp = SessionProgress.objects.create(
            student=self.profile,
            session=session,
            watched_seconds=100,
            is_completed=True,
            completed_at=timezone.now(),
        )
        # Ensure today's date is the activity date
        SessionProgress.objects.filter(pk=sp.pk).update(updated_at=timezone.now())
        response = self.admin_client.get(DASHBOARD_URL)
        sr = response.data["streak_retention"]
        self.assertGreater(sr["1_3_days"], 0)

    def test_empty_dashboard(self):
        """Dashboard works with no data beyond setup."""
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["exams_passed_today"], 0)
        self.assertEqual(response.data["active_users"], 0)


class AdminDashboardPermissionTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_student_cannot_access_dashboard(self):
        user, _ = self.factory.create_student()
        client = self.factory.get_auth_client(user)
        response = client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access_dashboard(self):
        anon = APIClient()
        response = anon.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
