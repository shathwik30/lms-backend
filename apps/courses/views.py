from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import ErrorMessage, SuccessMessage
from core.exceptions import PurchaseRequired, SessionNotAccessible
from core.pagination import SmallPagination
from core.permissions import IsAdmin, IsStudent

from .models import Bookmark, Course, Session
from .serializers import (
    BookmarkSerializer,
    CourseSerializer,
    SessionDetailSerializer,
    SessionListSerializer,
)
from .services import CourseAccessService

# ── Student views ──


class LevelCourseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: CourseSerializer(many=True)})
    def get(self, request, level_pk):
        courses = Course.objects.filter(level_id=level_pk, is_active=True).select_related("level")
        return Response(CourseSerializer(courses, many=True).data)


@extend_schema_view(
    list=extend_schema(tags=["Courses"], summary="List sessions for a course"),
)
class CourseSessionsView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = SessionListSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Session.objects.none()
        course_id = self.kwargs["course_pk"]
        profile = self.request.user.student_profile  # type: ignore[union-attr]

        if not CourseAccessService.has_course_access(profile, course_id):
            raise PurchaseRequired()

        try:
            course = Course.objects.get(pk=course_id)
        except Course.DoesNotExist as exc:
            raise PurchaseRequired() from exc
        return Session.objects.filter(
            week__course=course,
            is_active=True,
        ).select_related("week")


class SessionDetailView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(responses={200: SessionDetailSerializer})
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

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Bookmark.objects.none()
        return Bookmark.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).select_related("session__week")

    def perform_create(self, serializer):
        serializer.save(student=self.request.user.student_profile)  # type: ignore[union-attr]


class BookmarkDeleteView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(responses={204: None})
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
    serializer_class = CourseSerializer
    queryset = Course.objects.select_related("level")
    filterset_fields = ["level", "is_active"]


@extend_schema_view(
    retrieve=extend_schema(tags=["Courses"], summary="Get course details (admin)"),
    update=extend_schema(tags=["Courses"], summary="Update a course"),
    partial_update=extend_schema(tags=["Courses"], summary="Partially update a course"),
    destroy=extend_schema(tags=["Courses"], summary="Delete a course"),
)
class AdminCourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    serializer_class = CourseSerializer
    queryset = Course.objects.all()


@extend_schema_view(
    list=extend_schema(tags=["Courses"], summary="List sessions (admin)"),
    create=extend_schema(tags=["Courses"], summary="Create a session"),
)
class AdminSessionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = SessionDetailSerializer
    queryset = Session.objects.select_related("week__course__level")
    filterset_fields = ["week", "is_active", "session_type"]


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
