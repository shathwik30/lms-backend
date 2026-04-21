from django.conf import settings
from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course
from apps.courses.serializers import CourseSerializer
from apps.exams.models import Exam, ExamAttempt
from apps.levels.models import Level
from core.permissions import IsAdmin
from core.services.eligibility import EligibilityService

from .models import Banner
from .serializers import BannerReadSerializer, BannerSerializer, HomeLevelExamSerializer


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

    @extend_schema(responses={200: CourseSerializer(many=True)}, tags=["Home"])
    def get(self, request):
        courses = Course.objects.filter(is_active=True).select_related("level")[:10]
        return Response(CourseSerializer(courses, many=True).data)


class LevelExamsView(APIView):
    """Active exams for a level, grouped by type, for the home screen.

    Authenticated students also receive per-exam attempt status
    (is_eligible, is_passed, best_score, last_attempt_status, attempts_count).
    """

    permission_classes = [AllowAny]

    _EXAM_TYPE_ORDER = Case(
        When(exam_type=Exam.ExamType.ONBOARDING, then=Value(0)),
        When(exam_type=Exam.ExamType.WEEKLY, then=Value(1)),
        When(exam_type=Exam.ExamType.LEVEL_FINAL, then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )

    @extend_schema(responses={200: HomeLevelExamSerializer(many=True)}, tags=["Home"])
    def get(self, request, level_id):
        level = get_object_or_404(Level, pk=level_id, is_active=True)

        exams = list(
            Exam.objects.filter(level=level, is_active=True)
            .select_related("level", "week", "course")
            .annotate(_type_order=self._EXAM_TYPE_ORDER)
            .order_by("_type_order", "week__order", "created_at")
        )

        context = {"request": request}
        profile = getattr(request.user, "student_profile", None) if request.user.is_authenticated else None
        if profile is not None:
            context["attempt_stats"] = self._build_attempt_stats(profile, exams)
            context["eligibility_map"] = {
                exam.id: EligibilityService.can_attempt_exam(profile, exam) for exam in exams
            }

        return Response(HomeLevelExamSerializer(exams, many=True, context=context).data)

    @staticmethod
    def _build_attempt_stats(profile, exams):
        exam_ids = [exam.id for exam in exams]
        if not exam_ids:
            return {}

        stats: dict = {
            exam_id: {"count": 0, "best_score": None, "is_passed": False, "last_status": None}
            for exam_id in exam_ids
        }
        latest_started: dict = {}
        attempts = ExamAttempt.objects.filter(student=profile, exam_id__in=exam_ids).only(
            "id", "exam_id", "status", "score", "is_passed", "started_at"
        )
        for attempt in attempts:
            entry = stats[attempt.exam_id]
            entry["count"] += 1
            if attempt.score is not None and (entry["best_score"] is None or attempt.score > entry["best_score"]):
                entry["best_score"] = attempt.score
            if attempt.is_passed:
                entry["is_passed"] = True
            if attempt.exam_id not in latest_started or attempt.started_at > latest_started[attempt.exam_id]:
                latest_started[attempt.exam_id] = attempt.started_at
                entry["last_status"] = attempt.status
        return stats


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
