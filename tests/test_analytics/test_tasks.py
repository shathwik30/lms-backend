from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.analytics.models import DailyRevenue, LevelAnalytics
from apps.analytics.tasks import aggregate_daily_analytics
from apps.exams.models import ExamAttempt
from apps.payments.models import PaymentTransaction, Purchase
from core.test_utils import TestFactory


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class AggregateDailyAnalyticsTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1)
        self.yesterday = timezone.localdate() - timedelta(days=1)

    def test_creates_daily_revenue_record(self):
        aggregate_daily_analytics()
        self.assertTrue(DailyRevenue.objects.filter(date=self.yesterday).exists())

    def test_revenue_zero_when_no_transactions(self):
        aggregate_daily_analytics()
        revenue = DailyRevenue.objects.get(date=self.yesterday)
        self.assertEqual(revenue.total_revenue, 0)
        self.assertEqual(revenue.total_transactions, 0)

    def test_revenue_aggregates_successful_transactions(self):
        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.data["level"],
            amount=Decimal("999.00"),
            gateway_order_id="order_1",
            status=PaymentTransaction.Status.SUCCESS,
        )
        # Backdate to yesterday
        PaymentTransaction.objects.filter(gateway_order_id="order_1").update(
            created_at=timezone.now() - timedelta(days=1),
        )

        aggregate_daily_analytics()
        revenue = DailyRevenue.objects.get(date=self.yesterday)
        self.assertEqual(revenue.total_revenue, Decimal("999.00"))
        self.assertEqual(revenue.total_transactions, 1)

    def test_ignores_failed_transactions(self):
        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.data["level"],
            amount=Decimal("999.00"),
            gateway_order_id="order_f",
            status=PaymentTransaction.Status.FAILED,
        )
        PaymentTransaction.objects.filter(gateway_order_id="order_f").update(
            created_at=timezone.now() - timedelta(days=1),
        )

        aggregate_daily_analytics()
        revenue = DailyRevenue.objects.get(date=self.yesterday)
        self.assertEqual(revenue.total_revenue, 0)

    def test_creates_level_analytics_record(self):
        aggregate_daily_analytics()
        self.assertTrue(
            LevelAnalytics.objects.filter(
                level=self.data["level"],
                date=self.yesterday,
            ).exists()
        )

    def test_level_analytics_counts_attempts(self):
        exam = self.data["exam"]
        ExamAttempt.objects.create(
            student=self.profile,
            exam=exam,
            status=ExamAttempt.Status.SUBMITTED,
            score=15,
            total_marks=exam.total_marks,
            is_passed=True,
            submitted_at=timezone.now() - timedelta(days=1),
        )

        aggregate_daily_analytics()
        analytics = LevelAnalytics.objects.get(
            level=self.data["level"],
            date=self.yesterday,
        )
        self.assertEqual(analytics.total_attempts, 1)
        self.assertEqual(analytics.total_passes, 1)
        self.assertEqual(analytics.total_failures, 0)

    def test_level_analytics_counts_purchases(self):
        purchase = self.factory.create_purchase(self.profile, self.data["level"])
        Purchase.objects.filter(pk=purchase.pk).update(
            purchased_at=timezone.now() - timedelta(days=1),
        )

        aggregate_daily_analytics()
        analytics = LevelAnalytics.objects.get(
            level=self.data["level"],
            date=self.yesterday,
        )
        self.assertEqual(analytics.total_purchases, 1)
        self.assertGreater(analytics.revenue, 0)

    def test_idempotent_updates_existing_records(self):
        aggregate_daily_analytics()
        aggregate_daily_analytics()
        self.assertEqual(
            DailyRevenue.objects.filter(date=self.yesterday).count(),
            1,
        )

    def test_ignores_todays_data(self):
        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.data["level"],
            amount=Decimal("999.00"),
            gateway_order_id="order_today",
            status=PaymentTransaction.Status.SUCCESS,
        )

        aggregate_daily_analytics()
        revenue = DailyRevenue.objects.get(date=self.yesterday)
        self.assertEqual(revenue.total_revenue, 0)
