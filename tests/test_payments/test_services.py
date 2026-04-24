from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.payments.models import PaymentTransaction, Purchase
from apps.progress.models import CourseProgress, LevelProgress
from core.constants import ErrorMessage
from core.exceptions import LevelLocked
from core.test_utils import TestFactory


class PaymentServiceInitiateTests(TestCase):
    """Tests for PaymentService.initiate_payment covering uncovered branches."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level1 = self.factory.create_level(order=1, price=999)

    def test_initiate_payment_level_not_found(self):
        """Non-existent level_id returns LEVEL_NOT_FOUND."""
        from apps.payments.services import PaymentService

        result, error = PaymentService.initiate_payment(self.user, 99999)
        self.assertIsNone(result)
        self.assertEqual(error, ErrorMessage.LEVEL_NOT_FOUND)

    def test_initiate_payment_active_purchase_exists(self):
        """Student with active purchase for the level gets ACTIVE_LEVEL_PURCHASE_EXISTS."""
        from apps.payments.services import PaymentService

        self.factory.create_purchase(self.profile, self.level1, days_valid=30)

        result, error = PaymentService.initiate_payment(self.user, self.level1.id)
        self.assertIsNone(result)
        self.assertEqual(error, ErrorMessage.ACTIVE_LEVEL_PURCHASE_EXISTS)

    def test_initiate_payment_level_locked_previous_not_cleared(self):
        """Attempt to buy level 2 without clearing level 1 raises LevelLocked."""
        from apps.payments.services import PaymentService

        level2 = self.factory.create_level(order=2, name="Level 2", price=1999)

        with self.assertRaises(LevelLocked):
            PaymentService.initiate_payment(self.user, level2.id)

    def test_initiate_payment_success(self):
        """Happy path: initiate_payment returns order data."""
        from apps.payments.services import PaymentService

        result, error = PaymentService.initiate_payment(self.user, self.level1.id)
        self.assertIsNone(error)
        self.assertIsNotNone(result)
        self.assertIn("transaction_id", result)
        self.assertIn("razorpay_order_id", result)
        # level.price is a DecimalField so str() yields e.g. "999.00"
        self.level1.refresh_from_db()
        self.assertEqual(result["amount"], str(self.level1.price))
        self.assertEqual(result["level_id"], self.level1.id)

    def test_initiate_payment_free_level_auto_grants_access(self):
        """Free levels should bypass Razorpay and grant access immediately."""
        from apps.payments.services import PaymentService

        self.level1.name = "Foundation"
        self.level1.price = 0
        self.level1.save(update_fields=["name", "price"])

        result, error = PaymentService.initiate_payment(self.user, self.level1.id)

        self.assertIsNone(error)
        self.assertIsNotNone(result)
        self.assertTrue(result["is_free"])
        self.assertIsNone(result["razorpay_order_id"])
        self.assertIsNotNone(result["purchase_id"])
        self.assertTrue(Purchase.objects.filter(student=self.profile, level=self.level1).exists())

        txn = PaymentTransaction.objects.get(student=self.profile, level=self.level1)
        self.assertEqual(txn.status, PaymentTransaction.Status.SUCCESS)
        self.assertIsNotNone(txn.purchase)

        progress = LevelProgress.objects.get(student=self.profile, level=self.level1)
        self.assertEqual(progress.status, LevelProgress.Status.IN_PROGRESS)


class PaymentServiceVerifyTests(TestCase):
    """Tests for PaymentService.verify_payment covering uncovered branches."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1, price=Decimal("999.00"))
        self.course = self.factory.create_course(self.level)

    def test_verify_payment_transaction_not_found(self):
        """Invalid razorpay_order_id returns TRANSACTION_NOT_FOUND."""
        from apps.payments.services import PaymentService

        data = {
            "razorpay_order_id": "nonexistent_order",
            "razorpay_payment_id": "pay_123",
            "razorpay_signature": "sig_123",
        }
        result, error = PaymentService.verify_payment(self.user, data)
        self.assertIsNone(result)
        self.assertEqual(error, ErrorMessage.TRANSACTION_NOT_FOUND)

    def test_verify_payment_level_not_linked(self):
        """Transaction with level=None returns LEVEL_NOT_LINKED."""
        from apps.payments.services import PaymentService

        PaymentTransaction.objects.create(
            student=self.profile,
            level=None,
            razorpay_order_id="order_no_level",
            amount=Decimal("999.00"),
            status=PaymentTransaction.Status.PENDING,
        )

        data = {
            "razorpay_order_id": "order_no_level",
            "razorpay_payment_id": "pay_456",
            "razorpay_signature": "sig_456",
        }
        result, error = PaymentService.verify_payment(self.user, data)
        self.assertIsNone(result)
        self.assertEqual(error, ErrorMessage.LEVEL_NOT_LINKED)

    def test_verify_payment_amount_mismatch(self):
        """Transaction amount != level.price returns AMOUNT_MISMATCH and sets status to FAILED."""
        from apps.payments.services import PaymentService

        txn = PaymentTransaction.objects.create(
            student=self.profile,
            level=self.level,
            razorpay_order_id="order_mismatch",
            amount=Decimal("500.00"),  # Doesn't match level.price of 999.00
            status=PaymentTransaction.Status.PENDING,
        )

        data = {
            "razorpay_order_id": "order_mismatch",
            "razorpay_payment_id": "pay_789",
            "razorpay_signature": "sig_789",
        }
        result, error = PaymentService.verify_payment(self.user, data)
        self.assertIsNone(result)
        self.assertEqual(error, ErrorMessage.AMOUNT_MISMATCH)

        txn.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransaction.Status.FAILED)

    @patch("core.tasks.send_purchase_confirmation_task.delay")
    def test_verify_payment_success_creates_all_records(self, mock_email):
        """Full happy path: verify_payment creates purchase, LevelProgress, CourseProgress."""
        from apps.payments.services import PaymentService

        txn = PaymentTransaction.objects.create(
            student=self.profile,
            level=self.level,
            razorpay_order_id="order_success",
            amount=self.level.price,
            status=PaymentTransaction.Status.PENDING,
        )

        data = {
            "razorpay_order_id": "order_success",
            "razorpay_payment_id": "pay_success",
            "razorpay_signature": "sig_success",
        }
        purchase, error = PaymentService.verify_payment(self.user, data)
        self.assertIsNone(error)
        self.assertIsNotNone(purchase)
        self.assertEqual(purchase.student, self.profile)
        self.assertEqual(purchase.level, self.level)
        self.assertEqual(purchase.amount_paid, self.level.price)

        # Transaction updated
        txn.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(txn.razorpay_payment_id, "pay_success")
        self.assertEqual(txn.purchase, purchase)

        # LevelProgress created
        lp = LevelProgress.objects.get(student=self.profile, level=self.level)
        self.assertEqual(lp.status, LevelProgress.Status.IN_PROGRESS)
        self.assertEqual(lp.purchase, purchase)

        # CourseProgress created for active courses
        cp = CourseProgress.objects.filter(student=self.profile, course=self.course)
        self.assertTrue(cp.exists())
        self.assertEqual(cp.first().status, CourseProgress.Status.NOT_STARTED)

        # Profile current_level updated
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_level, self.level)

        # Email task called
        mock_email.assert_called_once()

    @patch("core.tasks.send_purchase_confirmation_task.delay")
    def test_verify_payment_with_existing_level_progress(self, mock_email):
        """Verify payment with existing LevelProgress updates it rather than creating duplicate."""
        from apps.payments.services import PaymentService

        existing_lp = LevelProgress.objects.create(
            student=self.profile,
            level=self.level,
            status=LevelProgress.Status.EXAM_FAILED,
            started_at=timezone.now() - timedelta(days=30),
        )

        PaymentTransaction.objects.create(
            student=self.profile,
            level=self.level,
            razorpay_order_id="order_existing_lp",
            amount=self.level.price,
            status=PaymentTransaction.Status.PENDING,
        )

        data = {
            "razorpay_order_id": "order_existing_lp",
            "razorpay_payment_id": "pay_existing_lp",
            "razorpay_signature": "sig_existing_lp",
        }
        purchase, error = PaymentService.verify_payment(self.user, data)
        self.assertIsNone(error)
        self.assertIsNotNone(purchase)

        existing_lp.refresh_from_db()
        self.assertEqual(existing_lp.purchase, purchase)
        self.assertEqual(existing_lp.status, LevelProgress.Status.IN_PROGRESS)


