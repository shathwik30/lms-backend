from __future__ import annotations

import logging
import uuid
from typing import Any

from apps.users.models import User

from .models import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, dict):
            return {key: NotificationService._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [NotificationService._json_safe(item) for item in value]
        return value

    @staticmethod
    def create(
        user: User,
        title: str,
        message: str,
        notification_type: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> Notification | None:
        try:
            return Notification.objects.create(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type or Notification.NotificationType.GENERAL,
                data=NotificationService._json_safe(data),
            )
        except Exception:
            logger.exception("Failed to create notification for user %s: %s", user, title)
            return None

    @staticmethod
    def mark_read(notification: Notification) -> None:
        notification.is_read = True
        notification.save(update_fields=["is_read"])

    @staticmethod
    def mark_all_read(user: User) -> int:
        return Notification.objects.filter(
            user=user,
            is_read=False,
        ).update(is_read=True)

    @staticmethod
    def delete_all(user: User) -> int:
        count, _ = Notification.objects.filter(user=user).delete()
        return count

    @staticmethod
    def delete_one(user: User, notification_id: int) -> tuple[bool, str | None]:
        try:
            notification = Notification.objects.get(pk=notification_id, user=user)
        except Notification.DoesNotExist:
            from core.constants import ErrorMessage

            return False, ErrorMessage.NOT_FOUND
        notification.delete()
        return True, None

    @staticmethod
    def unread_count(user: User) -> int:
        return Notification.objects.filter(
            user=user,
            is_read=False,
        ).count()
