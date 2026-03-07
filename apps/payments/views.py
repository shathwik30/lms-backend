import logging

from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics, status
from rest_framework import serializers as drf_serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import ErrorMessage
from core.pagination import LargePagination
from core.permissions import IsAdmin, IsStudent
from core.throttling import SafeScopedRateThrottle

from .models import PaymentTransaction, Purchase
from .serializers import (
    AdminExtendValiditySerializer,
    InitiatePaymentSerializer,
    PaymentTransactionSerializer,
    PurchaseSerializer,
    VerifyPaymentSerializer,
)
from .services import PaymentService

logger = logging.getLogger(__name__)


# ── Student views ──


class InitiatePaymentView(APIView):
    permission_classes = [IsStudent]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "payment"

    @extend_schema(
        request=InitiatePaymentSerializer,
        responses={
            201: inline_serializer(
                "InitiatePaymentResponse",
                fields={
                    "transaction_id": drf_serializers.IntegerField(),
                    "gateway_order_id": drf_serializers.CharField(),
                    "amount": drf_serializers.CharField(),
                    "currency": drf_serializers.CharField(),
                    "course_id": drf_serializers.IntegerField(),
                    "course_title": drf_serializers.CharField(),
                    "razorpay_key": drf_serializers.CharField(allow_null=True),
                },
            )
        },
    )
    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result, error = PaymentService.initiate_payment(
            request.user,
            serializer.validated_data["course_id"],
        )
        if error == ErrorMessage.COURSE_NOT_FOUND:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)
        if error == ErrorMessage.PAYMENT_GATEWAY_ERROR:
            return Response({"detail": error}, status=status.HTTP_502_BAD_GATEWAY)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_201_CREATED)


class VerifyPaymentView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(request=VerifyPaymentSerializer, responses={201: PurchaseSerializer})
    def post(self, request):
        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        purchase, error = PaymentService.verify_payment(
            request.user,
            serializer.validated_data,
        )
        if error == ErrorMessage.TRANSACTION_NOT_FOUND:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PurchaseSerializer(purchase).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(tags=["Payments"], summary="List my purchases"),
)
class PurchaseHistoryView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = PurchaseSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Purchase.objects.none()
        return Purchase.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).select_related("course__level")


@extend_schema_view(
    list=extend_schema(tags=["Payments"], summary="List my transactions"),
)
class TransactionHistoryView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = PaymentTransactionSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PaymentTransaction.objects.none()
        return PaymentTransaction.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        )


# ── Admin views ──


class AdminExtendValidityView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(request=AdminExtendValiditySerializer, responses={200: PurchaseSerializer})
    def post(self, request):
        serializer = AdminExtendValiditySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        purchase, error = PaymentService.extend_validity(
            serializer.validated_data["purchase_id"],
            serializer.validated_data["extra_days"],
            request.user,
        )
        if error:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)

        return Response(PurchaseSerializer(purchase).data)


@extend_schema_view(
    list=extend_schema(tags=["Payments"], summary="List all purchases (admin)"),
)
class AdminPurchaseListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = PurchaseSerializer
    queryset = Purchase.objects.select_related("course__level", "student__user")
    pagination_class = LargePagination
    filterset_fields = ["status", "course__level"]
