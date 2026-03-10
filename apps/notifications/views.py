from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics, status
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import ErrorMessage, SuccessMessage
from core.pagination import SmallPagination

from .models import Notification
from .serializers import NotificationSerializer
from .services import NotificationService


@extend_schema_view(
    list=extend_schema(tags=["Notifications"], summary="List my notifications"),
)
class NotificationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = SmallPagination
    filterset_fields = ["is_read", "notification_type"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user)  # type: ignore[misc]


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        request=None,
        responses={
            200: inline_serializer(
                "MarkReadResponse",
                fields={
                    "detail": drf_serializers.CharField(),
                },
            )
        },
    )
    def patch(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        NotificationService.mark_read(notification)
        return Response({"detail": SuccessMessage.MARKED_AS_READ})


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        request=None,
        responses={
            200: inline_serializer(
                "MarkAllReadResponse",
                fields={
                    "detail": drf_serializers.CharField(),
                    "count": drf_serializers.IntegerField(),
                },
            )
        },
    )
    def post(self, request):
        count = NotificationService.mark_all_read(request.user)
        return Response({"detail": SuccessMessage.ALL_NOTIFICATIONS_READ, "count": count})


class NotificationDeleteAllView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        request=None,
        responses={
            200: inline_serializer(
                "DeleteAllResponse",
                fields={
                    "detail": drf_serializers.CharField(),
                    "count": drf_serializers.IntegerField(),
                },
            )
        },
    )
    def delete(self, request):
        count = NotificationService.delete_all(request.user)
        return Response({"detail": SuccessMessage.ALL_NOTIFICATIONS_CLEARED, "count": count})


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        responses={
            200: inline_serializer(
                "UnreadCountResponse",
                fields={
                    "unread_count": drf_serializers.IntegerField(),
                },
            )
        },
    )
    def get(self, request):
        count = NotificationService.unread_count(request.user)
        return Response({"unread_count": count})


class NotificationDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None}, tags=["Notifications"], summary="Delete a notification")
    def delete(self, request, pk):
        success, error = NotificationService.delete_one(request.user, pk)
        if not success:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
