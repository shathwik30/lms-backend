"""
Tests for retry logic and error handling in apps/payments/tasks.py.

Covers:
  - expire_purchases: success path (active expired purchases are marked EXPIRED)
  - expire_purchases: SoftTimeLimitExceeded (re-raised, not retried)
  - expire_purchases: generic Exception triggers self.retry()
"""

from datetime import timedelta
from unittest.mock import patch

from celery.exceptions import SoftTimeLimitExceeded
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.payments.models import Purchase
from apps.payments.tasks import expire_purchases
from core.constants import TaskConfig
from core.test_utils import TestFactory

HEAVY_EXPECTED_TOTAL_CALLS = TaskConfig.HEAVY_MAX_RETRIES + 1


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class ExpirePurchasesTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)

    def test_success_path_expires_past_due_purchases(self):
        """Active purchases past their expiry date are marked EXPIRED."""
        purchase = self.factory.create_expired_purchase(self.profile, self.level)
        self.assertEqual(purchase.status, Purchase.Status.ACTIVE)

        count = expire_purchases()

        self.assertEqual(count, 1)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, Purchase.Status.EXPIRED)

    def test_does_not_expire_active_valid_purchases(self):
        """Purchases not yet expired should remain ACTIVE."""
        purchase = self.factory.create_purchase(self.profile, self.level)
        count = expire_purchases()
        self.assertEqual(count, 0)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, Purchase.Status.ACTIVE)

    def test_does_not_re_expire_already_expired(self):
        """Purchases already marked EXPIRED are not counted again."""
        Purchase.objects.create(
            student=self.profile,
            level=self.level,
            amount_paid=self.level.price,
            expires_at=timezone.now() - timedelta(days=5),
            status=Purchase.Status.EXPIRED,
        )
        count = expire_purchases()
        self.assertEqual(count, 0)

    def test_multiple_expired_purchases(self):
        """All expired active purchases are updated in a single call."""
        self.factory.create_expired_purchase(self.profile, self.level)
        level2 = self.factory.create_level(order=2)
        _, profile2 = self.factory.create_student(email="other@test.com")
        self.factory.create_expired_purchase(profile2, level2)

        count = expire_purchases()
        self.assertEqual(count, 2)

    def test_soft_time_limit_exceeded_reraises(self):
        """SoftTimeLimitExceeded is re-raised, NOT retried."""
        with patch(
            "apps.payments.tasks.Purchase.objects",
        ) as mock_objects:
            mock_objects.filter.side_effect = SoftTimeLimitExceeded()
            with self.assertRaises(SoftTimeLimitExceeded):
                expire_purchases()

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    def test_generic_exception_triggers_retry(self):
        """Generic Exception triggers self.retry()."""
        call_count = 0

        def failing_filter(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("DB connection lost")

        with patch(
            "apps.payments.tasks.Purchase.objects",
        ) as mock_objects:
            mock_objects.filter.side_effect = failing_filter
            result = expire_purchases.apply()
            self.assertEqual(result.state, "FAILURE")
            self.assertEqual(call_count, HEAVY_EXPECTED_TOTAL_CALLS)

    def test_returns_zero_when_nothing_to_expire(self):
        """Returns 0 when no purchases need expiring."""
        count = expire_purchases()
        self.assertEqual(count, 0)
