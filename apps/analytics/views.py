import datetime

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
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

    @extend_schema(tags=["Analytics"], summary="Admin dashboard stats")
    def get(self, request):
        now = timezone.now()
        today = now.date()
        seven_days_ago = now - datetime.timedelta(days=7)
        thirty_days_ago = now - datetime.timedelta(days=30)

        # Total students
        total_students = StudentProfile.objects.count()

        # Total revenue (all time)
        total_revenue = Purchase.objects.filter(status="active").aggregate(total=Sum("amount_paid"))["total"] or 0

        # Active users (students with session activity in last 7 days)
        active_users = (
            SessionProgress.objects.filter(updated_at__gte=seven_days_ago).values("student").distinct().count()
        )

        # Exams passed today
        exams_passed_today = ExamAttempt.objects.filter(
            is_passed=True,
            submitted_at__date=today,
        ).count()

        # Open doubts
        open_doubts = DoubtTicket.objects.filter(status="open").count()

        # Recent doubts (last 10)
        recent_doubts = list(
            DoubtTicket.objects.select_related("student__user")
            .order_by("-created_at")[:10]
            .values(
                "id",
                "title",
                "status",
                "context_type",
                "created_at",
                student_name=Count("student__user__full_name"),
            )
        )
        # Use a simpler approach for recent doubts
        recent_doubt_qs = DoubtTicket.objects.select_related("student__user").order_by("-created_at")[:10]
        recent_doubts = [
            {
                "id": d.id,
                "student_name": d.student.user.full_name,
                "title": d.title,
                "status": d.status,
                "context_type": d.context_type,
                "created_at": d.created_at,
            }
            for d in recent_doubt_qs
        ]

        # Daily active users (last 30 days for graph)
        daily_active_users = list(
            SessionProgress.objects.filter(updated_at__gte=thirty_days_ago)
            .annotate(date=TruncDate("updated_at"))
            .values("date")
            .annotate(count=Count("student", distinct=True))
            .order_by("date")
        )

        # Streak retention buckets
        streak_data = self._calculate_streak_retention()

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

    def _calculate_streak_retention(self) -> dict:
        """Bucket students by current streak length."""
        today = timezone.now().date()
        students = StudentProfile.objects.all()[:500]

        buckets = {"0_days": 0, "1_3_days": 0, "4_7_days": 0, "8_plus_days": 0}

        for student in students:
            dates = list(
                SessionProgress.objects.filter(student=student)
                .values_list("updated_at__date", flat=True)
                .distinct()
                .order_by("-updated_at__date")[:30]
            )
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
