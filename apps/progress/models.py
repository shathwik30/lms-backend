from django.db import models

from core.models import TimeStampedModel


class SessionProgress(TimeStampedModel):
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="session_progress",
    )
    session = models.ForeignKey(
        "courses.Session",
        on_delete=models.CASCADE,
        related_name="progress_records",
    )
    watched_seconds = models.PositiveIntegerField(default=0)
    is_completed = models.BooleanField(default=False, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "session_progress"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "session"], name="unique_session_progress"),
        ]

    def __str__(self):
        return f"{self.student} → {self.session.title}"


class LevelProgress(TimeStampedModel):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not Started"
        IN_PROGRESS = "in_progress", "In Progress"
        SYLLABUS_COMPLETE = "syllabus_complete", "Syllabus Complete"
        EXAM_PASSED = "exam_passed", "Exam Passed"
        EXAM_FAILED = "exam_failed", "Exam Failed"

    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="level_progress",
    )
    level = models.ForeignKey(
        "levels.Level",
        on_delete=models.CASCADE,
        related_name="progress_records",
    )
    purchase = models.ForeignKey(
        "payments.Purchase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="level_progress",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED,
        db_index=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "level_progress"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "level"], name="unique_level_progress"),
        ]

    def __str__(self):
        return f"{self.student} → {self.level.name} ({self.status})"
