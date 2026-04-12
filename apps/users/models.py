from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from core.models import TimeStampedModel


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # type: ignore[attr-defined]
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_admin", True)
        extra_fields.setdefault("is_student", False)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True, blank=True, null=True)
    full_name = models.CharField(max_length=150)
    is_student = models.BooleanField(default=True, db_index=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    profile_picture = models.ImageField(upload_to="users/avatars/", blank=True)
    google_id = models.CharField(max_length=128, unique=True, null=True, blank=True, db_index=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["is_student", "is_active"], name="idx_user_student_active"),
        ]

    def __str__(self):
        return self.email


class StudentProfile(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"
        PREFER_NOT_TO_SAY = "prefer_not_to_say", "Prefer not to say"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    current_level = models.ForeignKey(
        "levels.Level",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="current_students",
    )
    highest_cleared_level = models.ForeignKey(
        "levels.Level",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cleared_students",
    )
    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        null=True,
        blank=True,
    )
    is_onboarding_completed = models.BooleanField(default=False)
    is_onboarding_exam_attempted = models.BooleanField(default=False)

    class Meta:
        db_table = "student_profiles"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Profile: {self.user.email}"


class AdminStudentActionLog(TimeStampedModel):
    class ActionType(models.TextChoices):
        RESET_EXAM_ATTEMPTS = "reset_exam_attempts", "Reset Exam Attempts"
        UNLOCK_LEVEL = "unlock_level", "Unlock Level"
        MANUAL_PASS = "manual_pass", "Manual Pass"
        EXTEND_VALIDITY = "extend_validity", "Extend Validity"

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="admin_action_logs",
    )
    admin_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="student_admin_action_logs",
    )
    action_type = models.CharField(max_length=30, choices=ActionType.choices, db_index=True)
    level = models.ForeignKey(
        "levels.Level",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="admin_student_action_logs",
    )
    purchase = models.ForeignKey(
        "payments.Purchase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="admin_action_logs",
    )
    reason = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "admin_student_action_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "created_at"], name="idx_admin_action_student"),
            models.Index(fields=["action_type", "created_at"], name="idx_admin_action_type"),
        ]

    def __str__(self):
        return f"{self.admin_user.email} → {self.student.user.email} ({self.action_type})"


class IssueReport(TimeStampedModel):
    class Category(models.TextChoices):
        BUG = "bug", "Bug"
        CONTENT = "content", "Content Issue"
        PAYMENT = "payment", "Payment Issue"
        ACCOUNT = "account", "Account Issue"
        OTHER = "other", "Other"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="issue_reports")
    category = models.CharField(max_length=15, choices=Category.choices, default=Category.OTHER, db_index=True)
    subject = models.CharField(max_length=300)
    description = models.TextField()
    screenshot = models.ImageField(upload_to="issues/screenshots/", blank=True)
    is_resolved = models.BooleanField(default=False, db_index=True)
    device_info = models.CharField(max_length=200, blank=True, default="")
    browser_info = models.CharField(max_length=200, blank=True, default="")
    os_info = models.CharField(max_length=200, blank=True, default="")
    admin_response = models.TextField(blank=True, default="")

    class Meta:
        db_table = "issue_reports"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email}: {self.subject}"


class UserPreference(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="preferences")
    push_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    doubt_reply_notifications = models.BooleanField(default=True)
    exam_result_notifications = models.BooleanField(default=True)
    promotional_notifications = models.BooleanField(default=True)
    payment_notifications = models.BooleanField(default=True)
    issue_report_notifications = models.BooleanField(default=True)
    feedback_reminder_notifications = models.BooleanField(default=True)

    class Meta:
        db_table = "user_preferences"

    def __str__(self):
        return f"Preferences: {self.user.email}"
