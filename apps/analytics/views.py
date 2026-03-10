from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics

from core.pagination import LargePagination
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
    pagination_class = LargePagination
    filterset_fields = ["date"]


@extend_schema_view(
    list=extend_schema(tags=["Analytics"], summary="List per-level analytics"),
)
class LevelAnalyticsListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = LevelAnalyticsSerializer
    queryset = LevelAnalytics.objects.select_related("level")
    pagination_class = LargePagination
    filterset_fields = ["level", "date"]
