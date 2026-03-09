from django.db import models

from core.models import TimeStampedModel


class Question(TimeStampedModel):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    class QuestionType(models.TextChoices):
        MCQ = "mcq", "MCQ"
        MULTI_MCQ = "multi_mcq", "Multi-Select MCQ"
        FILL_BLANK = "fill_blank", "Fill in the Blank"

    exam = models.ForeignKey(
        "exams.Exam",
        on_delete=models.CASCADE,
        related_name="questions",
    )
    level = models.ForeignKey(
        "levels.Level",
        on_delete=models.CASCADE,
        related_name="questions",
    )
    text = models.TextField()
    image_url = models.URLField(max_length=500, blank=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, db_index=True)
    question_type = models.CharField(
        max_length=15,
        choices=QuestionType.choices,
        default=QuestionType.MCQ,
        db_index=True,
    )
    marks = models.PositiveIntegerField(default=4)
    negative_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Marks deducted for wrong answer (0 = no negative marking)",
    )
    explanation = models.TextField(blank=True, help_text="Explanation shown after answering")
    correct_text_answer = models.CharField(
        max_length=500,
        blank=True,
        help_text="Correct answer text for fill-in-the-blank questions",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "questions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Q#{self.pk} ({self.difficulty})"


class Option(TimeStampedModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.TextField()
    image_url = models.URLField(max_length=500, blank=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        db_table = "options"
        ordering = ["id"]

    def __str__(self):
        return f"Option for Q#{self.question_id}"


class Exam(TimeStampedModel):
    class ExamType(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        LEVEL_FINAL = "level_final", "Level Final"
        ONBOARDING = "onboarding", "Onboarding"

    level = models.ForeignKey(
        "levels.Level",
        on_delete=models.CASCADE,
        related_name="exams",
    )
    week = models.ForeignKey(
        "levels.Week",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exams",
    )
    course = models.ForeignKey(
        "courses.Course",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exams",
    )
    exam_type = models.CharField(max_length=15, choices=ExamType.choices, db_index=True)
    title = models.CharField(max_length=200)
    duration_minutes = models.PositiveIntegerField()
    total_marks = models.PositiveIntegerField()
    passing_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    num_questions = models.PositiveIntegerField()
    is_proctored = models.BooleanField(default=False)
    max_warnings = models.PositiveIntegerField(
        default=3,
        help_text="Max proctoring warnings before disqualification",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "exams"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ExamAttempt(TimeStampedModel):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        SUBMITTED = "submitted", "Submitted"
        TIMED_OUT = "timed_out", "Timed Out"

    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="exam_attempts",
    )
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
        db_index=True,
    )
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    total_marks = models.PositiveIntegerField()
    is_passed = models.BooleanField(null=True, blank=True, db_index=True)
    is_disqualified = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "exam_attempts"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["student", "exam"], name="idx_attempt_student_exam"),
            models.Index(fields=["status", "is_passed", "is_disqualified"], name="idx_attempt_leaderboard"),
            models.Index(fields=["student", "started_at"], name="idx_attempt_student_started"),
            models.Index(fields=["status", "started_at"], name="idx_attempt_status_started"),
        ]

    def __str__(self):
        return f"{self.student} → {self.exam.title}"


class AttemptQuestion(TimeStampedModel):
    attempt = models.ForeignKey(
        ExamAttempt,
        on_delete=models.CASCADE,
        related_name="attempt_questions",
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(
        Option,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    selected_options = models.ManyToManyField(
        Option,
        blank=True,
        related_name="multi_attempts",
        help_text="Selected options for multi-select MCQ questions",
    )
    text_answer = models.CharField(
        max_length=500,
        blank=True,
        help_text="Text answer for fill-in-the-blank questions",
    )
    is_correct = models.BooleanField(null=True, blank=True)
    marks_awarded = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    order = models.PositiveIntegerField()

    class Meta:
        db_table = "attempt_questions"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question"], name="unique_question_per_attempt"),
        ]

    def __str__(self):
        return f"Q#{self.question_id} in Attempt #{self.attempt_id}"


class ProctoringViolation(TimeStampedModel):
    class ViolationType(models.TextChoices):
        FULL_SCREEN_EXIT = "full_screen_exit", "Full Screen Exit"
        TAB_SWITCH = "tab_switch", "Tab Switch"
        VOICE_DETECTED = "voice_detected", "Voice Detected"
        MULTI_FACE = "multi_face", "Multiple Faces Detected"
        EXTENSION_DETECTED = "extension_detected", "Extension Detected"

    attempt = models.ForeignKey(
        ExamAttempt,
        on_delete=models.CASCADE,
        related_name="violations",
    )
    violation_type = models.CharField(max_length=25, choices=ViolationType.choices)
    warning_number = models.PositiveIntegerField()
    details = models.TextField(blank=True)

    class Meta:
        db_table = "proctoring_violations"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.violation_type} (Warning {self.warning_number}) - Attempt #{self.attempt_id}"
