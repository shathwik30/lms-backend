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
    class SessionType(models.TextChoices):
        VIDEO = "video", "Video"
        RESOURCE = "resource", "Resource"
        PRACTICE_EXAM = "practice_exam", "Practice Exam"
        PROCTORED_EXAM = "proctored_exam", "Proctored Exam"

    class ResourceType(models.TextChoices):
        PDF = "pdf", "PDF"
        NOTE = "note", "Note"
        MARKDOWN = "markdown", "Markdown"

    week = models.ForeignKey(
        "levels.Week",
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    video_url = models.URLField(max_length=500, blank=True)
    file_url = models.URLField(max_length=500, blank=True)
    resource_type = models.CharField(
        max_length=10,
        choices=ResourceType.choices,
        blank=True,
        default="",
    )
    markdown_content = models.TextField(blank=True, default="")
    thumbnail_url = models.URLField(max_length=500, blank=True, default="")
    duration_seconds = models.PositiveIntegerField(default=0)
    order = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True, db_index=True)
    session_type = models.CharField(
        max_length=20,
        choices=SessionType.choices,
        default=SessionType.VIDEO,
        db_index=True,
    )
    exam = models.ForeignKey(
        "exams.Exam",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sessions",
    )

    class Meta:
        db_table = "sessions"
        ordering = ["order"]

    def __str__(self):
        return self.title
