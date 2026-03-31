from __future__ import annotations

import datetime

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics
from rest_framework import serializers as drf_serializers
from rest_framework import status as http_status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course
from apps.doubts.models import DoubtTicket
from apps.exams.models import ExamAttempt
from apps.levels.models import Level
from apps.payments.models import Purchase
from apps.progress.models import CourseProgress, LevelProgress, SessionProgress
from apps.users.models import StudentProfile
from core.constants import ErrorMessage
from core.pagination import AnalyticsCursorPagination
from core.permissions import IsAdmin

from .models import DailyRevenue, LevelAnalytics
from .serializers import DailyRevenueSerializer, LevelAnalyticsSerializer


@extend_schema_view(
    list=extend_schema(tags=["Analytics"], summary="List daily revenue records"),
)
class RevenueListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = DailyRevenueSerializer
    queryset = DailyRevenue.objects.all()
    pagination_class = AnalyticsCursorPagination
    filterset_fields = ["date"]


@extend_schema_view(
    list=extend_schema(tags=["Analytics"], summary="List per-level analytics"),
)
class LevelAnalyticsListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = LevelAnalyticsSerializer
    queryset = LevelAnalytics.objects.select_related("level")
    pagination_class = AnalyticsCursorPagination
    filterset_fields = ["level", "date"]


class AdminDashboardView(APIView):
    """Aggregated admin dashboard stats endpoint."""

    permission_classes = [IsAdmin]

    @extend_schema(
        tags=["Analytics"],
        summary="Admin dashboard stats",
        responses={
            200: inline_serializer(
                "AdminDashboardResponse",
                fields={
                    "total_students": drf_serializers.IntegerField(),
                    "total_revenue": drf_serializers.CharField(),
                    "active_users": drf_serializers.IntegerField(),
                    "exams_passed_today": drf_serializers.IntegerField(),
                    "open_doubts": drf_serializers.IntegerField(),
                    "recent_doubts": drf_serializers.ListField(child=drf_serializers.DictField()),
                    "daily_active_users": drf_serializers.ListField(child=drf_serializers.DictField()),
                    "streak_retention": drf_serializers.DictField(),
                },
            )
        },
    )
    def get(self, request: Request) -> Response:
        now = timezone.now()
        today = now.date()
        seven_days_ago = now - datetime.timedelta(days=7)
        thirty_days_ago = now - datetime.timedelta(days=30)

        total_students: int = StudentProfile.objects.count()

        total_revenue = (
            Purchase.objects.filter(status=Purchase.Status.ACTIVE).aggregate(total=Sum("amount_paid"))["total"] or 0
        )

        active_users: int = (
            SessionProgress.objects.filter(updated_at__gte=seven_days_ago).values("student").distinct().count()
        )

        exams_passed_today: int = ExamAttempt.objects.filter(
            is_passed=True,
            submitted_at__date=today,
        ).count()

        open_doubts: int = DoubtTicket.objects.filter(status=DoubtTicket.Status.OPEN).count()

        recent_doubts: list[dict[str, object]] = [
            {
                "id": d.id,
                "student_name": d.student.user.full_name,
                "title": d.title,
                "status": d.status,
                "context_type": d.context_type,
                "created_at": d.created_at,
            }
            for d in DoubtTicket.objects.select_related("student__user").order_by("-created_at")[:10]
        ]

        daily_active_users: list[dict[str, object]] = list(
            SessionProgress.objects.filter(updated_at__gte=thirty_days_ago)
            .annotate(date=TruncDate("updated_at"))
            .values("date")
            .annotate(count=Count("student", distinct=True))
            .order_by("date")
        )

        streak_data = self._calculate_streak_retention(today)

        return Response(
            {
                "total_students": total_students,
                "total_revenue": str(total_revenue),
                "active_users": active_users,
                "exams_passed_today": exams_passed_today,
                "open_doubts": open_doubts,
                "recent_doubts": recent_doubts,
                "daily_active_users": daily_active_users,
                "streak_retention": streak_data,
            }
        )

    @staticmethod
    def _calculate_streak_retention(today: datetime.date) -> dict[str, int]:
        """Bucket students by current streak length using a single bulk query."""
        cutoff = today - datetime.timedelta(days=30)
        activity = (
            SessionProgress.objects.filter(updated_at__date__gte=cutoff)
            .values("student_id")
            .annotate(active_date=TruncDate("updated_at"))
            .values_list("student_id", "active_date")
            .distinct()
        )

        student_dates: dict[int, list[datetime.date]] = {}
        for student_id, active_date in activity:
            student_dates.setdefault(student_id, []).append(active_date)

        total_students: int = StudentProfile.objects.count()
        num_active = len(student_dates)

        buckets: dict[str, int] = {
            "0_days": total_students - num_active,
            "1_3_days": 0,
            "4_7_days": 0,
            "8_plus_days": 0,
        }

        for dates in student_dates.values():
            dates.sort(reverse=True)
            streak = 0
            expected = today
            for d in dates:
                if d == expected:
                    streak += 1
                    expected -= datetime.timedelta(days=1)
                elif d < expected:
                    break

            if streak == 0:
                buckets["0_days"] += 1
            elif streak <= 3:
                buckets["1_3_days"] += 1
            elif streak <= 7:
                buckets["4_7_days"] += 1
            else:
                buckets["8_plus_days"] += 1

        return buckets


