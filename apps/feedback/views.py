from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import ErrorMessage
from core.decorators import swagger_safe
from core.pagination import LargePagination, SmallPagination
from core.permissions import IsAdmin, IsStudent
from core.throttling import SafeScopedRateThrottle

from .models import SessionFeedback
from .serializers import SessionFeedbackSerializer
from .services import FeedbackService


class SubmitFeedbackView(APIView):
    permission_classes = [IsStudent]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "feedback"

    @extend_schema(request=SessionFeedbackSerializer, responses={201: SessionFeedbackSerializer}, tags=["Feedback"])
    def post(self, request, session_pk):
        serializer = SessionFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feedback, error = FeedbackService.submit(
            request.user.student_profile,
            session_pk,
            serializer.validated_data,
        )
        if error == ErrorMessage.SESSION_NOT_FOUND:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)
        if error == ErrorMessage.PURCHASE_REQUIRED_FOR_FEEDBACK:
            return Response({"detail": error}, status=status.HTTP_403_FORBIDDEN)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(SessionFeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(tags=["Feedback"], summary="List my feedback"),
)
class StudentFeedbackListView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = SessionFeedbackSerializer
    pagination_class = SmallPagination
    filterset_fields = ["session", "overall_rating"]

    @swagger_safe(SessionFeedback)
    def get_queryset(self):
        return SessionFeedback.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).select_related("session")


@extend_schema_view(
    list=extend_schema(tags=["Feedback"], summary="List all feedback (admin)"),
)
class AdminFeedbackListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = SessionFeedbackSerializer
    queryset = SessionFeedback.objects.select_related("student__user", "session")
    pagination_class = LargePagination
    filterset_fields = ["session", "overall_rating", "difficulty_rating", "clarity_rating"]
    search_fields = ["student__user__email"]
