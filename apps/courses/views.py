from django.db.models import Prefetch
from django.http import Http404
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import ErrorMessage, SuccessMessage
from core.decorators import swagger_safe
from core.exceptions import PurchaseRequired, SessionNotAccessible
from core.pagination import LargePagination, SmallPagination
from core.permissions import IsAdmin, IsStudent

from .models import Bookmark, Course, Session
from .serializers import (
    AdminCourseSerializer,
    BookmarkSerializer,
    CourseSerializer,
    SessionDetailSerializer,
)
from .services import CourseAccessService

# ── Student views ──


class LevelCourseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: CourseSerializer(many=True)}, tags=["Courses"])
    def get(self, request, level_pk):
        courses = Course.objects.filter(level_id=level_pk, is_active=True).select_related("level")
        return Response(CourseSerializer(courses, many=True).data)


class CourseCurriculumView(APIView):
    """
    Returns the full course curriculum: weeks in order, each with their
    sessions in order. Every session includes lock status and the student's
    progress so the frontend can render the course map in a single request.

    Lock rule: a session is locked when any earlier session (across all prior
    weeks and within the current week) has not yet been completed.

    Queries: 3 total — weeks+sessions, progress, course lookup.
    """

    permission_classes = [IsStudent]

    @extend_schema(
        tags=["Courses"],
        summary="Get structured course curriculum with per-session lock & progress",
        responses={
            200: inline_serializer(
                "CourseCurriculumResponse",
                fields={
                    "course_id": serializers.IntegerField(),
                    "course_title": serializers.CharField(),
                    "weeks": serializers.ListField(child=serializers.DictField()),
                },
            )
        },
    )
    def get(self, request, course_pk):
        from apps.levels.models import Week
        from apps.progress.models import SessionProgress

        profile = request.user.student_profile

        if not CourseAccessService.has_course_access(profile, course_pk):
            raise PurchaseRequired()

        try:
            course = Course.objects.select_related("level").get(pk=course_pk, is_active=True)
        except Course.DoesNotExist:
            raise Http404 from None

        # Query 1: weeks + sessions (2 queries via prefetch, counts as 1 round-trip block)
        weeks = list(
            Week.objects.filter(course=course, is_active=True)
            .order_by("order")
            .prefetch_related(
                Prefetch(
                    "sessions",
                    queryset=Session.objects.filter(is_active=True).order_by("order").defer("markdown_content"),
                    to_attr="active_sessions",
                )
            )
        )

        # Query 2: all progress for this student on this course in one shot
        all_session_ids = [s.id for w in weeks for s in w.active_sessions]
        progress_map: dict[int, SessionProgress] = {
            sp.session_id: sp
            for sp in SessionProgress.objects.filter(
                student=profile,
                session_id__in=all_session_ids,
            )
        }

        # Compute is_locked by walking the flat ordered session list.
        # A session is locked iff any preceding session is incomplete.
        all_prev_complete = True
        lock_map: dict[int, bool] = {}
        for week in weeks:
            for session in week.active_sessions:
                lock_map[session.id] = not all_prev_complete
                sp = progress_map.get(session.id)
                if not (sp and sp.is_completed):
                    all_prev_complete = False

        # Build structured response
        result_weeks = []
        for week in weeks:
            sessions_out = []
            week_complete = True

            for session in week.active_sessions:
                sp = progress_map.get(session.id)
                is_completed = bool(sp and sp.is_completed)
                if not is_completed:
                    week_complete = False

                sessions_out.append(
                    {
                        "id": session.id,
                        "title": session.title,
                        "description": session.description,
                        "order": session.order,
                        "session_type": session.session_type,
                        "resource_type": session.resource_type or None,
                        "duration_seconds": session.duration_seconds,
                        "thumbnail_url": session.thumbnail_url or None,
                        "exam_id": session.exam_id,
                        # lock / progress
                        "is_locked": lock_map[session.id],
                        "is_completed": is_completed,
                        "watched_seconds": sp.watched_seconds if sp else 0,
                        "completed_at": sp.completed_at.isoformat() if sp and sp.completed_at else None,
                        "is_exam_passed": sp.is_exam_passed if sp else None,
                    }
                )

            result_weeks.append(
                {
                    "id": week.id,
                    "name": week.name,
                    "order": week.order,
                    "is_complete": week_complete and len(sessions_out) > 0,
                    "sessions_count": len(sessions_out),
                    "sessions": sessions_out,
                }
            )

        return Response(
            {
                "course_id": course.id,
                "course_title": course.title,
                "weeks": result_weeks,
            }
        )


