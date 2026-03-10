from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.analytics.models import DailyRevenue, LevelAnalytics
from core.test_utils import TestFactory


class AnalyticsModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.level = self.factory.create_level(order=1)

    def test_create_daily_revenue(self):
        rev = DailyRevenue.objects.create(
            date=date.today(),
            total_revenue=5000,
            total_transactions=10,
        )
        self.assertEqual(str(rev), f"Revenue: {date.today()}")

    def test_create_level_analytics(self):
        analytics = LevelAnalytics.objects.create(
            level=self.level,
            date=date.today(),
            total_attempts=20,
            total_passes=15,
            total_failures=5,
            total_purchases=8,
            revenue=8000,
        )
        self.assertIsNotNone(analytics.pk)


class AnalyticsAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.level = self.factory.create_level(order=1)

    def test_admin_revenue_list(self):
        DailyRevenue.objects.create(
            date=date.today(),
            total_revenue=5000,
            total_transactions=10,
        )
        response = self.admin_client.get("/api/v1/analytics/revenue/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_admin_level_analytics_list(self):
        LevelAnalytics.objects.create(
            level=self.level,
            date=date.today(),
            total_attempts=20,
            total_passes=15,
        )
        response = self.admin_client.get("/api/v1/analytics/levels/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_student_cannot_access_analytics(self):
        user, _ = self.factory.create_student()
        client = self.factory.get_auth_client(user)
        response = client.get("/api/v1/analytics/revenue/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_access_level_analytics(self):
        user, _ = self.factory.create_student()
        client = self.factory.get_auth_client(user)
        response = client.get("/api/v1/analytics/levels/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access_analytics(self):
        response = self.client.get("/api/v1/analytics/revenue/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_cannot_access_level_analytics(self):
        anon = APIClient()
        response = anon.get("/api/v1/analytics/levels/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AggregateAnalyticsTaskTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.data = self.factory.setup_full_level(order=1, num_questions=5)

    def test_aggregate_creates_daily_revenue(self):
        from apps.analytics.tasks import aggregate_daily_analytics
        from apps.payments.models import PaymentTransaction

        _, profile = self.factory.create_student()
        yesterday = timezone.localdate() - timedelta(days=1)

        # Create a successful transaction backdated to yesterday (local time)
        txn = PaymentTransaction.objects.create(
            student=profile,
            level=self.data["level"],
            razorpay_order_id="test_order_1",
            amount=999,
            status=PaymentTransaction.Status.SUCCESS,
        )
        PaymentTransaction.objects.filter(pk=txn.pk).update(
            created_at=timezone.localtime() - timedelta(days=1),
        )

        aggregate_daily_analytics()
        rev = DailyRevenue.objects.get(date=yesterday)
        self.assertEqual(rev.total_transactions, 1)
        self.assertEqual(float(rev.total_revenue), 999.0)

    def test_aggregate_creates_level_analytics(self):
        from apps.analytics.tasks import aggregate_daily_analytics
        from apps.exams.models import ExamAttempt

        _, profile = self.factory.create_student()
        yesterday = timezone.localdate() - timedelta(days=1)

        attempt = ExamAttempt.objects.create(
            student=profile,
            exam=self.data["exam"],
            total_marks=20,
            status=ExamAttempt.Status.SUBMITTED,
            is_passed=True,
            score=20,
        )
        ExamAttempt.objects.filter(pk=attempt.pk).update(
            submitted_at=timezone.localtime() - timedelta(days=1),
        )

        aggregate_daily_analytics()
        analytics = LevelAnalytics.objects.get(
            level=self.data["level"],
            date=yesterday,
        )
        self.assertEqual(analytics.total_attempts, 1)
        self.assertEqual(analytics.total_passes, 1)


class LevelAnalyticsPassRateTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.level = self.factory.create_level(order=1)
        from apps.analytics.serializers import LevelAnalyticsSerializer

        self.serializer_class = LevelAnalyticsSerializer

    def test_pass_rate_returns_none_for_zero_attempts(self):
        analytics = LevelAnalytics.objects.create(
            level=self.level,
            date=date.today(),
            total_attempts=0,
            total_passes=0,
        )
        serializer = self.serializer_class(analytics)
        self.assertIsNone(serializer.data["pass_rate"])

    def test_pass_rate_correct_calculation(self):
        analytics = LevelAnalytics.objects.create(
            level=self.level,
            date=date.today(),
            total_attempts=20,
            total_passes=15,
        )
        serializer = self.serializer_class(analytics)
        self.assertEqual(serializer.data["pass_rate"], 75.0)

    def test_pass_rate_rounds_correctly(self):
        analytics = LevelAnalytics.objects.create(
            level=self.level,
            date=date.today(),
            total_attempts=3,
            total_passes=1,
        )
        serializer = self.serializer_class(analytics)
        self.assertEqual(serializer.data["pass_rate"], 33.33)
