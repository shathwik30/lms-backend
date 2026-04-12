from __future__ import annotations

import contextlib
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework_simplejwt.tokens import RefreshToken

from apps.levels.models import Level
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.payments.models import Purchase
from apps.payments.services import PaymentService
from apps.progress.models import LevelProgress
from apps.users.models import AdminStudentActionLog, StudentProfile, UserPreference
from apps.users.models import User as UserModel
from core.constants import ErrorMessage, SuccessMessage
from core.services.eligibility import EligibilityService

logger = logging.getLogger(__name__)

User = get_user_model()


class AuthService:
    @staticmethod
    def register(user: UserModel) -> dict[str, str]:
        refresh = RefreshToken.for_user(user)

        from core.tasks import fire_and_forget, send_welcome_email_task

        fire_and_forget(send_welcome_email_task, user.email, user.full_name)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    @staticmethod
    def login(email: str, password: str) -> tuple[UserModel | None, dict[str, str] | None]:
        user = authenticate(email=email, password=password)
        if not user:
            return None, None
        refresh = RefreshToken.for_user(user)
        return user, {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    @staticmethod
    def google_auth(id_token_str: str) -> tuple[UserModel | None, dict[str, str] | None, str | bool]:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        try:
            token_info = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError:
            return None, None, ErrorMessage.INVALID_GOOGLE_TOKEN

        email = (token_info.get("email") or "").lower()
        if not email or not token_info.get("email_verified"):
            return None, None, ErrorMessage.GOOGLE_EMAIL_NOT_VERIFIED

        google_id = token_info["sub"]
        full_name = token_info.get("name", email.split("@")[0])

        created = False

        # 1. Returning Google user — look up by stable google_id
        try:
            user = User.objects.get(google_id=google_id)
        except User.DoesNotExist:
            # 2. Existing email/password account — link google_id to it
            try:
                user = User.objects.get(email=email)
                user.google_id = google_id
                user.save(update_fields=["google_id"])
            except User.DoesNotExist:
                # 3. Brand new user — create via Google
                user = User.objects.create_user(email=email, full_name=full_name, google_id=google_id)
                created = True

        if not user.is_active:
            return None, None, ErrorMessage.ACCOUNT_DEACTIVATED

        refresh = RefreshToken.for_user(user)
        tokens = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
        return user, tokens, created

    @staticmethod
    def logout(refresh_token: str) -> tuple[bool, str]:
        try:
            RefreshToken(refresh_token).blacklist()  # type: ignore[arg-type]
            return True, SuccessMessage.LOGGED_OUT
        except Exception:
            return False, ErrorMessage.INVALID_OR_EXPIRED_TOKEN

    @staticmethod
    def change_password(
        user: UserModel, old_password: str, new_password: str
    ) -> tuple[dict[str, str] | None, str | None]:
        if not user.check_password(old_password):
            return None, ErrorMessage.INCORRECT_PASSWORD

        user.set_password(new_password)
        user.save(update_fields=["password"])

        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

        for token in OutstandingToken.objects.filter(user=user):
            with contextlib.suppress(Exception):
                RefreshToken(token.token).blacklist()  # type: ignore[arg-type]

        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, None


class PasswordResetService:
    @staticmethod
    def request_reset(email: str) -> None:
        try:
            user = User.objects.get(email=email.lower())
        except User.DoesNotExist:
            return

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

        from core.tasks import fire_and_forget, send_password_reset_task

        fire_and_forget(send_password_reset_task, user.email, user.full_name, reset_url)

    @staticmethod
    def confirm_reset(uid_b64: str, token: str, new_password: str) -> tuple[bool, str]:
        try:
            uid = force_str(urlsafe_base64_decode(uid_b64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return False, ErrorMessage.INVALID_RESET_LINK

        if not default_token_generator.check_token(user, token):
            return False, ErrorMessage.INVALID_OR_EXPIRED_RESET_LINK

        user.set_password(new_password)
        user.save(update_fields=["password"])
        logger.info("Password reset completed for %s", user.email)
        return True, SuccessMessage.PASSWORD_RESET_DONE


class ProfileService:
    @staticmethod
    def update_profile(user: UserModel, validated_data: dict) -> UserModel:
        gender = validated_data.pop("gender", None)
        if gender is not None and hasattr(user, "student_profile"):
            profile = user.student_profile
            profile.gender = gender
            profile.save(update_fields=["gender"])

        if validated_data:
            for field, value in validated_data.items():
                if field == "phone" and not value:
                    value = None
                setattr(user, field, value)
            user.save(update_fields=list(validated_data.keys()))
        return user

    @staticmethod
    def remove_profile_picture(user: UserModel) -> UserModel:
        if user.profile_picture:
            old_file = user.profile_picture
            user.profile_picture = ""
            user.save(update_fields=["profile_picture"])
            old_file.delete(save=False)
        return user

    @staticmethod
    def update_preferences(user: UserModel, validated_data: dict) -> UserPreference:
        prefs, _ = UserPreference.objects.get_or_create(user=user)
        for field, value in validated_data.items():
            setattr(prefs, field, value)
        prefs.save(update_fields=list(validated_data.keys()))
        return prefs

    @staticmethod
    def complete_onboarding(user: UserModel) -> tuple[bool, str | None]:
        if not user.is_student or not hasattr(user, "student_profile"):
            return False, ErrorMessage.ONLY_STUDENTS_ONBOARDING
        profile = user.student_profile
        profile.is_onboarding_completed = True
        profile.save(update_fields=["is_onboarding_completed"])
        return True, None


class AdminStudentManagementService:
    @staticmethod
    def _get_level(level_id: int) -> Level | None:
        return Level.objects.filter(pk=level_id, is_active=True).first()

    @staticmethod
    def _log_action(
        *,
        profile: StudentProfile,
        admin_user: UserModel,
        action_type: str,
        reason: str,
        level: Level | None = None,
        purchase: Purchase | None = None,
        metadata: dict | None = None,
    ) -> None:
        AdminStudentActionLog.objects.create(
            student=profile,
            admin_user=admin_user,
            action_type=action_type,
            level=level,
            purchase=purchase,
            reason=reason,
            metadata=metadata or {},
        )

    @staticmethod
    def reset_exam_attempts(
        profile: StudentProfile,
        level_id: int,
        admin_user: UserModel,
        reason: str,
    ) -> tuple[LevelProgress | None, str | None]:
        level = AdminStudentManagementService._get_level(level_id)
        if level is None:
            return None, ErrorMessage.LEVEL_NOT_FOUND

        with transaction.atomic():
            progress, _ = LevelProgress.objects.get_or_create(
                student=profile,
                level=level,
                defaults={
                    "status": LevelProgress.Status.IN_PROGRESS,
                    "started_at": timezone.now(),
                },
            )

            previous_attempts_used = progress.final_exam_attempts_used
            previous_status = progress.status
            update_fields: list[str] = []

            if progress.started_at is None:
                progress.started_at = timezone.now()
                update_fields.append("started_at")

            if progress.final_exam_attempts_used != 0:
                progress.final_exam_attempts_used = 0
                update_fields.append("final_exam_attempts_used")

            if progress.status != LevelProgress.Status.EXAM_PASSED:
                next_status = (
                    LevelProgress.Status.SYLLABUS_COMPLETE
                    if EligibilityService.is_syllabus_complete(profile, level)
                    else LevelProgress.Status.IN_PROGRESS
                )
                if progress.status != next_status:
                    progress.status = next_status
                    update_fields.append("status")
                if progress.completed_at is not None:
                    progress.completed_at = None
                    update_fields.append("completed_at")

            if update_fields:
                progress.save(update_fields=update_fields)

            AdminStudentManagementService._log_action(
                profile=profile,
                admin_user=admin_user,
                action_type=AdminStudentActionLog.ActionType.RESET_EXAM_ATTEMPTS,
                reason=reason,
                level=level,
                purchase=progress.purchase,
                metadata={
                    "previous_attempts_used": previous_attempts_used,
                    "new_attempts_used": progress.final_exam_attempts_used,
                    "previous_status": previous_status,
                    "new_status": progress.status,
                },
            )

        NotificationService.create(
            user=profile.user,
            title=f"Exam Attempts Reset: {level.name}",
            message=f"Your final exam attempts for {level.name} were reset by the admin team.",
            notification_type=Notification.NotificationType.EXAM_RESULT,
            data={"level_id": level.id},
        )
        return progress, None

    @staticmethod
    def unlock_level(
        profile: StudentProfile,
        level_id: int,
        admin_user: UserModel,
        reason: str,
    ) -> tuple[Purchase | None, str | None]:
        level = AdminStudentManagementService._get_level(level_id)
        if level is None:
            return None, ErrorMessage.LEVEL_NOT_FOUND

        with transaction.atomic():
            purchase = (
                Purchase.objects.filter(
                    student=profile,
                    level=level,
                    status=Purchase.Status.ACTIVE,
                    expires_at__gt=timezone.now(),
                )
                .order_by("-expires_at")
                .first()
            )
            created_purchase = False
            if purchase is None:
                purchase = Purchase.objects.create(
                    student=profile,
                    level=level,
                    amount_paid=0,
                    expires_at=timezone.now() + timedelta(days=level.validity_days),
                )
                created_purchase = True

            PaymentService._provision_access(profile, level, purchase)

            AdminStudentManagementService._log_action(
                profile=profile,
                admin_user=admin_user,
                action_type=AdminStudentActionLog.ActionType.UNLOCK_LEVEL,
                reason=reason,
                level=level,
                purchase=purchase,
                metadata={
                    "purchase_id": purchase.id,
                    "purchase_created": created_purchase,
                    "expires_at": purchase.expires_at.isoformat(),
                },
            )

        NotificationService.create(
            user=profile.user,
            title=f"Level Unlocked: {level.name}",
            message=f"Access to {level.name} has been unlocked by the admin team.",
            notification_type=Notification.NotificationType.LEVEL_UNLOCK,
            data={"level_id": level.id, "purchase_id": purchase.id},
        )
        return purchase, None

    @staticmethod
    def manual_pass_level(
        profile: StudentProfile,
        level_id: int,
        admin_user: UserModel,
        reason: str,
    ) -> tuple[LevelProgress | None, str | None]:
        level = AdminStudentManagementService._get_level(level_id)
        if level is None:
            return None, ErrorMessage.LEVEL_NOT_FOUND

        latest_purchase = (
            Purchase.objects.filter(student=profile, level=level).order_by("-expires_at", "-purchased_at").first()
        )

        with transaction.atomic():
            progress, created = LevelProgress.objects.get_or_create(
                student=profile,
                level=level,
                defaults={
                    "purchase": latest_purchase,
                    "status": LevelProgress.Status.EXAM_PASSED,
                    "started_at": timezone.now(),
                    "completed_at": timezone.now(),
                    "final_exam_attempts_used": 0,
                },
            )

            previous_status = progress.status
            previous_attempts_used = progress.final_exam_attempts_used
            update_fields: list[str] = []

            if not created:
                if progress.purchase_id is None and latest_purchase is not None:
                    progress.purchase = latest_purchase
                    update_fields.append("purchase")
                if progress.started_at is None:
                    progress.started_at = timezone.now()
                    update_fields.append("started_at")
                if progress.status != LevelProgress.Status.EXAM_PASSED:
                    progress.status = LevelProgress.Status.EXAM_PASSED
                    update_fields.append("status")
                progress.completed_at = timezone.now()
                update_fields.append("completed_at")
                if progress.final_exam_attempts_used != 0:
                    progress.final_exam_attempts_used = 0
                    update_fields.append("final_exam_attempts_used")
                if update_fields:
                    progress.save(update_fields=update_fields)

            profile_update_fields: list[str] = []
            if profile.highest_cleared_level is None or profile.highest_cleared_level.order < level.order:
                profile.highest_cleared_level = level
                profile_update_fields.append("highest_cleared_level")
            if profile.current_level is None or profile.current_level.order < level.order:
                profile.current_level = level
                profile_update_fields.append("current_level")
            if profile_update_fields:
                profile.save(update_fields=profile_update_fields)

            AdminStudentManagementService._log_action(
                profile=profile,
                admin_user=admin_user,
                action_type=AdminStudentActionLog.ActionType.MANUAL_PASS,
                reason=reason,
                level=level,
                purchase=latest_purchase,
                metadata={
                    "previous_status": previous_status,
                    "new_status": progress.status,
                    "previous_attempts_used": previous_attempts_used,
                    "new_attempts_used": progress.final_exam_attempts_used,
                },
            )

        NotificationService.create(
            user=profile.user,
            title=f"Level Marked Passed: {level.name}",
            message=f"{level.name} has been marked as passed by the admin team.",
            notification_type=Notification.NotificationType.EXAM_RESULT,
            data={"level_id": level.id},
        )
        return progress, None
