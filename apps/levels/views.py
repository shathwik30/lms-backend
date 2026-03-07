from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.permissions import AllowAny

from core.permissions import IsAdmin

from .models import Level, Week
from .serializers import LevelDetailSerializer, LevelListSerializer, WeekSerializer

# ── Public views ──


@extend_schema_view(
    list=extend_schema(tags=["Levels"], summary="List active levels"),
)
@method_decorator(cache_page(settings.CACHE_TTL_MEDIUM), name="dispatch")
class LevelListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = LevelListSerializer
    queryset = Level.objects.filter(is_active=True).prefetch_related("courses")
    pagination_class = None


@extend_schema_view(
    retrieve=extend_schema(tags=["Levels"], summary="Get level details"),
)
@method_decorator(cache_page(settings.CACHE_TTL_MEDIUM), name="dispatch")
class LevelDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = LevelDetailSerializer
    queryset = Level.objects.filter(is_active=True).prefetch_related("courses")


# ── Admin views ──


@extend_schema_view(
    list=extend_schema(tags=["Levels"], summary="List all levels (admin)"),
    create=extend_schema(tags=["Levels"], summary="Create a level"),
)
class AdminLevelListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = LevelDetailSerializer
    queryset = Level.objects.prefetch_related("courses")
    pagination_class = None


@extend_schema_view(
    retrieve=extend_schema(tags=["Levels"], summary="Get level details (admin)"),
    update=extend_schema(tags=["Levels"], summary="Update a level"),
    partial_update=extend_schema(tags=["Levels"], summary="Partially update a level"),
    destroy=extend_schema(tags=["Levels"], summary="Delete a level"),
)
class AdminLevelDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    serializer_class = LevelDetailSerializer
    queryset = Level.objects.all()


@extend_schema_view(
    list=extend_schema(tags=["Courses"], summary="List weeks for a course (admin)"),
    create=extend_schema(tags=["Courses"], summary="Create a week in a course"),
)
class AdminWeekListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = WeekSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Week.objects.none()
        return Week.objects.filter(course_id=self.kwargs["course_pk"])

    def perform_create(self, serializer):
        serializer.save(course_id=self.kwargs["course_pk"])


@extend_schema_view(
    retrieve=extend_schema(tags=["Courses"], summary="Get week details (admin)"),
    update=extend_schema(tags=["Courses"], summary="Update a week"),
    partial_update=extend_schema(tags=["Courses"], summary="Partially update a week"),
    destroy=extend_schema(tags=["Courses"], summary="Delete a week"),
)
class AdminWeekDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    serializer_class = WeekSerializer
    queryset = Week.objects.all()
