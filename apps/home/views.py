from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course
from apps.courses.serializers import CourseSerializer
from core.permissions import IsAdmin

from .models import Banner
from .serializers import BannerReadSerializer, BannerSerializer


@extend_schema_view(
    list=extend_schema(tags=["Home"], summary="List active banners"),
)
@method_decorator(cache_page(settings.CACHE_TTL_MEDIUM), name="dispatch")
class BannerListView(generics.ListAPIView):
    """Public list of active banners for the home screen."""

    permission_classes = [AllowAny]
    serializer_class = BannerReadSerializer
    queryset = Banner.objects.filter(is_active=True)
    pagination_class = None


@method_decorator(cache_page(settings.CACHE_TTL_SHORT), name="dispatch")
class FeaturedCoursesView(APIView):
    """Return featured/active courses for the home screen."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: CourseSerializer(many=True)})
    def get(self, request):
        courses = Course.objects.filter(is_active=True).select_related("level")[:10]
        return Response(CourseSerializer(courses, many=True).data)


# ── Admin views ──


@extend_schema_view(
    list=extend_schema(tags=["Home"], summary="List all banners (admin)"),
    create=extend_schema(tags=["Home"], summary="Create a banner"),
)
class AdminBannerListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = BannerSerializer
    queryset = Banner.objects.all()
    pagination_class = None


@extend_schema_view(
    retrieve=extend_schema(tags=["Home"], summary="Get banner details (admin)"),
    update=extend_schema(tags=["Home"], summary="Update a banner"),
    partial_update=extend_schema(tags=["Home"], summary="Partially update a banner"),
    destroy=extend_schema(tags=["Home"], summary="Delete a banner"),
)
class AdminBannerDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    serializer_class = BannerSerializer
    queryset = Banner.objects.all()
