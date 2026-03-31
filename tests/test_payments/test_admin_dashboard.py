from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.payments.models import PaymentTransaction
from core.test_utils import TestFactory

DASHBOARD_URL = "/api/v1/payments/admin/dashboard/"


class AdminPaymentDashboardTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)

    def test_dashboard_returns_all_fields(self):
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in [
            "total_revenue",
            "successful_payments",
            "failed_payments",
            "refunded_payments",
            "revenue_trend",
            "top_purchased_levels",
        ]:
            self.assertIn(key, response.data, f"Missing key: {key}")

    def test_revenue_calculation(self):
        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.level,
            razorpay_order_id="order_1",
            amount=999,
            status=PaymentTransaction.Status.SUCCESS,
        )
        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.level,
            razorpay_order_id="order_2",
            amount=1500,
            status=PaymentTransaction.Status.SUCCESS,
        )
        # Failed transaction should not count
        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.level,
            razorpay_order_id="order_3",
            amount=500,
            status=PaymentTransaction.Status.FAILED,
        )
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.data["total_revenue"], str(999 + 1500))

    def test_status_counts(self):
        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.level,
            razorpay_order_id="order_s1",
            amount=999,
            status=PaymentTransaction.Status.SUCCESS,
        )
        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.level,
            razorpay_order_id="order_s2",
            amount=999,
            status=PaymentTransaction.Status.SUCCESS,
        )
        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.level,
            razorpay_order_id="order_f1",
            amount=999,
            status=PaymentTransaction.Status.FAILED,
        )
        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.level,
            razorpay_order_id="order_r1",
            amount=999,
            status=PaymentTransaction.Status.REFUNDED,
        )
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.data["successful_payments"], 2)
        self.assertEqual(response.data["failed_payments"], 1)
        self.assertEqual(response.data["refunded_payments"], 1)

    def test_empty_state(self):
        response = self.admin_client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_revenue"], "0")
        self.assertEqual(response.data["successful_payments"], 0)
        self.assertEqual(response.data["failed_payments"], 0)
        self.assertEqual(response.data["refunded_payments"], 0)
        self.assertEqual(response.data["revenue_trend"], [])
        self.assertEqual(response.data["top_purchased_levels"], [])

    def test_revenue_trend_monthly(self):
        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.level,
            razorpay_order_id="order_t1",
            amount=999,
            status=PaymentTransaction.Status.SUCCESS,
        )
        response = self.admin_client.get(DASHBOARD_URL)
        trend = response.data["revenue_trend"]
        self.assertIsInstance(trend, list)
        self.assertGreaterEqual(len(trend), 1)
        entry = trend[0]
        self.assertIn("month", entry)
        self.assertIn("revenue", entry)
        self.assertIn("count", entry)

    def test_top_purchased_levels(self):
        level2 = self.factory.create_level(order=2)
        # 2 purchases for level 1
        self.factory.create_purchase(self.profile, self.level)
        user2, profile2 = self.factory.create_student(email="s2@test.com")
        self.factory.create_purchase(profile2, self.level)
        # 1 purchase for level 2
        self.factory.create_purchase(self.profile, level2)

        response = self.admin_client.get(DASHBOARD_URL)
        top = response.data["top_purchased_levels"]
        self.assertIsInstance(top, list)
        self.assertGreaterEqual(len(top), 2)
        # First level should have highest purchase count
        self.assertEqual(top[0]["level_id"], self.level.pk)
        self.assertEqual(top[0]["purchase_count"], 2)

    def test_student_forbidden(self):
        student_client = self.factory.get_auth_client(self.user)
        response = student_client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated(self):
        anon = APIClient()
        response = anon.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