class AdminLevelAnalyticsDetailView(APIView):
    """Detailed analytics for a single level."""

    permission_classes = [IsAdmin]

    @extend_schema(
        tags=["Analytics"],
        summary="Level analytics detail",
        parameters=[
            inline_serializer(
                "LevelAnalyticsDetailParams",
                fields={"days": drf_serializers.IntegerField(default=30, required=False)},
            )
        ],
        responses={
            200: inline_serializer(
                "AdminLevelAnalyticsDetailResponse",
                fields={
                    "level_id": drf_serializers.IntegerField(),
                    "level_name": drf_serializers.CharField(),
                    "students_enrolled": drf_serializers.IntegerField(),
                    "completion_rate": drf_serializers.FloatField(allow_null=True),
                    "exam_pass_rate": drf_serializers.FloatField(allow_null=True),
                    "average_score": drf_serializers.FloatField(allow_null=True),
                    "student_activity": drf_serializers.ListField(child=drf_serializers.DictField()),
                    "module_completion_rate": drf_serializers.ListField(child=drf_serializers.DictField()),
                },
            )
        },
    )
    def get(self, request: Request, level_pk: int) -> Response:
        try:
            level = Level.objects.get(pk=level_pk)
        except Level.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=http_status.HTTP_404_NOT_FOUND)

        # Stat cards
        students_enrolled = (
            Purchase.objects.filter(level=level, status=Purchase.Status.ACTIVE).values("student").distinct().count()
        )

        total_level_students = LevelProgress.objects.filter(level=level).count()
        exam_passed_count = LevelProgress.objects.filter(level=level, status=LevelProgress.Status.EXAM_PASSED).count()
        completion_rate = round((exam_passed_count / total_level_students) * 100, 2) if total_level_students else None

        level_final_attempts = ExamAttempt.objects.filter(
            exam__level=level,
            exam__exam_type="level_final",
            status=ExamAttempt.Status.SUBMITTED,
        )
        total_exam_attempts = level_final_attempts.count()
        exam_passes = level_final_attempts.filter(is_passed=True).count()
        exam_pass_rate = round((exam_passes / total_exam_attempts) * 100, 2) if total_exam_attempts else None

        avg_score = level_final_attempts.aggregate(avg=Avg("score"))["avg"]
        average_score = round(float(avg_score), 2) if avg_score is not None else None

        # Student activity chart
        days = min(int(request.query_params.get("days", 30)), 90)
        cutoff = timezone.now() - datetime.timedelta(days=days)
        student_activity: list[dict[str, object]] = list(
            SessionProgress.objects.filter(
                session__week__course__level=level,
                updated_at__gte=cutoff,
            )
            .annotate(date=TruncDate("updated_at"))
            .values("date")
            .annotate(active_students=Count("student", distinct=True))
            .order_by("date")
        )

        # Module (course) completion — single annotated query
        courses_with_stats = (
            Course.objects.filter(level=level, is_active=True)
            .annotate(
                total_students=Count("progress_records"),
                completed_students=Count(
                    "progress_records",
                    filter=Q(progress_records__status=CourseProgress.Status.COMPLETED),
                ),
            )
            .values("id", "title", "total_students", "completed_students")
        )
        module_completion: list[dict[str, object]] = [
            {
                "course_id": c["id"],
                "course_title": c["title"],
                "completion_rate": (
                    round((c["completed_students"] / c["total_students"]) * 100, 2) if c["total_students"] else 0
                ),
                "total_students": c["total_students"],
                "completed_students": c["completed_students"],
            }
            for c in courses_with_stats
        ]

        return Response(
            {
                "level_id": level.id,
                "level_name": level.name,
                "students_enrolled": students_enrolled,
                "completion_rate": completion_rate,
                "exam_pass_rate": exam_pass_rate,
                "average_score": average_score,
                "student_activity": student_activity,
                "module_completion_rate": module_completion,
            }
        )
