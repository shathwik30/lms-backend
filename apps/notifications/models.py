from django.db import models

from core.models import TimeStampedModel


class Notification(TimeStampedModel):
    class NotificationType(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        EXAM_RESULT = "exam_result", "Exam Result"
        DOUBT_REPLY = "doubt_reply", "Doubt Reply"
        LEVEL_UNLOCK = "level_unlock", "Level Unlock"
        COURSE_EXPIRY = "course_expiry", "Course Expiry"
        GENERAL = "general", "General"

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
        db_index=True,
    )
    is_read = models.BooleanField(default=False, db_index=True)
    data = models.JSONField(null=True, blank=True, help_text="Extra payload for the client")

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"], name="idx_notification_user_read"),
        ]

    def __str__(self):
        return f"{self.user.email}: {self.title}"
