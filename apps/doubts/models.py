from django.db import models

from core.models import TimeStampedModel


class DoubtTicket(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_REVIEW = "in_review", "In Review"
        ANSWERED = "answered", "Answered"
        CLOSED = "closed", "Closed"

    class ContextType(models.TextChoices):
        SESSION = "session", "Session"
        TOPIC = "topic", "Topic"
        EXAM_QUESTION = "exam_question", "Exam Question"

    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="doubt_tickets",
    )
    title = models.CharField(max_length=300)
    description = models.TextField()
    screenshot = models.ImageField(upload_to="doubts/screenshots/", blank=True)

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    context_type = models.CharField(max_length=20, choices=ContextType.choices, db_index=True)
    session = models.ForeignKey(
        "courses.Session",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="doubt_tickets",
    )
    exam_question = models.ForeignKey(
        "exams.Question",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="doubt_tickets",
    )
    assigned_to = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_doubts",
    )
    bonus_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        db_table = "doubt_tickets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Doubt #{self.pk}: {self.title}"


class DoubtReply(TimeStampedModel):
    ticket = models.ForeignKey(
        DoubtTicket,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    author = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="doubt_replies",
    )
    message = models.TextField()
    attachment = models.FileField(upload_to="doubts/attachments/", blank=True)

    class Meta:
        db_table = "doubt_replies"
        ordering = ["created_at"]

    def __str__(self):
        return f"Reply on Doubt #{self.ticket_id}"
