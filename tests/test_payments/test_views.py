from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.payments.models import Purchase
from apps.progress.models import LevelProgress
from core.test_utils import TestFactory


class PurchaseModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        _, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1)

    def test_active_purchase_is_valid(self):
        purchase = self.factory.create_purchase(self.profile, self.data["level"])
        self.assertTrue(purchase.is_valid)

    def test_expired_purchase_is_not_valid(self):
        purchase = self.factory.create_expired_purchase(self.profile, self.data["level"])
        self.assertFalse(purchase.is_valid)

    def test_revoked_purchase_is_not_valid(self):
        purchase = self.factory.create_purchase(self.profile, self.data["level"])
        purchase.status = Purchase.Status.REVOKED
        purchase.save()
        self.assertFalse(purchase.is_valid)


class PaymentAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data = self.factory.setup_full_level(order=1)

    def test_initiate_payment_dev_mode(self):
        response = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("razorpay_order_id", response.data)
        self.assertTrue(response.data["razorpay_order_id"].startswith("dev_order_"))

    def test_verify_payment_dev_mode(self):
        init_resp = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        order_id = init_resp.data["razorpay_order_id"]

        response = self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "dev_pay_123",
                "razorpay_signature": "dev_sig_123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_verify_sends_purchase_confirmation_email(self):
        from django.core import mail

        init_resp = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": init_resp.data["razorpay_order_id"],
                "razorpay_payment_id": "dev_pay_email",
                "razorpay_signature": "dev_sig_email",
            },
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Purchase Confirmed", mail.outbox[0].subject)

    def test_verify_creates_level_progress(self):
        """Successful verify should create LevelProgress with IN_PROGRESS."""
        init_resp = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": init_resp.data["razorpay_order_id"],
                "razorpay_payment_id": "dev_pay_456",
                "razorpay_signature": "dev_sig_456",
            },
        )
        progress = LevelProgress.objects.get(student=self.profile, level=self.data["level"])
        self.assertEqual(progress.status, LevelProgress.Status.IN_PROGRESS)

    def test_verify_updates_current_level(self):
        """Successful verify should set student's current_level."""
        init_resp = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": init_resp.data["razorpay_order_id"],
                "razorpay_payment_id": "dev_pay_789",
                "razorpay_signature": "dev_sig_789",
            },
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_level, self.data["level"])

    def test_verify_does_not_downgrade_passed_level(self):
        """Re-purchasing after passing should not reset LevelProgress to IN_PROGRESS."""
        LevelProgress.objects.create(
            student=self.profile,
            level=self.data["level"],
            status=LevelProgress.Status.EXAM_PASSED,
        )
        init_resp = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": init_resp.data["razorpay_order_id"],
                "razorpay_payment_id": "dev_pay_nodg",
                "razorpay_signature": "dev_sig_nodg",
            },
        )
        progress = LevelProgress.objects.get(student=self.profile, level=self.data["level"])
        self.assertEqual(progress.status, LevelProgress.Status.EXAM_PASSED)

    def test_verify_wrong_order_id_returns_404(self):
        response = self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": "nonexistent_order",
                "razorpay_payment_id": "pay_123",
                "razorpay_signature": "sig_123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_verify_already_verified_returns_404(self):
        """Double-verifying should fail since txn status is no longer PENDING."""
        init_resp = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        order_id = init_resp.data["razorpay_order_id"]
        self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "dev_pay_1",
                "razorpay_signature": "dev_sig_1",
            },
        )
        response = self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "dev_pay_2",
                "razorpay_signature": "dev_sig_2",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_purchase_history(self):
        self.factory.create_purchase(self.profile, self.data["level"])
        response = self.client.get("/api/v1/payments/purchases/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_transaction_history(self):
        response = self.client.get("/api/v1/payments/transactions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cannot_purchase_without_eligibility(self):
        data2 = self.factory.setup_full_level(order=2)
        response = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": data2["level"].pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_active_purchase_blocked(self):
        self.factory.create_purchase(self.profile, self.data["level"])
        response = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_initiate_nonexistent_level_returns_404(self):
        response = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": 99999,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_access_payments(self):
        anon = APIClient()
        response = anon.post("/api/v1/payments/initiate/", {"level_id": 1})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminPaymentAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        _, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1)

    def test_admin_list_purchases(self):
        self.factory.create_purchase(self.profile, self.data["level"])
        response = self.admin_client.get("/api/v1/payments/admin/purchases/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_admin_extend_validity(self):
        purchase = self.factory.create_purchase(self.profile, self.data["level"])
        old_expiry = purchase.expires_at
        response = self.admin_client.post(
            "/api/v1/payments/admin/extend/",
            {
                "purchase_id": purchase.pk,
                "extra_days": 15,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        purchase.refresh_from_db()
        self.assertGreater(purchase.expires_at, old_expiry)
        self.assertEqual(purchase.extended_by_days, 15)

    def test_admin_extend_expired_purchase_reactivates(self):
        """Extending an expired purchase should re-activate it."""
        purchase = self.factory.create_expired_purchase(self.profile, self.data["level"])
        purchase.status = Purchase.Status.EXPIRED
        purchase.save()
        response = self.admin_client.post(
            "/api/v1/payments/admin/extend/",
            {
                "purchase_id": purchase.pk,
                "extra_days": 30,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, Purchase.Status.ACTIVE)

    def test_admin_extend_nonexistent_purchase_returns_404(self):
        response = self.admin_client.post(
            "/api/v1/payments/admin/extend/",
            {
                "purchase_id": 99999,
                "extra_days": 10,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_cannot_access_admin_purchases(self):
        user, _ = self.factory.create_student(email="other@test.com")
        client = self.factory.get_auth_client(user)
        response = client.get("/api/v1/payments/admin/purchases/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ExpirePurchasesTaskTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        _, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1)

    def test_expire_task_marks_expired_purchases(self):
        from apps.payments.tasks import expire_purchases

        purchase = self.factory.create_expired_purchase(self.profile, self.data["level"])
        self.assertEqual(purchase.status, Purchase.Status.ACTIVE)
        count = expire_purchases()
        self.assertEqual(count, 1)
        purchase.refresh_from_db()
        self.assertEqual(purchase.status, Purchase.Status.EXPIRED)

    def test_expire_task_skips_active_purchases(self):
        from apps.payments.tasks import expire_purchases

        self.factory.create_purchase(self.profile, self.data["level"])
        count = expire_purchases()
        self.assertEqual(count, 0)


class PaymentAmountVerificationTests(APITestCase):
    """Tests for amount verification between transaction and level price."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data = self.factory.setup_full_level(order=1)

    def test_amount_mismatch_returns_400(self):
        """If txn.amount != level.price at verify time, should return 400."""
        from apps.payments.models import PaymentTransaction

        init_resp = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        order_id = init_resp.data["razorpay_order_id"]

        # Tamper with the transaction amount to simulate mismatch
        txn = PaymentTransaction.objects.get(razorpay_order_id=order_id)
        txn.amount = self.data["level"].price + 100
        txn.save(update_fields=["amount"])

        response = self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "dev_pay_mismatch",
                "razorpay_signature": "dev_sig_mismatch",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data["detail"].lower())

        # Transaction should be marked FAILED
        txn.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransaction.Status.FAILED)

    def test_amount_match_succeeds(self):
        """When txn.amount == level.price, verify should succeed normally."""
        init_resp = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        order_id = init_resp.data["razorpay_order_id"]

        response = self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "dev_pay_match",
                "razorpay_signature": "dev_sig_match",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_level_price_change_between_initiate_and_verify_is_caught(self):
        """If level price changes after initiate but before verify, mismatch is caught."""
        init_resp = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        order_id = init_resp.data["razorpay_order_id"]

        # Change the level price after initiation
        level = self.data["level"]
        level.price = level.price + 500
        level.save(update_fields=["price"])

        response = self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "dev_pay_pricechange",
                "razorpay_signature": "dev_sig_pricechange",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data["detail"].lower())


class PaymentDataIsolationTests(APITestCase):
    """Tests that students cannot access each other's payment data."""

    def setUp(self):
        self.factory = TestFactory()
        self.user_a, self.profile_a = self.factory.create_student(email="student_a@test.com")
        self.client_a = self.factory.get_auth_client(self.user_a)
        self.user_b, self.profile_b = self.factory.create_student(email="student_b@test.com")
        self.client_b = self.factory.get_auth_client(self.user_b)
        self.data = self.factory.setup_full_level(order=1)

    def test_student_b_cannot_verify_student_a_transaction(self):
        """Student B should get 404 when trying to verify Student A's transaction."""
        init_resp = self.client_a.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        order_id = init_resp.data["razorpay_order_id"]

        response = self.client_b.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "dev_pay_steal",
                "razorpay_signature": "dev_sig_steal",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_b_cannot_see_student_a_purchase_history(self):
        """Student B's purchase list should not include Student A's purchases."""
        self.factory.create_purchase(self.profile_a, self.data["level"])

        response = self.client_b.get("/api/v1/payments/purchases/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_student_b_cannot_see_student_a_transaction_history(self):
        """Student B's transaction list should not include Student A's transactions."""
        # Student A initiates a payment to create a transaction
        self.client_a.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )

        response = self.client_b.get("/api/v1/payments/transactions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)


class PaymentEdgeCaseTests(APITestCase):
    """Tests for edge cases in the payment flow."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data = self.factory.setup_full_level(order=1)

    def test_inactive_level_returns_404_on_initiate(self):
        """Initiating payment for an inactive level should return 404."""
        level = self.data["level"]
        level.is_active = False
        level.save(update_fields=["is_active"])

        response = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": level.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_verify_with_already_failed_transaction_returns_404(self):
        """Verify should return 404 if the transaction is already FAILED."""
        from apps.payments.models import PaymentTransaction

        init_resp = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        order_id = init_resp.data["razorpay_order_id"]

        # Manually mark transaction as FAILED
        txn = PaymentTransaction.objects.get(razorpay_order_id=order_id)
        txn.status = PaymentTransaction.Status.FAILED
        txn.save(update_fields=["status"])

        response = self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "dev_pay_failed",
                "razorpay_signature": "dev_sig_failed",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_double_verify_returns_404(self):
        """Second verify attempt on an already-verified transaction should return 404."""
        init_resp = self.client.post(
            "/api/v1/payments/initiate/",
            {
                "level_id": self.data["level"].pk,
            },
        )
        order_id = init_resp.data["razorpay_order_id"]

        # First verify succeeds
        first_resp = self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "dev_pay_first",
                "razorpay_signature": "dev_sig_first",
            },
        )
        self.assertEqual(first_resp.status_code, status.HTTP_201_CREATED)

        # Second verify should fail with 404 (status is no longer PENDING)
        second_resp = self.client.post(
            "/api/v1/payments/verify/",
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": "dev_pay_second",
                "razorpay_signature": "dev_sig_second",
            },
        )
        self.assertEqual(second_resp.status_code, status.HTTP_404_NOT_FOUND)
