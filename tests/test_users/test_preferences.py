from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import UserPreference
from core.test_utils import TestFactory


class UserPreferenceAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)

    def test_get_preferences_auto_creates(self):
        self.assertFalse(UserPreference.objects.filter(user=self.user).exists())
        response = self.client.get("/api/v1/auth/preferences/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["push_notifications"])
        self.assertTrue(UserPreference.objects.filter(user=self.user).exists())

    def test_get_preferences_defaults(self):
        response = self.client.get("/api/v1/auth/preferences/")
        self.assertTrue(response.data["push_notifications"])
        self.assertTrue(response.data["email_notifications"])
        self.assertTrue(response.data["doubt_reply_notifications"])
        self.assertTrue(response.data["exam_result_notifications"])
        self.assertTrue(response.data["promotional_notifications"])

    def test_update_single_preference(self):
        response = self.client.patch(
            "/api/v1/auth/preferences/",
            {
                "push_notifications": False,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["push_notifications"])
        self.assertTrue(response.data["email_notifications"])  # unchanged

    def test_update_multiple_preferences(self):
        response = self.client.patch(
            "/api/v1/auth/preferences/",
            {
                "push_notifications": False,
                "promotional_notifications": False,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["push_notifications"])
        self.assertFalse(response.data["promotional_notifications"])
        self.assertTrue(response.data["email_notifications"])

    def test_update_persists(self):
        self.client.patch(
            "/api/v1/auth/preferences/",
            {
                "email_notifications": False,
            },
        )
        response = self.client.get("/api/v1/auth/preferences/")
        self.assertFalse(response.data["email_notifications"])

    def test_unauthenticated_denied(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.get("/api/v1/auth/preferences/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_also_use_preferences(self):
        admin = self.factory.create_admin()
        admin_client = self.factory.get_auth_client(admin)
        response = admin_client.get("/api/v1/auth/preferences/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
