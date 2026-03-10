from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.test_utils import TestFactory

User = get_user_model()


class UserModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_create_student_user(self):
        user, profile = self.factory.create_student()
        self.assertTrue(user.is_student)
        self.assertFalse(user.is_admin)
        self.assertIsNotNone(profile)

    def test_create_admin_user(self):
        admin = self.factory.create_admin()
        self.assertTrue(admin.is_admin)
        self.assertTrue(admin.is_staff)
        self.assertFalse(admin.is_student)

    def test_signal_creates_student_profile(self):
        """Signal should auto-create StudentProfile for student users."""
        user = User.objects.create_user(
            email="signal@test.com",
            password="test123",
            full_name="Signal Test",
        )
        self.assertTrue(hasattr(user, "student_profile"))

    def test_signal_skips_admin_profile(self):
        admin = self.factory.create_admin()
        self.assertFalse(hasattr(admin, "student_profile"))

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="test123", full_name="No Email")

    def test_signal_does_not_duplicate_on_save(self):
        """Re-saving an existing user should not create a second profile."""
        user, profile = self.factory.create_student()
        user.full_name = "Updated Name"
        user.save()
        self.assertEqual(user.student_profile.pk, profile.pk)


class AuthAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_register(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "new@test.com",
                "full_name": "New User",
                "password": "securepass123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_register_sends_welcome_email(self):
        from django.core import mail

        self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "welcome@test.com",
                "full_name": "Welcome User",
                "password": "securepass123",
            },
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Welcome", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["welcome@test.com"])

    def test_register_short_password(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "short@test.com",
                "full_name": "Short Pass",
                "password": "abc",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_email(self):
        self.factory.create_student(email="dup@test.com")
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "dup@test.com",
                "full_name": "Duplicate",
                "password": "securepass123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_required_fields(self):
        response = self.client.post("/api/v1/auth/register/", {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_success(self):
        self.factory.create_student(email="login@test.com", password="mypass123")
        response = self.client.post(
            "/api/v1/auth/login/",
            {
                "email": "login@test.com",
                "password": "mypass123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)

    def test_login_wrong_password(self):
        self.factory.create_student(email="wrong@test.com", password="mypass123")
        response = self.client.post(
            "/api/v1/auth/login/",
            {
                "email": "wrong@test.com",
                "password": "wrongpass",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_email(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {
                "email": "nobody@test.com",
                "password": "whatever123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_authenticated(self):
        user, _ = self.factory.create_student()
        client = self.factory.get_auth_client(user)
        response = client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], user.email)

    def test_me_includes_profile_for_student(self):
        user, _ = self.factory.create_student()
        client = self.factory.get_auth_client(user)
        response = client.get("/api/v1/auth/me/")
        self.assertIn("profile", response.data)

    def test_me_admin_no_profile(self):
        admin = self.factory.create_admin()
        client = self.factory.get_auth_client(admin)
        response = client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("profile", response.data)

    def test_me_unauthenticated(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout(self):
        user, _ = self.factory.create_student()
        client = self.factory.get_auth_client(user)
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        response = client.post("/api/v1/auth/logout/", {"refresh": str(refresh)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_without_token(self):
        user, _ = self.factory.create_student(email="logout2@test.com")
        client = self.factory.get_auth_client(user)
        response = client.post("/api/v1/auth/logout/", {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_unauthenticated(self):
        response = self.client.post("/api/v1/auth/logout/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminStudentAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.user, self.profile = self.factory.create_student()

    def test_admin_list_students(self):
        response = self.admin_client.get("/api/v1/auth/admin/students/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_admin_student_detail(self):
        response = self.admin_client.get(f"/api/v1/auth/admin/students/{self.profile.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_student_detail_404(self):
        response = self.admin_client.get("/api/v1/auth/admin/students/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_promote_student(self):
        level = self.factory.create_level(order=1)
        response = self.admin_client.patch(
            f"/api/v1/auth/admin/students/{self.profile.pk}/",
            {"highest_cleared_level": level.pk},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.highest_cleared_level, level)

    def test_admin_promote_invalid_level_returns_404(self):
        response = self.admin_client.patch(
            f"/api/v1/auth/admin/students/{self.profile.pk}/",
            {"highest_cleared_level": 99999},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_set_current_level_invalid_returns_404(self):
        response = self.admin_client.patch(
            f"/api/v1/auth/admin/students/{self.profile.pk}/",
            {"current_level": 99999},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_cannot_access_admin(self):
        student_client = self.factory.get_auth_client(self.user)
        response = student_client.get("/api/v1/auth/admin/students/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access_admin(self):
        response = self.client.get("/api/v1/auth/admin/students/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UpdateProfileAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student(
            email="profile@test.com",
            password="testpass123",
        )
        self.client = self.factory.get_auth_client(self.user)

    def test_update_full_name(self):
        response = self.client.patch("/api/v1/auth/me/", {"full_name": "New Name"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "New Name")

    def test_update_phone(self):
        response = self.client.patch("/api/v1/auth/me/", {"phone": "1234567890"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "1234567890")

    def test_update_both_fields(self):
        response = self.client.patch(
            "/api/v1/auth/me/",
            {
                "full_name": "Updated Name",
                "phone": "9876543210",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Updated Name")
        self.assertEqual(self.user.phone, "9876543210")

    def test_clear_phone(self):
        self.user.phone = "1111111111"
        self.user.save()
        response = self.client.patch("/api/v1/auth/me/", {"phone": ""})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.phone)

    def test_duplicate_phone_rejected(self):
        self.factory.create_student(email="other@test.com")
        other = User.objects.get(email="other@test.com")
        other.phone = "5555555555"
        other.save()
        response = self.client.patch("/api/v1/auth/me/", {"phone": "5555555555"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_own_phone_not_flagged_as_duplicate(self):
        self.user.phone = "1234567890"
        self.user.save()
        response = self.client.patch("/api/v1/auth/me/", {"phone": "1234567890"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_unauthenticated(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.patch("/api/v1/auth/me/", {"full_name": "Hacker"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_response_contains_user_data(self):
        response = self.client.patch("/api/v1/auth/me/", {"full_name": "Check"})
        self.assertEqual(response.data["full_name"], "Check")
        self.assertEqual(response.data["email"], "profile@test.com")


class UpdateGenderAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student(
            email="gender@test.com",
            password="testpass123",
        )
        self.client = self.factory.get_auth_client(self.user)

    def test_update_gender(self):
        response = self.client.patch("/api/v1/auth/me/", {"gender": "male"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.gender, "male")

    def test_update_gender_prefer_not_to_say(self):
        response = self.client.patch("/api/v1/auth/me/", {"gender": "prefer_not_to_say"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.gender, "prefer_not_to_say")

    def test_invalid_gender_rejected(self):
        response = self.client.patch("/api/v1/auth/me/", {"gender": "invalid"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gender_in_profile_response(self):
        """GET /api/v1/auth/me/ should include gender in the profile."""
        self.profile.gender = "female"
        self.profile.save(update_fields=["gender"])
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["gender"], "female")

    def test_gender_default_is_null(self):
        """New profile should have gender=null."""
        response = self.client.get("/api/v1/auth/me/")
        self.assertIsNone(response.data["profile"]["gender"])

    def test_update_gender_with_other_fields(self):
        """Updating gender alongside user fields should work."""
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"full_name": "New Name", "gender": "other"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.full_name, "New Name")
        self.assertEqual(self.profile.gender, "other")

    def test_update_only_user_fields_without_gender(self):
        """Updating only user fields should not affect gender."""
        self.profile.gender = "male"
        self.profile.save(update_fields=["gender"])
        response = self.client.patch("/api/v1/auth/me/", {"full_name": "Another Name"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.gender, "male")


class ChangePasswordAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student(
            email="chpw@test.com",
            password="oldpass123",
        )
        self.client = self.factory.get_auth_client(self.user)

    def test_change_password_success(self):
        response = self.client.post(
            "/api/v1/auth/change-password/",
            {
                "old_password": "oldpass123",
                "new_password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass456"))

    def test_change_password_wrong_old(self):
        response = self.client.post(
            "/api/v1/auth/change-password/",
            {
                "old_password": "wrongold",
                "new_password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_change_password_short_new(self):
        response = self.client.post(
            "/api/v1/auth/change-password/",
            {
                "old_password": "oldpass123",
                "new_password": "short",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_unauthenticated(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.post(
            "/api/v1/auth/change-password/",
            {
                "old_password": "oldpass123",
                "new_password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_can_login_with_new_password(self):
        self.client.post(
            "/api/v1/auth/change-password/",
            {
                "old_password": "oldpass123",
                "new_password": "newpass456",
            },
        )
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.post(
            "/api/v1/auth/login/",
            {
                "email": "chpw@test.com",
                "password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)

    def test_old_password_no_longer_works(self):
        self.client.post(
            "/api/v1/auth/change-password/",
            {
                "old_password": "oldpass123",
                "new_password": "newpass456",
            },
        )
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.post(
            "/api/v1/auth/login/",
            {
                "email": "chpw@test.com",
                "password": "oldpass123",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_URL="http://localhost:3000",
)
class PasswordResetAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student(
            email="reset@test.com",
            password="oldpass123",
        )

    def test_request_reset_existing_email(self):
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {
                "email": "reset@test.com",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detail", response.data)

    def test_request_reset_sends_email(self):
        from django.core import mail

        self.client.post(
            "/api/v1/auth/password-reset/",
            {
                "email": "reset@test.com",
            },
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset-password", mail.outbox[0].body)

    def test_request_reset_nonexistent_email_still_200(self):
        """Should not reveal whether email exists."""
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {
                "email": "nobody@test.com",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_request_reset_nonexistent_email_no_mail(self):
        from django.core import mail

        self.client.post(
            "/api/v1/auth/password-reset/",
            {
                "email": "nobody@test.com",
            },
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_request_reset_invalid_email_format(self):
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {
                "email": "not-an-email",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_reset_success(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {
                "uid": uid,
                "token": token,
                "new_password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass456"))

    def test_confirm_reset_invalid_uid(self):
        token = default_token_generator.make_token(self.user)
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {
                "uid": "invaliduid",
                "token": token,
                "new_password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_reset_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {
                "uid": uid,
                "token": "bad-token",
                "new_password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_reset_token_single_use(self):
        """Token should be invalidated after password change."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {
                "uid": uid,
                "token": token,
                "new_password": "newpass456",
            },
        )
        # Second attempt with same token should fail
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {
                "uid": uid,
                "token": token,
                "new_password": "anotherpass789",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_reset_short_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {
                "uid": uid,
                "token": token,
                "new_password": "short",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_reset_nonexistent_user(self):
        uid = urlsafe_base64_encode(force_bytes(99999))
        response = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {
                "uid": uid,
                "token": "some-token",
                "new_password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_login_with_new_password_after_reset(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {
                "uid": uid,
                "token": token,
                "new_password": "newpass456",
            },
        )
        response = self.client.post(
            "/api/v1/auth/login/",
            {
                "email": "reset@test.com",
                "password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)


# ── Google OAuth Tests ──


@override_settings(GOOGLE_CLIENT_ID="test-google-client-id")
class GoogleOAuthAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_new_user_creation(self, mock_verify):
        """Google sign-in with a new email should create a user and return created=True."""
        mock_verify.return_value = {
            "sub": "google-uid-001",
            "email": "newgoogle@example.com",
            "email_verified": True,
            "name": "Google User",
            "picture": "https://lh3.example.com/photo.jpg",
        }
        response = self.client.post(
            "/api/v1/auth/google/",
            {
                "id_token": "valid-google-token",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["created"])
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertEqual(response.data["user"]["email"], "newgoogle@example.com")
        user = User.objects.get(email="newgoogle@example.com")
        self.assertEqual(user.google_id, "google-uid-001")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_returning_user_lookup_by_google_id(self, mock_verify):
        """Returning Google user should be found by google_id, not email."""
        User.objects.create_user(
            email="googleuser@example.com",
            full_name="Google User",
            google_id="google-uid-returning",
        )
        mock_verify.return_value = {
            "sub": "google-uid-returning",
            "email": "googleuser@example.com",
            "email_verified": True,
            "name": "Google User",
        }
        response = self.client.post("/api/v1/auth/google/", {"id_token": "valid-google-token"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["created"])
        self.assertIn("tokens", response.data)

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_links_existing_email_password_account(self, mock_verify):
        """Google sign-in with an email that already has a password account should link google_id."""
        self.factory.create_student(email="emailuser@example.com", password="strongpass123")
        mock_verify.return_value = {
            "sub": "google-uid-link",
            "email": "emailuser@example.com",
            "email_verified": True,
            "name": "Email User",
        }
        response = self.client.post("/api/v1/auth/google/", {"id_token": "valid-google-token"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["created"])
        self.assertIn("tokens", response.data)
        user = User.objects.get(email="emailuser@example.com")
        self.assertEqual(user.google_id, "google-uid-link")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_existing_user_login(self, mock_verify):
        """Google sign-in with an existing email should log in and return created=False."""
        self.factory.create_student(email="existing@example.com")
        mock_verify.return_value = {
            "sub": "google-uid-existing",
            "email": "existing@example.com",
            "email_verified": True,
            "name": "Existing User",
            "picture": "",
        }
        response = self.client.post(
            "/api/v1/auth/google/",
            {
                "id_token": "valid-google-token",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["created"])
        self.assertIn("tokens", response.data)
        self.assertEqual(response.data["user"]["email"], "existing@example.com")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_invalid_token_returns_400(self, mock_verify):
        """An invalid Google token should return 400."""
        mock_verify.side_effect = ValueError("Invalid token")
        response = self.client.post(
            "/api/v1/auth/google/",
            {
                "id_token": "invalid-token",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_google_unverified_email_returns_400(self, mock_verify):
        """A Google account with an unverified email should return 400."""
        mock_verify.return_value = {
            "sub": "google-uid-unverified",
            "email": "unverified@example.com",
            "email_verified": False,
            "name": "Unverified User",
        }
        response = self.client.post(
            "/api/v1/auth/google/",
            {
                "id_token": "valid-but-unverified-token",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)


# ── Complete Onboarding Tests ──


class CompleteOnboardingAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student(
            email="onboard@test.com",
        )
        self.client = self.factory.get_auth_client(self.user)

    def test_complete_onboarding_marks_true(self):
        """POST should set onboarding_completed=True on the student profile."""
        self.assertFalse(self.profile.onboarding_completed)
        response = self.client.post("/api/v1/auth/onboarding/complete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["onboarding_completed"])
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.onboarding_completed)

    def test_non_student_gets_400(self):
        """An admin (non-student) user should receive 400."""
        admin = self.factory.create_admin(email="adminonboard@test.com")
        admin_client = self.factory.get_auth_client(admin)
        response = admin_client.post("/api/v1/auth/onboarding/complete/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)


# ── Report an Issue Tests ──


class ReportIssueAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student(email="reporter@test.com")
        self.client = self.factory.get_auth_client(self.user)

    def test_create_issue_report(self):
        """POST /api/v1/auth/report-issue/ should create an issue report."""
        response = self.client.post(
            "/api/v1/auth/report-issue/",
            {
                "category": "bug",
                "subject": "App crashes on login",
                "description": "The app crashes every time I try to log in.",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["subject"], "App crashes on login")
        self.assertEqual(response.data["category"], "bug")
        self.assertFalse(response.data["is_resolved"])

    def test_list_user_issues(self):
        """GET /api/v1/auth/my-issues/ should list only the current user's issues."""
        # Create an issue for this user
        self.client.post(
            "/api/v1/auth/report-issue/",
            {
                "category": "content",
                "subject": "Typo in lesson 3",
                "description": "There is a typo in the third lesson.",
            },
        )
        # Create an issue for another user
        other_user, _ = self.factory.create_student(email="other@test.com")
        other_client = self.factory.get_auth_client(other_user)
        other_client.post(
            "/api/v1/auth/report-issue/",
            {
                "category": "payment",
                "subject": "Payment failed",
                "description": "My payment did not go through.",
            },
        )

        response = self.client.get("/api/v1/auth/my-issues/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["subject"], "Typo in lesson 3")


# ── Onboarding Completed in Profile Tests ──


class OnboardingCompletedInProfileTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student(
            email="profilecheck@test.com",
        )
        self.client = self.factory.get_auth_client(self.user)

    def test_me_includes_onboarding_completed_in_profile(self):
        """GET /api/v1/auth/me/ should include onboarding_completed in the profile."""
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("profile", response.data)
        self.assertIn("onboarding_completed", response.data["profile"])
        self.assertFalse(response.data["profile"]["onboarding_completed"])

    def test_me_reflects_onboarding_completed_after_completion(self):
        """After completing onboarding, GET /api/v1/auth/me/ should show True."""
        self.profile.onboarding_completed = True
        self.profile.save(update_fields=["onboarding_completed"])
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["profile"]["onboarding_completed"])


# ── Avatar Upload Tests ──


class AvatarUploadTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student(email="avatar@test.com")
        self.client = self.factory.get_auth_client(self.user)

    def _make_image(self):
        """Create a small in-memory image for testing."""
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return SimpleUploadedFile("avatar.png", buf.read(), content_type="image/png")

    def test_upload_avatar(self):
        image = self._make_image()
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"profile_picture": image},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile_picture)
        self.assertIn("users/avatars/", self.user.profile_picture.name)

    def test_avatar_url_in_response(self):
        image = self._make_image()
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"profile_picture": image},
            format="multipart",
        )
        self.assertTrue(response.data["profile_picture"])

    def test_delete_avatar(self):
        # First upload
        image = self._make_image()
        self.client.patch(
            "/api/v1/auth/me/",
            {"profile_picture": image},
            format="multipart",
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile_picture)
        # Then delete
        response = self.client.delete("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile_picture)

    def test_upload_replaces_previous(self):
        img1 = self._make_image()
        self.client.patch(
            "/api/v1/auth/me/",
            {"profile_picture": img1},
            format="multipart",
        )
        self.user.refresh_from_db()
        first_name = self.user.profile_picture.name
        img2 = self._make_image()
        self.client.patch(
            "/api/v1/auth/me/",
            {"profile_picture": img2},
            format="multipart",
        )
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.profile_picture.name, first_name)

    def test_update_name_without_affecting_avatar(self):
        image = self._make_image()
        self.client.patch(
            "/api/v1/auth/me/",
            {"profile_picture": image},
            format="multipart",
        )
        self.user.refresh_from_db()
        original = self.user.profile_picture.name
        response = self.client.patch("/api/v1/auth/me/", {"full_name": "New Name"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile_picture.name, original)


class ChangePasswordSecurityTests(APITestCase):
    """Tests for token blacklisting and new token issuance on password change."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student(
            email="chpwsec@test.com",
            password="oldpass123",
        )
        self.client = self.factory.get_auth_client(self.user)

    def test_change_password_returns_new_tokens(self):
        """Response must contain both 'refresh' and 'access' keys."""
        response = self.client.post(
            "/api/v1/auth/change-password/",
            {
                "old_password": "oldpass123",
                "new_password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("refresh", response.data)
        self.assertIn("access", response.data)

    def test_old_refresh_token_rejected_after_password_change(self):
        """Old refresh tokens must be blacklisted after a password change."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        old_refresh = RefreshToken.for_user(self.user)

        # Change the password (this should blacklist all outstanding tokens)
        self.client.post(
            "/api/v1/auth/change-password/",
            {
                "old_password": "oldpass123",
                "new_password": "newpass456",
            },
        )

        # Try to use the old refresh token to get a new access token
        anon = APIClient()
        response = anon.post(
            "/api/v1/auth/token/refresh/",
            {
                "refresh": str(old_refresh),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_wrong_old_password(self):
        """Submitting an incorrect old password must return 400."""
        response = self.client.post(
            "/api/v1/auth/change-password/",
            {
                "old_password": "wrongpassword",
                "new_password": "newpass456",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LogoutSecurityTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student(email="logoutsec@test.com")
        self.client = self.factory.get_auth_client(self.user)
        self.refresh = RefreshToken.for_user(self.user)

    def test_logout_with_valid_token_succeeds(self):
        response = self.client.post(
            "/api/v1/auth/logout/",
            {
                "refresh": str(self.refresh),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_without_token_returns_400(self):
        response = self.client.post("/api/v1/auth/logout/", {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_with_invalid_token_returns_400(self):
        response = self.client.post(
            "/api/v1/auth/logout/",
            {
                "refresh": "invalid-token",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_blacklists_token(self):
        """After successful logout, the same refresh token should be rejected."""
        self.client.post(
            "/api/v1/auth/logout/",
            {
                "refresh": str(self.refresh),
            },
        )
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.post(
            "/api/v1/auth/token/refresh/",
            {
                "refresh": str(self.refresh),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfilePictureSizeValidationTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student(email="picsize@test.com")
        self.client = self.factory.get_auth_client(self.user)

    def test_large_profile_picture_rejected(self):
        """A profile picture larger than 5MB should be rejected with 400."""
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile

        buf = io.BytesIO(b"\x00" * (6 * 1024 * 1024))  # 6 MB of data
        large_file = SimpleUploadedFile(
            "large.png",
            buf.getvalue(),
            content_type="image/png",
        )
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"profile_picture": large_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_small_profile_picture_accepted(self):
        """A proper small PNG image should be accepted with 200."""
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        small_file = SimpleUploadedFile(
            "small.png",
            buf.read(),
            content_type="image/png",
        )
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"profile_picture": small_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SignalErrorHandlingTests(TestCase):
    def test_signal_logs_error_on_profile_creation_failure(self):
        """When StudentProfile.objects.get_or_create raises, the signal catches
        the error and logs it instead of crashing."""
        User = get_user_model()
        with (
            patch(
                "apps.users.models.StudentProfile.objects.get_or_create",
                side_effect=Exception("DB error"),
            ),
            patch("apps.users.signals.logger") as mock_logger,
        ):
            user = User.objects.create_user(
                email="signalfail@test.com",
                password="testpass123",
                full_name="Signal Fail",
            )
            self.assertIsNotNone(user)
            self.assertTrue(User.objects.filter(email="signalfail@test.com").exists())
            mock_logger.exception.assert_called_once()

    def test_signal_still_works_normally(self):
        """Creating a student user normally should produce a student_profile."""
        User = get_user_model()
        user = User.objects.create_user(
            email="signalok@test.com",
            password="testpass123",
            full_name="Signal OK",
        )
        self.assertTrue(hasattr(user, "student_profile"))
        self.assertIsNotNone(user.student_profile)
