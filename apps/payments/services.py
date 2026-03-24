from __future__ import annotations

import logging
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
    def initiate_payment(user: UserModel, level_id: int) -> tuple[dict | None, str | None]:
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

        receipt = f"level_{level.id}_student_{profile.id}"

        if settings.RAZORPAY_KEY_ID:
            from core.services.razorpay import RazorpayService

            try:
                order_data = RazorpayService.create_order(
                    amount=float(level.price),
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

        try:
            txn = PaymentTransaction.objects.select_related("level").get(
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

        with transaction.atomic():
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

            # Create/update LevelProgress
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

            # Create CourseProgress for all active courses in the level
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

        NotificationService.create(
            user=user,
            title=f"Purchase Confirmed: {level.name}",
            message=f"Your purchase of {level.name} is confirmed. Valid until {purchase.expires_at.strftime('%d %b %Y')}.",
            notification_type=Notification.NotificationType.PURCHASE,
            data={"purchase_id": purchase.id, "level_id": level.id},
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
    def extend_validity(purchase_id: int, extra_days: int, admin_user: UserModel) -> tuple[Purchase | None, str | None]:
        try:
            purchase = Purchase.objects.get(pk=purchase_id)
        except Purchase.DoesNotExist:
            return None, ErrorMessage.PURCHASE_NOT_FOUND

        purchase.expires_at += timedelta(days=extra_days)
        purchase.extended_by_days += extra_days
        purchase.extended_by = admin_user
        if purchase.status == Purchase.Status.EXPIRED:
            purchase.status = Purchase.Status.ACTIVE
        purchase.save(update_fields=["expires_at", "extended_by_days", "extended_by", "status"])

        return purchase, None