class SessionDetailView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(responses={200: SessionDetailSerializer}, tags=["Courses"])
    def get(self, request, pk):
        try:
            session = Session.objects.select_related("week__course__level").get(pk=pk, is_active=True)
        except Session.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        profile = request.user.student_profile
        if not CourseAccessService.has_level_access(profile, session.week.course.level):
            raise PurchaseRequired()

        if not CourseAccessService.is_session_accessible(profile, session):
            raise SessionNotAccessible()

        return Response(SessionDetailSerializer(session).data)


class CompleteResourceSessionView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(
        request=None,
        responses={
            200: inline_serializer(
                "ResourceSessionCompleteResponse",
                fields={
                    "detail": serializers.CharField(),
                },
            ),
        },
        tags=["Courses"],
        summary="Mark resource session as completed",
    )
    def post(self, request, pk):
        from apps.progress.services import ProgressService

        profile = request.user.student_profile
        progress, error = ProgressService.complete_resource_session(profile, pk)
        if error:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)
        return Response({"detail": SuccessMessage.RESOURCE_SESSION_COMPLETED})


# ── Bookmark views ──


@extend_schema_view(
    list=extend_schema(tags=["Courses"], summary="List my bookmarks"),
    create=extend_schema(tags=["Courses"], summary="Bookmark a session"),
)
class BookmarkListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsStudent]
    serializer_class = BookmarkSerializer
    pagination_class = SmallPagination

    @swagger_safe(Bookmark)
    def get_queryset(self):
        return Bookmark.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).select_related("session__week")

    def perform_create(self, serializer):
        serializer.save(student=self.request.user.student_profile)  # type: ignore[union-attr]


class BookmarkDeleteView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(responses={204: None}, tags=["Courses"])
    def delete(self, request, pk):
        try:
            bookmark = Bookmark.objects.get(
                pk=pk,
                student=request.user.student_profile,
            )
        except Bookmark.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        bookmark.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Admin views ──


@extend_schema_view(
    list=extend_schema(tags=["Courses"], summary="List courses (admin)"),
    create=extend_schema(tags=["Courses"], summary="Create a course"),
)
class AdminCourseListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdmin]
    queryset = Course.objects.select_related("level").order_by("-created_at")
    pagination_class = LargePagination
    filterset_fields = ["level", "is_active"]

    def get_serializer_class(self) -> type[CourseSerializer] | type[AdminCourseSerializer]:
        if self.request.method == "POST":
            return CourseSerializer
        return AdminCourseSerializer


@extend_schema_view(
    retrieve=extend_schema(tags=["Courses"], summary="Get course details (admin)"),
    update=extend_schema(tags=["Courses"], summary="Update a course"),
    partial_update=extend_schema(tags=["Courses"], summary="Partially update a course"),
    destroy=extend_schema(tags=["Courses"], summary="Delete a course"),
)
class AdminCourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    queryset = Course.objects.select_related("level")

    def get_serializer_class(self) -> type[CourseSerializer] | type[AdminCourseSerializer]:
        if self.request.method == "GET":
            return AdminCourseSerializer
        return CourseSerializer


@extend_schema_view(
    list=extend_schema(tags=["Courses"], summary="List sessions (admin)"),
    create=extend_schema(tags=["Courses"], summary="Create a session"),
)
class AdminSessionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = SessionDetailSerializer
    filterset_fields = ["week", "is_active", "session_type"]

    @swagger_safe(Session)
    def get_queryset(self):
        if self.request.method == "GET":
            return Session.objects.select_related("week__course__level").defer("markdown_content")
        return Session.objects.select_related("week__course__level")


@extend_schema_view(
    retrieve=extend_schema(tags=["Courses"], summary="Get session details (admin)"),
    update=extend_schema(tags=["Courses"], summary="Update a session"),
    partial_update=extend_schema(tags=["Courses"], summary="Partially update a session"),
    destroy=extend_schema(tags=["Courses"], summary="Delete a session"),
)
class AdminSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    serializer_class = SessionDetailSerializer
    queryset = Session.objects.all()
