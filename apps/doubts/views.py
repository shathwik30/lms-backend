from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import ErrorMessage
from core.decorators import swagger_safe
from core.pagination import LargePagination, SmallPagination
from core.permissions import IsAdmin, IsStudent
from core.throttling import SafeScopedRateThrottle

from .models import DoubtTicket
from .serializers import (
    AdminAssignDoubtSerializer,
    AdminBonusMarksSerializer,
    CreateDoubtSerializer,
    DoubtReplySerializer,
    DoubtTicketDetailSerializer,
    DoubtTicketListSerializer,
    UpdateDoubtStatusSerializer,
)
from .services import DoubtService

# ── Student views ──


@extend_schema_view(
    list=extend_schema(tags=["Doubts"], summary="List my doubt tickets"),
    create=extend_schema(tags=["Doubts"], summary="Create a doubt ticket"),
)
class StudentDoubtListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsStudent]
    pagination_class = SmallPagination
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "doubt_create"
    filterset_fields = ["status"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreateDoubtSerializer
        return DoubtTicketListSerializer

    @swagger_safe(DoubtTicket)
    def get_queryset(self):
        return DoubtTicket.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).prefetch_related("replies")

    def perform_create(self, serializer):
        profile = self.request.user.student_profile  # type: ignore[union-attr]
        DoubtService.validate_doubt_access(
            profile,
            serializer.validated_data.get("context_type"),
            serializer.validated_data,
        )
        serializer.save(student=profile)


@extend_schema_view(
    retrieve=extend_schema(tags=["Doubts"], summary="Get doubt ticket details"),
)
class StudentDoubtDetailView(generics.RetrieveAPIView):
    permission_classes = [IsStudent]
    serializer_class = DoubtTicketDetailSerializer

    @swagger_safe(DoubtTicket)
    def get_queryset(self):
        return DoubtTicket.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).prefetch_related("replies__author")


class StudentDoubtReplyView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(request=DoubtReplySerializer, responses={201: DoubtReplySerializer}, tags=["Doubts"])
    def post(self, request, pk):
        try:
            ticket = DoubtTicket.objects.get(
                pk=pk,
                student=request.user.student_profile,
            )
        except DoubtTicket.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        error = DoubtService.validate_reply_allowed(ticket)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        serializer = DoubtReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(ticket=ticket, author=request.user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ── Admin views ──


@extend_schema_view(
    list=extend_schema(tags=["Doubts"], summary="List all doubt tickets (admin)"),
)
class AdminDoubtListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = DoubtTicketListSerializer
    pagination_class = LargePagination
    queryset = DoubtTicket.objects.select_related(
        "student__user",
        "session__week__course__level",
        "exam_question__exam__level",
        "exam_question__exam__course",
    ).prefetch_related("replies")
    filterset_fields = ["status", "context_type", "assigned_to"]
    search_fields = ["title", "student__user__email"]


@extend_schema_view(
    retrieve=extend_schema(tags=["Doubts"], summary="Get doubt ticket details (admin)"),
)
class AdminDoubtDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdmin]
    serializer_class = DoubtTicketDetailSerializer
    queryset = DoubtTicket.objects.prefetch_related("replies__author")


class AdminDoubtReplyView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(request=DoubtReplySerializer, responses={201: DoubtReplySerializer}, tags=["Doubts"])
    def post(self, request, pk):
        try:
            ticket = DoubtTicket.objects.get(pk=pk)
        except DoubtTicket.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        error = DoubtService.validate_reply_allowed(ticket)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        serializer = DoubtReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = serializer.save(ticket=ticket, author=request.user)

        DoubtService.admin_reply(ticket, request.user, reply)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminAssignDoubtView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(request=AdminAssignDoubtSerializer, responses={200: DoubtTicketDetailSerializer}, tags=["Doubts"])
    def patch(self, request, pk):
        try:
            ticket = DoubtTicket.objects.get(pk=pk)
        except DoubtTicket.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminAssignDoubtSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result, error = DoubtService.assign_ticket(
            ticket,
            serializer.validated_data["assigned_to"],
        )
        if error == ErrorMessage.USER_NOT_FOUND:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DoubtTicketDetailSerializer(result).data)


class AdminDoubtStatusView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        request=UpdateDoubtStatusSerializer,
        responses={200: DoubtTicketDetailSerializer},
        tags=["Doubts"],
    )
    def patch(self, request, pk):
        try:
            ticket = DoubtTicket.objects.get(pk=pk)
        except DoubtTicket.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        serializer = UpdateDoubtStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result, error = DoubtService.update_status(
            ticket,
            serializer.validated_data["status"],
        )
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DoubtTicketDetailSerializer(result).data)


class AdminBonusMarksView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(request=AdminBonusMarksSerializer, responses={200: DoubtTicketDetailSerializer}, tags=["Doubts"])
    def patch(self, request, pk):
        try:
            ticket = DoubtTicket.objects.get(pk=pk)
        except DoubtTicket.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminBonusMarksSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = DoubtService.update_bonus_marks(
            ticket,
            serializer.validated_data["bonus_marks"],
        )
        return Response(DoubtTicketDetailSerializer(result).data)
