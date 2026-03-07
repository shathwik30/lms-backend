from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.otp import OTPService


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class OTPUnitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_generate_otp_format(self):
        otp = OTPService._generate()
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

    def test_send_otp_success(self):
        success, msg = OTPService.send("test@example.com", "verify")
        self.assertTrue(success)
        self.assertIn("sent", msg.lower())

    def test_send_otp_cooldown(self):
        OTPService.send("test@example.com", "verify")
        success, msg = OTPService.send("test@example.com", "verify")
        self.assertFalse(success)
        self.assertIn("wait", msg.lower())

    def test_verify_otp_success(self):
        with patch("apps.users.otp.OTPService._generate", return_value="123456"):
            OTPService.send("test@example.com", "verify")
        success, msg = OTPService.verify("test@example.com", "123456", "verify")
        self.assertTrue(success)

    def test_verify_otp_wrong_code(self):
        with patch("apps.users.otp.OTPService._generate", return_value="123456"):
            OTPService.send("test@example.com", "verify")
        success, msg = OTPService.verify("test@example.com", "999999", "verify")
        self.assertFalse(success)
        self.assertIn("invalid", msg.lower())

    def test_verify_otp_expired(self):
        success, msg = OTPService.verify("nobody@example.com", "123456", "verify")
        self.assertFalse(success)
        self.assertIn("expired", msg.lower())

    def test_verify_otp_consumed(self):
        with patch("apps.users.otp.OTPService._generate", return_value="123456"):
            OTPService.send("test@example.com", "verify")
        OTPService.verify("test@example.com", "123456", "verify")
        # Second use should fail
        success, msg = OTPService.verify("test@example.com", "123456", "verify")
        self.assertFalse(success)

    def test_verify_otp_max_attempts(self):
        with patch("apps.users.otp.OTPService._generate", return_value="123456"):
            OTPService.send("test@example.com", "verify")
        for _ in range(5):
            OTPService.verify("test@example.com", "000000", "verify")
        success, msg = OTPService.verify("test@example.com", "123456", "verify")
        self.assertFalse(success)
        self.assertIn("too many", msg.lower())


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class OTPAPITests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_send_otp_endpoint(self):
        response = self.client.post(
            "/api/v1/auth/otp/send/",
            {
                "email": "user@test.com",
                "purpose": "verify",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)

    def test_send_otp_cooldown_returns_429(self):
        self.client.post(
            "/api/v1/auth/otp/send/",
            {
                "email": "user@test.com",
                "purpose": "verify",
            },
        )
        response = self.client.post(
            "/api/v1/auth/otp/send/",
            {
                "email": "user@test.com",
                "purpose": "verify",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_verify_otp_endpoint(self):
        with patch("apps.users.otp.OTPService._generate", return_value="654321"):
            self.client.post(
                "/api/v1/auth/otp/send/",
                {
                    "email": "user@test.com",
                    "purpose": "verify",
                },
            )
        response = self.client.post(
            "/api/v1/auth/otp/verify/",
            {
                "email": "user@test.com",
                "otp": "654321",
                "purpose": "verify",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["verified"])

    def test_verify_otp_wrong_code(self):
        with patch("apps.users.otp.OTPService._generate", return_value="654321"):
            self.client.post(
                "/api/v1/auth/otp/send/",
                {
                    "email": "user@test.com",
                    "purpose": "verify",
                },
            )
        response = self.client.post(
            "/api/v1/auth/otp/verify/",
            {
                "email": "user@test.com",
                "otp": "000000",
                "purpose": "verify",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["verified"])

    def test_verify_otp_invalid_format(self):
        response = self.client.post(
            "/api/v1/auth/otp/verify/",
            {
                "email": "user@test.com",
                "otp": "12",  # too short
                "purpose": "verify",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_otp_invalid_purpose(self):
        response = self.client.post(
            "/api/v1/auth/otp/send/",
            {
                "email": "user@test.com",
                "purpose": "invalid_purpose",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class OTPSecurityTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_otp_is_six_digits(self):
        """generate_otp() must return a zero-padded 6-digit numeric string."""
        for _ in range(50):
            otp = OTPService._generate()
            self.assertEqual(len(otp), 6)
            self.assertTrue(otp.isdigit())
            self.assertGreaterEqual(int(otp), 100000)
            self.assertLessEqual(int(otp), 999999)

    def test_otp_uses_secrets_module(self):
        """The otp module must use the secrets module, not insecure random."""
        import inspect

        import apps.users.otp as otp_module

        source = inspect.getsource(otp_module)
        self.assertIn("secrets", source)
        self.assertNotIn("random.randint", source)

    def test_otp_max_attempts_lockout(self):
        """After 5 wrong attempts the correct OTP should also be rejected."""
        with patch("apps.users.otp.OTPService._generate", return_value="123456"):
            OTPService.send("lockout@example.com", "verify")

        for _ in range(5):
            OTPService.verify("lockout@example.com", "000000", "verify")

        success, msg = OTPService.verify("lockout@example.com", "123456", "verify")
        self.assertFalse(success)
        self.assertIn("too many", msg.lower())

    def test_otp_cooldown_prevents_rapid_resend(self):
        """A second send_otp call within the cooldown window must return False."""
        success_first, _ = OTPService.send("cooldown@example.com", "verify")
        self.assertTrue(success_first)

        success_second, msg = OTPService.send("cooldown@example.com", "verify")
        self.assertFalse(success_second)
        self.assertIn("wait", msg.lower())

    def test_otp_expired_returns_failure(self):
        """If the OTP is deleted from cache (simulating expiry), verify should fail."""
        with patch("apps.users.otp.OTPService._generate", return_value="123456"):
            OTPService.send("expired@example.com", "verify")

        # Simulate expiry by removing the cached OTP
        cache.delete("otp:verify:expired@example.com")

        success, msg = OTPService.verify("expired@example.com", "123456", "verify")
        self.assertFalse(success)
        self.assertIn("expired", msg.lower())

    def test_otp_verification_cleans_up(self):
        """After a successful verification the OTP key must be removed from cache."""
        with patch("apps.users.otp.OTPService._generate", return_value="123456"):
            OTPService.send("cleanup@example.com", "verify")

        success, _ = OTPService.verify("cleanup@example.com", "123456", "verify")
        self.assertTrue(success)

        # The OTP should no longer exist in cache
        stored = cache.get("otp:verify:cleanup@example.com")
        self.assertIsNone(stored)
