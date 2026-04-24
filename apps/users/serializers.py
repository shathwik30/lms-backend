from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from core.serializer_fields import UUIDOrLegacyIntegerField

from .models import AdminStudentActionLog, IssueReport, StudentProfile, UserPreference

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

    def validate_email(self, value: str) -> str:
        return value.lower()


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
    name = serializers.CharField(source="user.full_name", read_only=True)
    student_name = serializers.CharField(source="user.full_name", read_only=True)
    student_email = serializers.EmailField(source="user.email", read_only=True)
    student_profile_picture = serializers.ImageField(source="user.profile_picture", read_only=True)
    current_level_name = serializers.CharField(source="current_level.name", default=None)
    highest_cleared_level_name = serializers.CharField(
        source="highest_cleared_level.name",
        default=None,
    )
    validity_till = serializers.DateTimeField(source="_validity_till", read_only=True, default=None)
    days_remaining = serializers.SerializerMethodField()
    validity_status = serializers.SerializerMethodField()
    exam_status = serializers.SerializerMethodField()
    streak = serializers.SerializerMethodField()
    streak_label = serializers.SerializerMethodField()
    last_active = serializers.DateTimeField(source="_last_active", read_only=True, default=None)
    account_status = serializers.SerializerMethodField()
    account_status_display = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "name",
            "student_name",
            "student_email",
            "student_profile_picture",
            "user",
            "current_level",
            "current_level_name",
            "highest_cleared_level",
            "highest_cleared_level_name",
            "gender",
            "is_onboarding_completed",
            "is_onboarding_exam_attempted",
            "validity_till",
            "days_remaining",
            "validity_status",
            "exam_status",
            "streak",
            "streak_label",
            "last_active",
            "account_status",
            "account_status_display",
            "created_at",
        ]
        read_only_fields = fields

    def get_days_remaining(self, obj: StudentProfile) -> int | None:
        validity_till = getattr(obj, "_validity_till", None)
        if validity_till is None:
            return None
        return max((validity_till - timezone.now()).days, 0)

    def get_validity_status(self, obj: StudentProfile) -> str:
        validity_till = getattr(obj, "_validity_till", None)
        if validity_till is None:
            return "none"
        if validity_till <= timezone.now():
            return "expired"
        if (validity_till - timezone.now()).days <= 7:
            return "expiring_soon"
        return "active"

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

    def get_streak_label(self, obj: StudentProfile) -> str:
        streak = self.get_streak(obj)
        return "day" if streak == 1 else "days"

    def get_account_status(self, obj: StudentProfile) -> str:
        return "active" if obj.user.is_active else "inactive"

    def get_account_status_display(self, obj: StudentProfile) -> str:
        return "active" if obj.user.is_active else "blocked"


