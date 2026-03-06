from django.db import models

from core.models import TimeStampedModel


class Course(TimeStampedModel):
    level = models.ForeignKey(
        "levels.Level",
        on_delete=models.CASCADE,
        related_name="courses",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    validity_days = models.PositiveIntegerField(help_text="Access validity in days")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "courses"

    def __str__(self):
        return self.title


class Bookmark(TimeStampedModel):
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    session = models.ForeignKey(
        "courses.Session",
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )

    class Meta:
        db_table = "bookmarks"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "session"], name="unique_bookmark"),
        ]

    def __str__(self):
        return f"{self.student.user.email} → {self.session.title}"


class Session(TimeStampedModel):
    week = models.ForeignKey(
        "levels.Week",
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    video_url = models.URLField(max_length=500)
    duration_seconds = models.PositiveIntegerField()
    order = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "sessions"
        ordering = ["order"]

    def __str__(self):
        return self.title


class Resource(TimeStampedModel):
    class ResourceType(models.TextChoices):
        PDF = "pdf", "PDF"
        NOTE = "note", "Note"

    session = models.ForeignKey(
        Session,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="resources",
    )
    week = models.ForeignKey(
        "levels.Week",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="resources",
    )
    title = models.CharField(max_length=200)
    file_url = models.URLField(max_length=500)
    resource_type = models.CharField(max_length=10, choices=ResourceType.choices, db_index=True)

    class Meta:
        db_table = "resources"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(session__isnull=False) | models.Q(week__isnull=False),
                name="resource_must_have_session_or_week",
            ),
        ]

    def __str__(self):
        return self.title
