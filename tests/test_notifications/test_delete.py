from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from core.test_utils import TestFactory


class NotificationDeleteViewTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)

    def _create(self, **kwargs):
        defaults = {
            "user": self.user,
            "title": "Test Notification",
            "message": "Test message",
            "notification_type": Notification.NotificationType.GENERAL,
        }
        defaults.update(kwargs)
        return NotificationService.create(**defaults)

    def test_delete_own_notification(self):
        n = self._create()
        response = self.client.delete(f"/api/v1/notifications/{n.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(pk=n.pk).exists())

    def test_delete_nonexistent_returns_404(self):
        response = self.client.delete("/api/v1/notifications/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_others_notification(self):
        other_user, _ = self.factory.create_student(email="other@test.com")
        n = NotificationService.create(user=other_user, title="Other", message="Not yours")
        assert n is not None
        response = self.client.delete(f"/api/v1/notifications/{n.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Notification.objects.filter(pk=n.pk).exists())

    def test_delete_does_not_affect_other_notifications(self):
        n1 = self._create(title="Keep")
        n2 = self._create(title="Delete")
        self.client.delete(f"/api/v1/notifications/{n2.pk}/")
        self.assertTrue(Notification.objects.filter(pk=n1.pk).exists())

    def test_unauthenticated_denied(self):
        n = self._create()
        anon = APIClient()
        response = anon.delete(f"/api/v1/notifications/{n.pk}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
