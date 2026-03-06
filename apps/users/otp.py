import hmac
import logging
import secrets

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

OTP_EXPIRY_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
OTP_COOLDOWN_SECONDS = 60


class OTPService:
    @staticmethod
    def _cache_key(email, purpose):
        return f"otp:{purpose}:{email}"

    @staticmethod
    def _attempts_key(email, purpose):
        return f"otp_attempts:{purpose}:{email}"

    @staticmethod
    def _cooldown_key(email, purpose):
        return f"otp_cooldown:{purpose}:{email}"

    @staticmethod
    def _generate():
        return str(secrets.randbelow(900000) + 100000)

    @classmethod
    def send(cls, email, purpose="verify"):
        cooldown_key = cls._cooldown_key(email, purpose)
        if cache.get(cooldown_key):
            return False, "Please wait before requesting another OTP."

        otp = cls._generate()
        cache.set(cls._cache_key(email, purpose), otp, OTP_EXPIRY_SECONDS)
        cache.set(cooldown_key, True, OTP_COOLDOWN_SECONDS)
        cache.delete(cls._attempts_key(email, purpose))

        subject_map = {
            "verify": "Verify Your Email — LMS",
            "password_reset": "Password Reset OTP — LMS",
        }
        subject = subject_map.get(purpose, "Your OTP — LMS")

        send_mail(
            subject=subject,
            message=(
                f"Your OTP is: {otp}\n\n"
                f"This code expires in {OTP_EXPIRY_SECONDS // 60} minutes.\n"
                f"If you did not request this, ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info("OTP sent to %s for %s", email, purpose)
        return True, "OTP sent successfully."

    @classmethod
    def verify(cls, email, otp, purpose="verify"):
        attempts_key = cls._attempts_key(email, purpose)
        attempts = cache.get(attempts_key, 0)

        if attempts >= OTP_MAX_ATTEMPTS:
            cache.delete(cls._cache_key(email, purpose))
            return False, "Too many failed attempts. Please request a new OTP."

        stored_otp = cache.get(cls._cache_key(email, purpose))
        if not stored_otp:
            return False, "OTP has expired. Please request a new one."

        if not hmac.compare_digest(stored_otp, otp):
            cache.set(attempts_key, attempts + 1, OTP_EXPIRY_SECONDS)
            return False, "Invalid OTP."

        cache.delete(cls._cache_key(email, purpose))
        cache.delete(attempts_key)
        return True, "OTP verified successfully."
