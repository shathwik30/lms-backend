from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.serializers import CourseSerializer, SessionListSerializer
from apps.levels.serializers import LevelListSerializer
from core.constants import ErrorMessage, SearchConstants
from core.throttling import SafeScopedRateThrottle

from .services import SearchService


class SearchView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "search"

    @extend_schema(
        tags=["Search"],
        parameters=[
            OpenApiParameter(name="q", description="Search query", required=True, type=str),
            OpenApiParameter(name="level", description="Filter by level ID", required=False, type=int),
            OpenApiParameter(name="week", description="Filter by week ID", required=False, type=int),
        ],
        responses={
            200: inline_serializer(
                "SearchResponse",
                fields={
                    "levels": LevelListSerializer(many=True),
                    "courses": CourseSerializer(many=True),
                    "sessions": SessionListSerializer(many=True),
                    "questions_count": drf_serializers.IntegerField(),
                },
            )
        },
    )
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if len(query) < SearchConstants.MIN_QUERY_LENGTH:
            return Response(
                {"detail": ErrorMessage.SEARCH_QUERY_TOO_SHORT},
                status=status.HTTP_400_BAD_REQUEST,
            )

        level_id = request.query_params.get("level")
        week_id = request.query_params.get("week")

        results = SearchService.search(query, level_id, week_id)

        return Response(
            {
                "levels": LevelListSerializer(results["levels"], many=True).data,
                "courses": CourseSerializer(results["courses"], many=True).data,
                "sessions": SessionListSerializer(results["sessions"], many=True).data,
                "questions_count": results["questions_count"],
            }
        )
