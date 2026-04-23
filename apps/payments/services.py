from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.courses.models import Course
from apps.levels.models import Level
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.progress.models import CourseProgress, LevelProgress
from apps.users.models import User as UserModel
from core.constants import ErrorMessage, PaymentConstants
from core.exceptions import LevelLocked
from core.services.eligibility import EligibilityService

from .models import PaymentTransaction, Purchase

logger = logging.getLogger(__name__)


class PaymentService:
    @staticmethod
    def initiate_payment(user: UserModel, level_id: uuid.UUID) -> tuple[dict | None, str | None]:
        try:
            level = Level.objects.get(pk=level_id, is_active=True)
        except Level.DoesNotExist:
            return None, ErrorMessage.LEVEL_NOT_FOUND

        profile = user.student_profile

        if not EligibilityService.can_purchase_level(profile, level):
            raise LevelLocked()

        existing_purchase = Purchase.objects.filter(
            student=profile,
            level=level,
            status=Purchase.Status.ACTIVE,
        ).first()
        if existing_purchase and existing_purchase.is_valid:
            return None, ErrorMessage.ACTIVE_LEVEL_PURCHASE_EXISTS

        # Razorpay caps receipt at 40 chars; compact hex prefixes + epoch stay within.
        receipt = f"lvl_{level.id.hex[:8]}_stu_{profile.id.hex[:8]}_{int(timezone.now().timestamp())}"

        if settings.RAZORPAY_KEY_ID:
            from core.services.razorpay import RazorpayService

            try:
                order_data = RazorpayService.create_order(
                    amount=level.price,
                    receipt=receipt,
                    notes={
                        "level_id": str(level.id),
                        "student_id": str(profile.id),
                        "level_name": level.name,
                    },
                )
                razorpay_order_id = order_data["order_id"]
            except Exception as e:
                logger.error("Razorpay order creation failed: %s", e)
                return None, ErrorMessage.PAYMENT_GATEWAY_ERROR
        else:
            razorpay_order_id = f"dev_order_{timezone.now().strftime('%Y%m%d%H%M%S')}_{profile.pk}"

        txn = PaymentTransaction.objects.create(
            student=profile,
            level=level,
            razorpay_order_id=razorpay_order_id,
            amount=level.price,
        )

        logger.info(
            "Payment initiated: txn=%s student=%s level=%s amount=%s order=%s",
            txn.id,
            profile.id,
            level.id,
            level.price,
            razorpay_order_id,
        )

        return {
            "transaction_id": txn.id,
            "razorpay_order_id": razorpay_order_id,
            "amount": str(level.price),
            "currency": PaymentConstants.DEFAULT_CURRENCY,
            "level_id": level.id,
            "level_name": level.name,
            "razorpay_key": settings.RAZORPAY_KEY_ID or None,
        }, None

    @staticmethod
    def verify_payment(user: UserModel, data: dict) -> tuple[Purchase | None, str | None]:
        profile = user.student_profile

        with transaction.atomic():
            try:
                txn = PaymentTransaction.objects.select_for_update().get(
                    razorpay_order_id=data["razorpay_order_id"],
                    student=profile,
                    status=PaymentTransaction.Status.PENDING,
                )
            except PaymentTransaction.DoesNotExist:
                return None, ErrorMessage.TRANSACTION_NOT_FOUND

            if settings.RAZORPAY_KEY_ID:
                from core.services.razorpay import RazorpayService

                is_valid = RazorpayService.verify_payment(
                    order_id=data["razorpay_order_id"],
                    payment_id=data["razorpay_payment_id"],
                    signature=data["razorpay_signature"],
                )
                if not is_valid:
                    txn.status = PaymentTransaction.Status.FAILED
                    txn.save(update_fields=["status"])
                    logger.warning("Signature verification failed for txn %s", txn.id)
                    return None, ErrorMessage.PAYMENT_VERIFICATION_FAILED

            level = txn.level
            if not level:
                logger.error("No level linked to txn %s", txn.id)
                return None, ErrorMessage.LEVEL_NOT_LINKED

            if txn.amount != level.price:
                logger.warning("Amount mismatch for txn %s: txn=%s, level=%s", txn.id, txn.amount, level.price)
                txn.status = PaymentTransaction.Status.FAILED
                txn.save(update_fields=["status"])
                return None, ErrorMessage.AMOUNT_MISMATCH

            purchase = Purchase.objects.create(
                student=profile,
                level=level,
                amount_paid=txn.amount,
                expires_at=timezone.now() + timedelta(days=level.validity_days),
            )
            txn.razorpay_payment_id = data["razorpay_payment_id"]
            txn.status = PaymentTransaction.Status.SUCCESS
            txn.purchase = purchase
            txn.save(update_fields=["razorpay_payment_id", "status", "purchase"])

            PaymentService._provision_access(profile, level, purchase)

        logger.info(
            "Payment verified: txn=%s student=%s level=%s amount=%s",
            txn.id,
            profile.id,
            level.id,
            txn.amount,
        )

        NotificationService.create(
            user=user,
            title=f"Purchase Confirmed: {level.name}",
            message=f"Your purchase of {level.name} is confirmed. Valid until {purchase.expires_at.strftime('%d %b %Y')}.",
            notification_type=Notification.NotificationType.PURCHASE,
            data={"purchase_id": str(purchase.id), "level_id": str(level.id)},
        )

        from core.tasks import fire_and_forget, send_purchase_confirmation_task

        fire_and_forget(
            send_purchase_confirmation_task,
            user.email,
            user.full_name,
            level.name,
            str(purchase.amount_paid),
            purchase.expires_at.isoformat(),
        )

        return purchase, None

    @staticmethod
    def fulfill_captured_payment(razorpay_order_id: str, razorpay_payment_id: str) -> bool:
        """Fulfill a transaction confirmed as captured by Razorpay.

        Used by the reconciliation task when a student's browser never reached
        /verify/ (e.g. tab closed after payment). Idempotent — safe to call
        repeatedly; returns True if the purchase exists (now or already).
        """
        with transaction.atomic():
            try:
                txn = PaymentTransaction.objects.select_for_update().get(razorpay_order_id=razorpay_order_id)
            except PaymentTransaction.DoesNotExist:
                logger.warning("Reconcile: unknown order_id %s", razorpay_order_id)
                return False

            if txn.status == PaymentTransaction.Status.SUCCESS:
                return True  # already fulfilled by /verify/

            if txn.status != PaymentTransaction.Status.PENDING:
                logger.warning("Reconcile: txn %s has status %s, skipping", txn.id, txn.status)
                return False

            level = txn.level
            if not level:
                logger.error("Reconcile: no level linked to txn %s", txn.id)
                return False

            profile = txn.student
            purchase = Purchase.objects.create(
                student=profile,
                level=level,
                amount_paid=txn.amount,
                expires_at=timezone.now() + timedelta(days=level.validity_days),
            )
            txn.razorpay_payment_id = razorpay_payment_id
            txn.status = PaymentTransaction.Status.SUCCESS
            txn.purchase = purchase
            txn.save(update_fields=["razorpay_payment_id", "status", "purchase"])

            PaymentService._provision_access(profile, level, purchase)

        logger.info(
            "Reconciled: txn=%s student=%s level=%s amount=%s",
            txn.id,
            profile.id,
            level.id,
            txn.amount,
        )

        user = profile.user
        NotificationService.create(
            user=user,
            title=f"Purchase Confirmed: {level.name}",
            message=f"Your purchase of {level.name} is confirmed. Valid until {purchase.expires_at.strftime('%d %b %Y')}.",
            notification_type=Notification.NotificationType.PURCHASE,
            data={"purchase_id": str(purchase.id), "level_id": str(level.id)},
        )

        from core.tasks import fire_and_forget, send_purchase_confirmation_task

        fire_and_forget(
            send_purchase_confirmation_task,
            user.email,
            user.full_name,
            level.name,
            str(purchase.amount_paid),
            purchase.expires_at.isoformat(),
        )

        return True

    @staticmethod
    def _provision_access(profile, level, purchase):
        """Create LevelProgress + CourseProgress records after a successful purchase."""
        existing_progress = LevelProgress.objects.filter(
            student=profile,
            level=level,
        ).first()
        if existing_progress:
            existing_progress.purchase = purchase
            if existing_progress.status not in (
                LevelProgress.Status.EXAM_PASSED,
                LevelProgress.Status.SYLLABUS_COMPLETE,
            ):
                existing_progress.status = LevelProgress.Status.IN_PROGRESS
                existing_progress.started_at = timezone.now()
            existing_progress.save(update_fields=["purchase", "status", "started_at"])
        else:
            LevelProgress.objects.create(
                student=profile,
                level=level,
                status=LevelProgress.Status.IN_PROGRESS,
                purchase=purchase,
                started_at=timezone.now(),
            )

        courses = Course.objects.filter(level=level, is_active=True)
        for course in courses:
            CourseProgress.objects.get_or_create(
                student=profile,
                course=course,
                defaults={"status": CourseProgress.Status.NOT_STARTED},
            )

        if not profile.current_level or level.order >= profile.current_level.order:
            profile.current_level = level
            profile.save(update_fields=["current_level"])

    @staticmethod
    def dev_purchase(user: UserModel, level_id: uuid.UUID) -> tuple[Purchase | None, str | None]:
        """Bypass Razorpay and create a purchase directly. For development only."""
        try:
            level = Level.objects.get(pk=level_id, is_active=True)
        except Level.DoesNotExist:
            return None, ErrorMessage.LEVEL_NOT_FOUND

        profile = user.student_profile

        existing = Purchase.objects.filter(
            student=profile,
            level=level,
            status=Purchase.Status.ACTIVE,
        ).first()
        if existing and existing.is_valid:
            return None, ErrorMessage.ACTIVE_LEVEL_PURCHASE_EXISTS

        with transaction.atomic():
            txn = PaymentTransaction.objects.create(
                student=profile,
                level=level,
                razorpay_order_id=f"dev_{timezone.now().strftime('%Y%m%d%H%M%S')}_{profile.pk}",
                razorpay_payment_id=f"dev_pay_{profile.pk}_{level.pk}",
                amount=level.price,
                status=PaymentTransaction.Status.SUCCESS,
            )
            purchase = Purchase.objects.create(
                student=profile,
                level=level,
                amount_paid=level.price,
                expires_at=timezone.now() + timedelta(days=level.validity_days),
            )
            txn.purchase = purchase
            txn.save(update_fields=["purchase"])
            PaymentService._provision_access(profile, level, purchase)

        logger.info("Dev purchase: student=%s level=%s", profile.id, level.id)
        return purchase, None

    @staticmethod
    def extend_validity(
        purchase_id: uuid.UUID, extra_days: int, admin_user: UserModel, reason: str = ""
    ) -> tuple[Purchase | None, str | None]:
        try:
            purchase = Purchase.objects.get(pk=purchase_id)
        except Purchase.DoesNotExist:
            return None, ErrorMessage.PURCHASE_NOT_FOUND

        previous_expires_at = purchase.expires_at
        purchase.expires_at += timedelta(days=extra_days)
        purchase.extended_by_days += extra_days
        purchase.extended_by = admin_user
        if purchase.status == Purchase.Status.EXPIRED:
            purchase.status = Purchase.Status.ACTIVE
        purchase.save(update_fields=["expires_at", "extended_by_days", "extended_by", "status"])

        if reason:
            from apps.users.models import AdminStudentActionLog

            AdminStudentActionLog.objects.create(
                student=purchase.student,
                admin_user=admin_user,
                action_type=AdminStudentActionLog.ActionType.EXTEND_VALIDITY,
                level=purchase.level,
                purchase=purchase,
                reason=reason,
                metadata={
                    "extra_days": extra_days,
                    "previous_expires_at": previous_expires_at.isoformat(),
                    "new_expires_at": purchase.expires_at.isoformat(),
                },
            )

        return purchase, None
