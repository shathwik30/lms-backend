from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics, status
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import ErrorMessage, ProgressConstants
from core.permissions import IsStudent
from core.throttling import SafeScopedRateThrottle

from .models import LevelProgress, SessionProgress
from .serializers import (
    LeaderboardEntrySerializer,
    LevelProgressSerializer,
    SessionProgressSerializer,
    UpdateProgressSerializer,
)
from .services import ProgressService


class UpdateSessionProgressView(APIView):
    permission_classes = [IsStudent]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "progress_update"

    @extend_schema(request=UpdateProgressSerializer, responses={200: SessionProgressSerializer})
    def post(self, request, session_pk):
        serializer = UpdateProgressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        progress, error = ProgressService.update_session_progress(
            request.user.student_profile,
            session_pk,
            serializer.validated_data["watched_seconds"],
        )
        if error:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)

        return Response(SessionProgressSerializer(progress).data)


@extend_schema_view(
    list=extend_schema(tags=["Progress"], summary="List session progress for a level"),
)
class SessionProgressListView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = SessionProgressSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SessionProgress.objects.none()
        level_pk = self.kwargs.get("level_pk")
        return SessionProgress.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
            session__week__level_id=level_pk,
        ).select_related("session")


@extend_schema_view(
    list=extend_schema(tags=["Progress"], summary="List level progress"),
)
class LevelProgressListView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = LevelProgressSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return LevelProgress.objects.none()
        return LevelProgress.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).select_related("level")


class DashboardView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(
        responses={
            200: inline_serializer(
                "DashboardResponse",
                fields={
                    "current_level": drf_serializers.DictField(),
                    "level_progress": LevelProgressSerializer(many=True),
                    "next_action": drf_serializers.CharField(),
                    "message": drf_serializers.CharField(),
                },
            )
        }
    )
    def get(self, request):
        data = ProgressService.get_dashboard(request.user.student_profile)
        return Response(
            {
                "current_level": data["current_level"],
                "level_progress": LevelProgressSerializer(data["level_progress"], many=True).data,
                "next_action": data["next_action"],
                "message": data["message"],
            }
        )


class CalendarView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="year", type=int, required=True),
            OpenApiParameter(name="month", type=int, required=True),
        ],
        responses={
            200: inline_serializer(
                "CalendarResponse",
                fields={
                    "year": drf_serializers.IntegerField(),
                    "month": drf_serializers.IntegerField(),
                    "active_dates": drf_serializers.ListField(child=drf_serializers.DictField()),
                },
            )
        },
    )
    def get(self, request):
        try:
            year = int(request.query_params["year"])
            month = int(request.query_params["month"])
        except (KeyError, ValueError):
            return Response(
                {"detail": ErrorMessage.YEAR_MONTH_REQUIRED},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (1 <= month <= 12) or not (2000 <= year <= 2100):
            return Response(
                {"detail": ErrorMessage.YEAR_MONTH_REQUIRED},
                status=status.HTTP_400_BAD_REQUEST,
            )

        active_dates = ProgressService.get_calendar_data(
            request.user.student_profile,
            year,
            month,
        )
        return Response({"year": year, "month": month, "active_dates": active_dates})


class LeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="level", description="Filter by level ID", required=False, type=int),
            OpenApiParameter(
                name="limit", description="Number of results (default 20, max 50)", required=False, type=int
            ),
        ],
        responses={
            200: inline_serializer(
                "LeaderboardResponse",
                fields={
                    "leaderboard": LeaderboardEntrySerializer(many=True),
                    "my_rank": drf_serializers.IntegerField(allow_null=True),
                },
            )
        },
    )
    def get(self, request):
        try:
            limit = min(
                int(request.query_params.get("limit", ProgressConstants.DEFAULT_LEADERBOARD_LIMIT)),
                ProgressConstants.MAX_LEADERBOARD_LIMIT,
            )
        except ValueError:
            limit = ProgressConstants.DEFAULT_LEADERBOARD_LIMIT
        level_id = request.query_params.get("level")

        data = ProgressService.get_leaderboard(request.user, level_id, limit)
        return Response(data)
