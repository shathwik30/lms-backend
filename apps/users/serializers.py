from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import IssueReport, StudentProfile, UserPreference

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone", "password"]

    def create(self, validated_data):
        # StudentProfile is auto-created via post_save signal
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone", "profile_picture", "is_student", "is_admin"]
        read_only_fields = fields


class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    current_level_name = serializers.CharField(source="current_level.name", default=None)
    highest_cleared_level_name = serializers.CharField(
        source="highest_cleared_level.name",
        default=None,
    )

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "user",
            "current_level",
            "current_level_name",
            "highest_cleared_level",
            "highest_cleared_level_name",
            "gender",
            "is_onboarding_completed",
            "is_onboarding_exam_attempted",
            "created_at",
        ]
        read_only_fields = fields


class AdminStudentListSerializer(serializers.ModelSerializer):
    """
    Used by AdminStudentListView which annotates the queryset with
    ``_validity_till`` and ``_last_active`` to avoid N+1 queries.
    """

    user = UserSerializer(read_only=True)
    current_level_name = serializers.CharField(source="current_level.name", default=None)
    highest_cleared_level_name = serializers.CharField(
        source="highest_cleared_level.name",
        default=None,
    )
    validity_till = serializers.DateTimeField(source="_validity_till", read_only=True, default=None)
    exam_status = serializers.SerializerMethodField()
    streak = serializers.SerializerMethodField()
    last_active = serializers.DateTimeField(source="_last_active", read_only=True, default=None)
    account_status = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "user",
            "current_level",
            "current_level_name",
            "highest_cleared_level",
            "highest_cleared_level_name",
            "gender",
            "is_onboarding_completed",
            "is_onboarding_exam_attempted",
            "validity_till",
            "exam_status",
            "streak",
            "last_active",
            "account_status",
            "created_at",
        ]
        read_only_fields = fields

    def get_exam_status(self, obj: StudentProfile) -> str:
        from apps.exams.models import ExamAttempt

        attempt = ExamAttempt.objects.filter(student=obj).order_by("-started_at").values("status", "is_passed").first()
        if not attempt:
            return "not_attempted"
        if attempt["is_passed"]:
            return "passed"
        if attempt["status"] == ExamAttempt.Status.IN_PROGRESS:
            return "in_progress"
        return "failed"

    def get_streak(self, obj: StudentProfile) -> int:
        import datetime

        from django.utils import timezone

        from apps.progress.models import SessionProgress

        today = timezone.now().date()
        dates: list[datetime.date] = list(
            SessionProgress.objects.filter(student=obj)
            .values_list("updated_at__date", flat=True)
            .distinct()
            .order_by("-updated_at__date")[:60]
        )
        streak = 0
        expected = today
        for d in dates:
            if d == expected:
                streak += 1
                expected -= datetime.timedelta(days=1)
            elif d < expected:
                break
        return streak

    def get_account_status(self, obj: StudentProfile) -> str:
        return "active" if obj.user.is_active else "inactive"


