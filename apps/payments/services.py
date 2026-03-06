from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.courses.models import Course
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.progress.models import LevelProgress
from apps.users.models import User as UserModel
from core.constants import ErrorMessage, PaymentConstants
from core.exceptions import LevelLocked
from core.services.eligibility import EligibilityService

from .models import PaymentTransaction, Purchase

logger = logging.getLogger(__name__)


class PaymentService:
    @staticmethod
    def initiate_payment(user: UserModel, course_id: int) -> tuple[dict | None, str | None]:
        try:
            course = Course.objects.select_related("level").get(
                pk=course_id,
                is_active=True,
            )
        except Course.DoesNotExist:
            return None, ErrorMessage.COURSE_NOT_FOUND

        profile = user.student_profile

        if not EligibilityService.can_purchase_course(profile, course):
            raise LevelLocked()

        existing = Purchase.objects.filter(
            student=profile,
            course=course,
            status=Purchase.Status.ACTIVE,
        ).first()
        if existing and existing.is_valid:
            return None, ErrorMessage.ACTIVE_PURCHASE_EXISTS

        receipt = f"course_{course.id}_student_{profile.id}"

        if settings.RAZORPAY_KEY_ID:
            from core.services.razorpay import RazorpayService

            try:
                order_data = RazorpayService.create_order(
                    amount=float(course.price),
                    receipt=receipt,
                    notes={
                        "course_id": str(course.id),
                        "student_id": str(profile.id),
                        "course_title": course.title,
                    },
                )
                gateway_order_id = order_data["order_id"]
            except Exception as e:
                logger.error("Razorpay order creation failed: %s", e)
                return None, ErrorMessage.PAYMENT_GATEWAY_ERROR
        else:
            gateway_order_id = f"dev_order_{timezone.now().strftime('%Y%m%d%H%M%S')}_{profile.pk}"

        txn = PaymentTransaction.objects.create(
            student=profile,
            course=course,
            gateway_order_id=gateway_order_id,
            amount=course.price,
        )

        return {
            "transaction_id": txn.id,
            "gateway_order_id": gateway_order_id,
            "amount": str(course.price),
            "currency": PaymentConstants.DEFAULT_CURRENCY,
            "course_id": course.id,
            "course_title": course.title,
            "razorpay_key": settings.RAZORPAY_KEY_ID or None,
        }, None

    @staticmethod
    def verify_payment(user: UserModel, data: dict) -> tuple[Purchase | None, str | None]:
        profile = user.student_profile

        try:
            txn = PaymentTransaction.objects.get(
                gateway_order_id=data["gateway_order_id"],
                student=profile,
                status=PaymentTransaction.Status.PENDING,
            )
        except PaymentTransaction.DoesNotExist:
            return None, ErrorMessage.TRANSACTION_NOT_FOUND

        if settings.RAZORPAY_KEY_ID:
            from core.services.razorpay import RazorpayService

            is_valid = RazorpayService.verify_payment(
                order_id=data["gateway_order_id"],
                payment_id=data["gateway_payment_id"],
                signature=data["gateway_signature"],
            )
            if not is_valid:
                txn.status = PaymentTransaction.Status.FAILED
                txn.save(update_fields=["status"])
                return None, ErrorMessage.PAYMENT_VERIFICATION_FAILED

        course = txn.course
        if not course:
            logger.error("No course linked to txn %s", txn.id)
            return None, ErrorMessage.COURSE_NOT_LINKED

        if txn.amount != course.price:
            logger.warning("Amount mismatch for txn %s: txn=%s, course=%s", txn.id, txn.amount, course.price)
            txn.status = PaymentTransaction.Status.FAILED
            txn.save(update_fields=["status"])
            return None, ErrorMessage.AMOUNT_MISMATCH

        with transaction.atomic():
            txn.gateway_payment_id = data["gateway_payment_id"]
            txn.status = PaymentTransaction.Status.SUCCESS
            txn.save(update_fields=["gateway_payment_id", "status"])

            purchase = Purchase.objects.create(
                student=profile,
                course=course,
                amount_paid=txn.amount,
                expires_at=timezone.now() + timedelta(days=course.validity_days),
            )
            txn.purchase = purchase
            txn.save(update_fields=["purchase"])

            existing_progress = LevelProgress.objects.filter(
                student=profile,
                level=course.level,
            ).first()
            if existing_progress:
                existing_progress.purchase = purchase
                if existing_progress.status not in (
                    LevelProgress.Status.EXAM_PASSED,
                    LevelProgress.Status.SYLLABUS_COMPLETE,
                ):
                    existing_progress.status = LevelProgress.Status.IN_PROGRESS
                    existing_progress.started_at = timezone.now()
                existing_progress.save()
            else:
                LevelProgress.objects.create(
                    student=profile,
                    level=course.level,
                    status=LevelProgress.Status.IN_PROGRESS,
                    purchase=purchase,
                    started_at=timezone.now(),
                )

            if not profile.current_level or course.level.order >= profile.current_level.order:
                profile.current_level = course.level
                profile.save(update_fields=["current_level"])

        NotificationService.create(
            user=user,
            title=f"Purchase Confirmed: {course.title}",
            message=f"Your purchase of {course.title} is confirmed. Valid until {purchase.expires_at.strftime('%d %b %Y')}.",
            notification_type=Notification.NotificationType.PURCHASE,
            data={"purchase_id": purchase.id, "course_id": course.id},
        )

        from core.tasks import send_purchase_confirmation_task

        send_purchase_confirmation_task.delay(
            email=user.email,
            full_name=user.full_name,
            course_title=course.title,
            amount=str(purchase.amount_paid),
            expires_at_iso=purchase.expires_at.isoformat(),
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
        purchase.save()

        return purchase, None