class PaymentServiceExtendValidityTests(TestCase):
    """Tests for PaymentService.extend_validity covering uncovered branches."""

    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1, price=999)

    def test_extend_validity_purchase_not_found(self):
        """Non-existent purchase_id returns PURCHASE_NOT_FOUND."""
        from apps.payments.services import PaymentService

        result, error = PaymentService.extend_validity(99999, 30, self.admin)
        self.assertIsNone(result)
        self.assertEqual(error, ErrorMessage.PURCHASE_NOT_FOUND)

    def test_extend_validity_reactivates_expired_purchase(self):
        """Extending an expired purchase reactivates it."""
        from apps.payments.services import PaymentService

        purchase = self.factory.create_expired_purchase(self.profile, self.level)
        self.assertEqual(purchase.status, Purchase.Status.ACTIVE)

        # Force expired status
        purchase.status = Purchase.Status.EXPIRED
        purchase.save(update_fields=["status"])

        original_expires_at = purchase.expires_at

        result, error = PaymentService.extend_validity(purchase.id, 60, self.admin)
        self.assertIsNone(error)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, Purchase.Status.ACTIVE)
        self.assertEqual(result.extended_by_days, 60)
        self.assertEqual(result.extended_by, self.admin)
        self.assertEqual(result.expires_at, original_expires_at + timedelta(days=60))

    def test_extend_validity_active_purchase(self):
        """Extending an active purchase keeps it active and adds days."""
        from apps.payments.services import PaymentService

        purchase = self.factory.create_purchase(self.profile, self.level, days_valid=30)
        original_expires_at = purchase.expires_at

        result, error = PaymentService.extend_validity(purchase.id, 15, self.admin)
        self.assertIsNone(error)
        self.assertEqual(result.status, Purchase.Status.ACTIVE)
        self.assertEqual(result.expires_at, original_expires_at + timedelta(days=15))