class AdminStudentDetailSerializer(serializers.ModelSerializer):
    """Rich detail serializer used by AdminStudentDetailView GET."""

    user = UserSerializer(read_only=True)
    current_level_name = serializers.CharField(source="current_level.name", default=None)
    highest_cleared_level_name = serializers.CharField(
        source="highest_cleared_level.name",
        default=None,
    )
    account_status = serializers.SerializerMethodField()
    validity_till = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    last_active = serializers.SerializerMethodField()
    curriculum_progress = serializers.SerializerMethodField()
    exam_history = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "user",
            "current_level",
            "current_level_name",
            "highest_cleared_level",
            "highest_cleared_level_name",
            "gender",
            "is_onboarding_completed",
            "is_onboarding_exam_attempted",
            "account_status",
            "validity_till",
            "days_remaining",
            "last_active",
            "curriculum_progress",
            "exam_history",
            "created_at",
        ]
        read_only_fields = fields

    def _get_active_purchase(self, obj):
        if not hasattr(obj, "_cached_purchase"):
            from apps.payments.models import Purchase

            obj._cached_purchase = (
                Purchase.objects.filter(student=obj, status=Purchase.Status.ACTIVE).order_by("-expires_at").first()
            )
        return obj._cached_purchase

    def get_account_status(self, obj: StudentProfile) -> str:
        return "active" if obj.user.is_active else "inactive"

    def get_validity_till(self, obj: StudentProfile) -> str | None:
        purchase = self._get_active_purchase(obj)
        return purchase.expires_at.isoformat() if purchase else None

    def get_days_remaining(self, obj: StudentProfile) -> int | None:
        from django.utils import timezone as tz

        purchase = self._get_active_purchase(obj)
        if not purchase:
            return None
        return max((purchase.expires_at - tz.now()).days, 0)

    def get_last_active(self, obj: StudentProfile) -> str | None:
        from apps.progress.models import SessionProgress

        latest = (
            SessionProgress.objects.filter(student=obj)
            .order_by("-updated_at")
            .values_list("updated_at", flat=True)
            .first()
        )
        return latest.isoformat() if latest else None

    def get_curriculum_progress(self, obj: StudentProfile) -> dict | None:
        from apps.courses.models import Session
        from apps.feedback.models import SessionFeedback
        from apps.progress.models import SessionProgress

        level = obj.current_level
        if not level:
            return None

        total_sessions = Session.objects.filter(
            week__course__level=level, week__course__is_active=True, is_active=True
        ).count()
        if total_sessions == 0:
            return {
                "overall_completion": 0,
                "video_completion": 0,
                "practice_completion": 0,
                "feedback_submitted": 0,
            }

        completed = SessionProgress.objects.filter(
            student=obj, session__week__course__level=level, is_completed=True
        ).count()

        video_total = Session.objects.filter(
            week__course__level=level, session_type=Session.SessionType.VIDEO, is_active=True
        ).count()
        video_done = SessionProgress.objects.filter(
            student=obj,
            session__week__course__level=level,
            session__session_type=Session.SessionType.VIDEO,
            is_completed=True,
        ).count()

        practice_total = Session.objects.filter(
            week__course__level=level, session_type=Session.SessionType.PRACTICE_EXAM, is_active=True
        ).count()
        practice_done = SessionProgress.objects.filter(
            student=obj,
            session__week__course__level=level,
            session__session_type=Session.SessionType.PRACTICE_EXAM,
            is_completed=True,
        ).count()

        feedback_total = video_total
        feedback_done = SessionFeedback.objects.filter(student=obj, session__week__course__level=level).count()

        return {
            "overall_completion": round((completed / total_sessions) * 100, 1) if total_sessions else 0,
            "video_completion": round((video_done / video_total) * 100, 1) if video_total else 0,
            "practice_completion": round((practice_done / practice_total) * 100, 1) if practice_total else 0,
            "feedback_submitted": round((feedback_done / feedback_total) * 100, 1) if feedback_total else 0,
        }

    def get_exam_history(self, obj: StudentProfile) -> list[dict]:
        from apps.exams.models import ExamAttempt

        attempts = ExamAttempt.objects.filter(student=obj).select_related("exam").order_by("-started_at")[:10]

        result = []
        for attempt in attempts:
            attempt_number = ExamAttempt.objects.filter(
                student=obj, exam=attempt.exam, started_at__lte=attempt.started_at
            ).count()
            result.append(
                {
                    "id": attempt.id,
                    "exam_title": attempt.exam.title,
                    "score": str(attempt.score) if attempt.score is not None else None,
                    "total_marks": attempt.total_marks,
                    "is_passed": attempt.is_passed,
                    "started_at": attempt.started_at,
                    "attempt_number": attempt_number,
                }
            )
        return result


class AdminStudentUpdateSerializer(serializers.Serializer):
    current_level = serializers.IntegerField(required=False)
    highest_cleared_level = serializers.IntegerField(required=False)


class UpdateProfileSerializer(serializers.Serializer):
    MAX_PROFILE_PICTURE_SIZE = 5 * 1024 * 1024  # 5 MB

    full_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    profile_picture = serializers.ImageField(required=False, allow_empty_file=False)
    gender = serializers.ChoiceField(
        choices=StudentProfile.Gender.choices,
        required=False,
    )

    def validate_profile_picture(self, value):
        if value and value.size > self.MAX_PROFILE_PICTURE_SIZE:
            raise serializers.ValidationError(
                f"Profile picture must be under {self.MAX_PROFILE_PICTURE_SIZE // (1024 * 1024)} MB."
            )
        return value

    def validate_phone(self, value):
        if not value:
            return value
        user = self.context.get("user")
        qs = User.objects.filter(phone=value)
        if user:
            qs = qs.exclude(pk=user.pk)
        if qs.exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = [
            "push_notifications",
            "email_notifications",
            "doubt_reply_notifications",
            "exam_result_notifications",
            "promotional_notifications",
            "payment_notifications",
            "issue_report_notifications",
            "feedback_reminder_notifications",
        ]


class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(
        choices=["verify", "password_reset"],
        default="verify",
    )


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)
    purpose = serializers.ChoiceField(
        choices=["verify", "password_reset"],
        default="verify",
    )


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(help_text="Google ID token from client-side sign-in")


class IssueReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueReport
        fields = [
            "id",
            "category",
            "subject",
            "description",
            "screenshot",
            "device_info",
            "browser_info",
            "os_info",
            "is_resolved",
            "created_at",
        ]
        read_only_fields = ["id", "is_resolved", "created_at"]


class AdminIssueReportSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    student_name = serializers.CharField(source="user.full_name", read_only=True)
    student_profile_picture = serializers.ImageField(source="user.profile_picture", read_only=True)

    class Meta:
        model = IssueReport
        fields = [
            "id",
            "user",
            "user_email",
            "student_name",
            "student_profile_picture",
            "category",
            "subject",
            "description",
            "screenshot",
            "device_info",
            "browser_info",
            "os_info",
            "admin_response",
            "is_resolved",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_email",
            "student_name",
            "student_profile_picture",
            "category",
            "subject",
            "description",
            "screenshot",
            "device_info",
            "browser_info",
            "os_info",
            "created_at",
        ]
