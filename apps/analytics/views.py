from __future__ import annotations

import datetime

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics
from rest_framework import serializers as drf_serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.doubts.models import DoubtTicket
from apps.exams.models import ExamAttempt
from apps.payments.models import Purchase
from apps.progress.models import SessionProgress
from apps.users.models import StudentProfile
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
