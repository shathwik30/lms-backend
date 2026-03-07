from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from core.test_utils import TestFactory


class NotificationAPITests(APITestCase):
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

    def test_list_empty(self):
        response = self.client.get("/api/v1/notifications/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_list_own_notifications(self):
        self._create()
        self._create(title="Second")
        response = self.client.get("/api/v1/notifications/")
        self.assertEqual(response.data["count"], 2)

    def test_list_does_not_show_others(self):
        other_user, _ = self.factory.create_student(email="other@test.com")
        NotificationService.create(
            user=other_user,
            title="Other",
            message="Not yours",
        )
        self._create()
        response = self.client.get("/api/v1/notifications/")
        self.assertEqual(response.data["count"], 1)

    def test_filter_by_is_read(self):
        self._create()
        n2 = self._create(title="Read One")
        n2.is_read = True
        n2.save()
        response = self.client.get("/api/v1/notifications/?is_read=false")
        self.assertEqual(response.data["count"], 1)

    def test_filter_by_type(self):
        self._create(notification_type=Notification.NotificationType.PURCHASE)
        self._create(notification_type=Notification.NotificationType.EXAM_RESULT)
        response = self.client.get("/api/v1/notifications/?notification_type=purchase")
        self.assertEqual(response.data["count"], 1)

    def test_mark_read(self):
        n = self._create()
        self.assertFalse(n.is_read)
        response = self.client.patch(f"/api/v1/notifications/{n.pk}/read/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_mark_read_not_found(self):
        response = self.client.patch("/api/v1/notifications/99999/read/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_read_other_user_404(self):
        other_user, _ = self.factory.create_student(email="other2@test.com")
        n = NotificationService.create(user=other_user, title="X", message="X")
        assert n is not None
        response = self.client.patch(f"/api/v1/notifications/{n.pk}/read/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_all_read(self):
        self._create()
        self._create(title="Two")
        self._create(title="Three")
        response = self.client.post("/api/v1/notifications/read-all/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(
            Notification.objects.filter(user=self.user, is_read=False).count(),
            0,
        )

    def test_mark_all_read_idempotent(self):
        self._create()
        self.client.post("/api/v1/notifications/read-all/")
        response = self.client.post("/api/v1/notifications/read-all/")
        self.assertEqual(response.data["count"], 0)

    def test_unread_count(self):
        self._create()
        self._create(title="Two")
        n3 = self._create(title="Three")
        n3.is_read = True
        n3.save()
        response = self.client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unread_count"], 2)

    def test_unread_count_zero(self):
        response = self.client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(response.data["unread_count"], 0)

    def test_unauthenticated_denied(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.get("/api/v1/notifications/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NotificationHelperTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student()

    def test_create_notification_default_type(self):
        n = NotificationService.create(
            user=self.user,
            title="Test",
            message="Body",
        )
        assert n is not None
        self.assertEqual(n.notification_type, Notification.NotificationType.GENERAL)
        self.assertFalse(n.is_read)

    def test_create_notification_with_data(self):
        n = NotificationService.create(
            user=self.user,
            title="Test",
            message="Body",
            notification_type=Notification.NotificationType.PURCHASE,
            data={"purchase_id": 42},
        )
        assert n is not None
        self.assertEqual(n.data["purchase_id"], 42)  # type: ignore[index]


class NotificationClearAllTests(APITestCase):
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

    def test_clear_all_deletes_all_notifications(self):
        self._create(title="First")
        self._create(title="Second")
        self._create(title="Third")
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 3)
        response = self.client.delete("/api/v1/notifications/clear-all/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_clear_all_returns_deleted_count(self):
        self._create(title="First")
        self._create(title="Second")
        response = self.client.delete("/api/v1/notifications/clear-all/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_clear_all_returns_zero_when_no_notifications(self):
        response = self.client.delete("/api/v1/notifications/clear-all/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_clear_all_does_not_delete_other_users_notifications(self):
        other_user, _ = self.factory.create_student(email="other@test.com")
        NotificationService.create(user=other_user, title="Other's", message="Keep me")
        self._create(title="Mine")
        response = self.client.delete("/api/v1/notifications/clear-all/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(Notification.objects.filter(user=other_user).count(), 1)

    def test_clear_all_deletes_read_and_unread(self):
        self._create(title="Unread")
        n2 = self._create(title="Read")
        n2.is_read = True
        n2.save()
        response = self.client.delete("/api/v1/notifications/clear-all/")
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_clear_all_unauthenticated_denied(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.delete("/api/v1/notifications/clear-all/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NotificationHelperErrorHandlingTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student()

    def test_create_notification_returns_notification_on_success(self):
        n = NotificationService.create(
            user=self.user,
            title="Hello",
            message="World",
        )
        assert n is not None
        self.assertIsInstance(n, Notification)
        self.assertEqual(n.title, "Hello")
        self.assertEqual(n.message, "World")
        self.assertFalse(n.is_read)

    @patch("apps.notifications.models.Notification.objects.create")
    def test_create_notification_returns_none_on_db_error(self, mock_create):
        mock_create.side_effect = Exception("DB failure")
        result = NotificationService.create(
            user=self.user,
            title="Fail",
            message="Should not persist",
        )
        self.assertIsNone(result)

    @patch("apps.notifications.services.logger")
    @patch("apps.notifications.models.Notification.objects.create")
    def test_create_notification_logs_error_on_failure(self, mock_create, mock_logger):
        mock_create.side_effect = Exception("DB failure")
        NotificationService.create(
            user=self.user,
            title="Fail",
            message="Should log",
        )
        mock_logger.exception.assert_called_once()
