from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TimeStampedModel


class SessionFeedback(TimeStampedModel):
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="session_feedbacks",
    )
    session = models.ForeignKey(
        "courses.Session",
        on_delete=models.CASCADE,
        related_name="feedbacks",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        db_index=True,
    )
    difficulty_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        db_index=True,
    )
    clarity_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        db_index=True,
    )
    comment = models.TextField(blank=True)

    class Meta:
        db_table = "session_feedbacks"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "session"], name="unique_feedback_per_session"),
        ]

    def __str__(self):
        return f"Feedback: {self.student} → {self.session.title}"