class AdminStudentDetailSerializer(serializers.ModelSerializer):
    """Rich detail serializer used by AdminStudentDetailView GET."""

    user = UserSerializer(read_only=True)
    name = serializers.CharField(source="user.full_name", read_only=True)
    student_name = serializers.CharField(source="user.full_name", read_only=True)
    student_email = serializers.EmailField(source="user.email", read_only=True)
    student_profile_picture = serializers.ImageField(source="user.profile_picture", read_only=True)
    student_code = serializers.SerializerMethodField()
    registered_on = serializers.SerializerMethodField()
    current_level_name = serializers.CharField(source="current_level.name", default=None)
    highest_cleared_level_name = serializers.CharField(
        source="highest_cleared_level.name",
        default=None,
    )
    account_status = serializers.SerializerMethodField()
    account_status_display = serializers.SerializerMethodField()
    validity_till = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    validity_status = serializers.SerializerMethodField()
    learning_streak = serializers.SerializerMethodField()
    longest_streak = serializers.SerializerMethodField()
    streak_summary = serializers.SerializerMethodField()
    engagement_status = serializers.SerializerMethodField()
    last_active = serializers.SerializerMethodField()
    last_login_at = serializers.DateTimeField(source="user.last_login", read_only=True, default=None)
    last_login_ip = serializers.SerializerMethodField()
    profile_overview = serializers.SerializerMethodField()
    exam_access_status = serializers.SerializerMethodField()
    exam_access_message = serializers.SerializerMethodField()
    exam_summary = serializers.SerializerMethodField()
    curriculum_progress = serializers.SerializerMethodField()
    exam_history = serializers.SerializerMethodField()
    proctoring_summary = serializers.SerializerMethodField()
    support_interaction = serializers.SerializerMethodField()
    payment_history = serializers.SerializerMethodField()
    admin_action_history = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "name",
            "student_name",
            "student_email",
            "student_profile_picture",
            "student_code",
            "registered_on",
            "user",
            "current_level",
            "current_level_name",
            "highest_cleared_level",
            "highest_cleared_level_name",
            "gender",
            "is_onboarding_completed",
            "is_onboarding_exam_attempted",
            "account_status",
            "account_status_display",
            "validity_till",
            "days_remaining",
            "validity_status",
            "learning_streak",
            "longest_streak",
            "streak_summary",
            "engagement_status",
            "last_active",
            "last_login_at",
            "last_login_ip",
            "profile_overview",
            "exam_access_status",
            "exam_access_message",
            "exam_summary",
            "curriculum_progress",
            "exam_history",
            "proctoring_summary",
            "support_interaction",
            "payment_history",
            "admin_action_history",
            "created_at",
            "updated_at",
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

    def get_account_status_display(self, obj: StudentProfile) -> str:
        return "active" if obj.user.is_active else "blocked"

    def get_student_code(self, obj: StudentProfile) -> str:
        return f"STU-{str(obj.pk).replace('-', '').upper()[-5:]}"

    def get_registered_on(self, obj: StudentProfile) -> str:
        return timezone.localtime(obj.created_at).date().isoformat()

    def get_validity_till(self, obj: StudentProfile) -> str | None:
        purchase = self._get_active_purchase(obj)
        return purchase.expires_at.isoformat() if purchase else None

    def get_days_remaining(self, obj: StudentProfile) -> int | None:
        purchase = self._get_active_purchase(obj)
        if not purchase:
            return None
        return max((purchase.expires_at - timezone.now()).days, 0)

    def get_validity_status(self, obj: StudentProfile) -> str:
        purchase = self._get_active_purchase(obj)
        if not purchase:
            latest_purchase = purchase or getattr(obj, "_latest_purchase", None) or self._get_latest_purchase(obj)
            return "expired" if latest_purchase else "none"
        if purchase.expires_at <= timezone.now():
            return "expired"
        if (purchase.expires_at - timezone.now()).days <= 7:
            return "expiring_soon"
        return "active"

    def get_last_active(self, obj: StudentProfile) -> str | None:
        from apps.progress.models import SessionProgress

        latest = (
            SessionProgress.objects.filter(student=obj)
            .order_by("-updated_at")
            .values_list("updated_at", flat=True)
            .first()
        )
        return latest.isoformat() if latest else None

    def _get_active_dates(self, obj: StudentProfile) -> list:
        if not hasattr(obj, "_active_dates"):
            from apps.progress.models import SessionProgress

            obj._active_dates = sorted(
                set(
                    SessionProgress.objects.filter(student=obj)
                    .values_list("updated_at__date", flat=True)
                    .distinct()
                )
            )
        return obj._active_dates

    def get_learning_streak(self, obj: StudentProfile) -> int:
        import datetime

        today = timezone.now().date()
        dates_desc = sorted(self._get_active_dates(obj), reverse=True)
        streak = 0
        expected = today
        for active_date in dates_desc:
            if active_date == expected:
                streak += 1
                expected -= datetime.timedelta(days=1)
            elif active_date < expected:
                break
        return streak

    def get_longest_streak(self, obj: StudentProfile) -> int:
        import datetime

        dates = self._get_active_dates(obj)
        if not dates:
            return 0
        longest = current = 1
        for i in range(1, len(dates)):
            if dates[i] - dates[i - 1] == datetime.timedelta(days=1):
                current += 1
                longest = max(longest, current)
            else:
                current = 1
        return longest

    def get_streak_summary(self, obj: StudentProfile) -> dict:
        import datetime

        today = timezone.now().date()
        active_set = set(self._get_active_dates(obj))
        days = [today - datetime.timedelta(days=offset) for offset in range(6, -1, -1)]
        current = self.get_learning_streak(obj)
        at_risk_threshold = 3
        if current == 0:
            status_label = "broken"
        elif current < at_risk_threshold:
            status_label = "at_risk"
        else:
            status_label = "healthy"
        return {
            "current": current,
            "longest": self.get_longest_streak(obj),
            "status": status_label,
            "last_7_days": [
                {
                    "date": day.isoformat(),
                    "is_active": day in active_set,
                }
                for day in days
            ],
        }

    def get_engagement_status(self, obj: StudentProfile) -> dict:
        last_active_iso = self.get_last_active(obj)
        streak = self.get_learning_streak(obj)

        if last_active_iso is None:
            return {"status": "inactive", "label": "Inactive", "tone": "danger"}

        from django.utils.dateparse import parse_datetime

        last_active_dt = parse_datetime(last_active_iso)
        days_since = (timezone.now() - last_active_dt).days if last_active_dt else None

        if days_since is None or days_since >= 30:
            return {"status": "inactive", "label": "Inactive", "tone": "danger"}
        if days_since >= 7:
            return {"status": "at_risk", "label": "At Risk", "tone": "warning"}
        if streak >= 7:
            return {"status": "healthy", "label": "Healthy", "tone": "success"}
        return {"status": "active", "label": "Active", "tone": "neutral"}

    def get_last_login_ip(self, obj: StudentProfile) -> None:
        return None

    def _get_latest_purchase(self, obj):
        if not hasattr(obj, "_latest_purchase"):
            from apps.payments.models import Purchase

            obj._latest_purchase = Purchase.objects.filter(student=obj).order_by("-expires_at", "-purchased_at").first()
        return obj._latest_purchase

    def _get_level_progress(self, obj):
        if not hasattr(obj, "_level_progress"):
            from apps.progress.models import LevelProgress

            obj._level_progress = (
                LevelProgress.objects.filter(student=obj, level=obj.current_level).first()
                if obj.current_level_id
                else None
            )
        return obj._level_progress

    def get_profile_overview(self, obj: StudentProfile) -> dict:
        return {
            "email": obj.user.email,
            "phone": obj.user.phone,
            "current_curriculum_level": obj.current_level_id,
            "current_curriculum_level_name": obj.current_level.name if obj.current_level else None,
            "validity_till": self.get_validity_till(obj),
            "days_remaining": self.get_days_remaining(obj),
            "last_login_at": obj.user.last_login.isoformat() if obj.user.last_login else None,
            "last_login_ip": self.get_last_login_ip(obj),
        }

    def get_exam_access_status(self, obj: StudentProfile) -> str:
        from apps.progress.models import LevelProgress
        from core.services.eligibility import EligibilityService

        level = obj.current_level
        if level is None:
            return "no_level"

        purchase = self._get_active_purchase(obj)
        if purchase is None:
            return "locked"

        progress = self._get_level_progress(obj)
        if progress and progress.status == LevelProgress.Status.EXAM_PASSED:
            return "passed"
        if not EligibilityService.is_syllabus_complete(obj, level):
            return "locked"
        if progress and progress.final_exam_attempts_used >= level.max_final_exam_attempts:
            return "attempt_limit_reached"
        return "unlocked"

    def get_exam_access_message(self, obj: StudentProfile) -> str | None:
        status = self.get_exam_access_status(obj)
        level = obj.current_level
        if status == "no_level":
            return None
        if status == "locked":
            return "Student must complete all required content before the final exam unlocks."
        if status == "attempt_limit_reached" and level is not None:
            return f"All {level.max_final_exam_attempts} final exam attempts have been used."
        if status == "passed":
            return "Student has already passed the final exam for the current level."
        return "Final exam is available."

    def get_exam_summary(self, obj: StudentProfile) -> dict | None:
        level = obj.current_level
        if level is None:
            return None

        progress = self._get_level_progress(obj)
        attempts_used = progress.final_exam_attempts_used if progress else 0
        return {
            "attempts_used": attempts_used,
            "attempts_allowed": level.max_final_exam_attempts,
            "attempts_remaining": max(level.max_final_exam_attempts - attempts_used, 0),
            "status": self.get_exam_access_status(obj),
        }

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
            "completed_modules": completed,
            "total_modules": total_sessions,
            "exam_access_status": self.get_exam_access_status(obj),
            "exam_access_message": self.get_exam_access_message(obj),
        }

    def get_exam_history(self, obj: StudentProfile) -> list[dict]:
        from django.db.models import Count

        from apps.exams.models import ExamAttempt

        attempts = (
            ExamAttempt.objects.filter(student=obj)
            .select_related("exam")
            .annotate(violations_count=Count("violations"))
            .order_by("-started_at")[:10]
        )

        result = []
        for attempt in attempts:
            attempt_number = ExamAttempt.objects.filter(
                student=obj, exam=attempt.exam, started_at__lte=attempt.started_at
            ).count()
            duration_seconds = None
            if attempt.submitted_at:
                duration_seconds = int((attempt.submitted_at - attempt.started_at).total_seconds())
            result.append(
                {
                    "id": str(attempt.id),
                    "exam_title": attempt.exam.title,
                    "score": str(attempt.score) if attempt.score is not None else None,
                    "total_marks": attempt.total_marks,
                    "is_passed": attempt.is_passed,
                    "started_at": attempt.started_at.isoformat(),
                    "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                    "attempt_number": attempt_number,
                    "status": attempt.status,
                    "auto_submitted": attempt.status == ExamAttempt.Status.TIMED_OUT,
                    "is_disqualified": attempt.is_disqualified,
                    "violations_count": attempt.violations_count,
                    "duration_seconds": duration_seconds,
                }
            )
        return result

    def get_proctoring_summary(self, obj: StudentProfile) -> dict:
        from apps.exams.models import ExamAttempt, ProctoringViolation

        violations = ProctoringViolation.objects.filter(attempt__student=obj)
        total = violations.count()
        last = violations.order_by("-created_at").select_related("attempt__exam").first()
        attempts_with_violations = (
            ExamAttempt.objects.filter(student=obj, violations__isnull=False).distinct().count()
        )
        has_disqualification = ExamAttempt.objects.filter(student=obj, is_disqualified=True).exists()
        suspicious_flag = has_disqualification or total >= 3

        return {
            "total_violations": total,
            "suspicious_flag": suspicious_flag,
            "attempts_with_violations": attempts_with_violations,
            "last_incident_at": last.created_at.isoformat() if last else None,
            "last_incident_type": last.violation_type if last else None,
            "last_incident_exam_title": last.attempt.exam.title if last else None,
        }

    def get_support_interaction(self, obj: StudentProfile) -> dict:
        user_issues = IssueReport.objects.filter(user=obj.user)
        open_count = user_issues.filter(is_resolved=False).count()
        resolved_count = user_issues.filter(is_resolved=True).count()
        latest = user_issues.order_by("-created_at").first()

        latest_payload = None
        if latest:
            latest_payload = {
                "id": str(latest.id),
                "subject": latest.subject,
                "description": latest.description,
                "category": latest.category,
                "is_resolved": latest.is_resolved,
                "admin_response": latest.admin_response,
                "created_at": latest.created_at.isoformat(),
                "updated_at": latest.updated_at.isoformat(),
            }
        return {
            "open_count": open_count,
            "resolved_count": resolved_count,
            "total_count": open_count + resolved_count,
            "latest": latest_payload,
        }

    def get_payment_history(self, obj: StudentProfile) -> list[dict]:
        from apps.payments.models import Purchase

        purchases = (
            Purchase.objects.filter(student=obj)
            .select_related("level")
            .prefetch_related("transactions")
            .order_by("-purchased_at")
        )

        result = []
        for purchase in purchases:
            successful_txn = next(
                (txn for txn in purchase.transactions.all() if txn.status == "success"),
                None,
            )
            latest_txn = successful_txn or next(iter(purchase.transactions.all()), None)
            transaction_id = None
            if latest_txn:
                transaction_id = latest_txn.razorpay_payment_id or latest_txn.razorpay_order_id

            result.append(
                {
                    "id": str(purchase.id),
                    "transaction_id": transaction_id,
                    "level": str(purchase.level_id) if purchase.level_id else None,
                    "level_name": purchase.level.name if purchase.level else None,
                    "amount": str(purchase.amount_paid),
                    "purchased_at": purchase.purchased_at.isoformat(),
                    "expires_at": purchase.expires_at.isoformat() if purchase.expires_at else None,
                    "status": purchase.status,
                    "payment_status": latest_txn.status if latest_txn else None,
                    "payment_method": "razorpay" if latest_txn else None,
                    "payment_gateway": "razorpay",
                    "extended_by_days": purchase.extended_by_days,
                    "is_valid": purchase.is_valid,
                }
            )
        return result

    def get_admin_action_history(self, obj: StudentProfile) -> list[dict]:
        logs = obj.admin_action_logs.select_related("admin_user", "level", "purchase")[:10]
        return list(AdminStudentActionLogSerializer(logs, many=True).data)


class AdminStudentUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False, max_length=150)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=15)
    gender = serializers.ChoiceField(required=False, choices=StudentProfile.Gender.choices)
    current_level = UUIDOrLegacyIntegerField(required=False)
    highest_cleared_level = UUIDOrLegacyIntegerField(required=False)

    def validate_email(self, value: str) -> str:
        value = value.lower()
        instance = self.context.get("instance")
        qs = User.objects.filter(email=value)
        if instance is not None:
            qs = qs.exclude(pk=instance.user_id)
        if qs.exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_phone(self, value: str) -> str | None:
        if not value:
            return None
        instance = self.context.get("instance")
        qs = User.objects.filter(phone=value)
        if instance is not None:
            qs = qs.exclude(pk=instance.user_id)
        if qs.exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value


class AdminStudentLevelActionSerializer(serializers.Serializer):
    level_id = UUIDOrLegacyIntegerField()
    reason = serializers.CharField()

    def validate_reason(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("reason field is required.")
        return value


class AdminStudentExtendValiditySerializer(AdminStudentLevelActionSerializer):
    extra_days = serializers.IntegerField(min_value=1)


class AdminStudentReminderSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AdminStudentActionLogSerializer(serializers.ModelSerializer):
    admin_email = serializers.EmailField(source="admin_user.email", read_only=True)
    level_name = serializers.CharField(source="level.name", read_only=True, default=None)

    class Meta:
        model = AdminStudentActionLog
        fields = [
            "id",
            "action_type",
            "admin_user",
            "admin_email",
            "level",
            "level_name",
            "purchase",
            "reason",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields


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

    def validate_email(self, value: str) -> str:
        return value.lower()


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

    def validate_email(self, value: str) -> str:
        return value.lower()


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)
    purpose = serializers.ChoiceField(
        choices=["verify", "password_reset"],
        default="verify",
    )

    def validate_email(self, value: str) -> str:
        return value.lower()


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
