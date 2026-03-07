from __future__ import annotations

import contextlib
import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User as UserModel
from core.constants import ErrorMessage, SuccessMessage

logger = logging.getLogger(__name__)

User = get_user_model()


class AuthService:
    @staticmethod
    def register(user: UserModel) -> dict[str, str]:
        refresh = RefreshToken.for_user(user)

        from core.tasks import send_welcome_email_task

        send_welcome_email_task.delay(user.email, user.full_name)

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
            idinfo = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError:
            return None, None, ErrorMessage.INVALID_GOOGLE_TOKEN

        email = idinfo.get("email")
        if not email or not idinfo.get("email_verified"):
            return None, None, ErrorMessage.GOOGLE_EMAIL_NOT_VERIFIED

        google_id = idinfo["sub"]
        full_name = idinfo.get("name", email.split("@")[0])

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
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

        from core.tasks import send_password_reset_task

        send_password_reset_task.delay(user.email, user.full_name, reset_url)

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
    def complete_onboarding(user: UserModel) -> tuple[bool, str | None]:
        if not user.is_student or not hasattr(user, "student_profile"):
            return False, ErrorMessage.ONLY_STUDENTS_ONBOARDING
        profile = user.student_profile
        profile.onboarding_completed = True
        profile.save(update_fields=["onboarding_completed"])
        return True, None
