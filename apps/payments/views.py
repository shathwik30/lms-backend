import datetime
import logging

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics, status
from rest_framework import serializers as drf_serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import ErrorMessage
from core.decorators import swagger_safe
from core.pagination import LargePagination, SmallPagination
from core.permissions import IsAdmin, IsStudent
from core.throttling import SafeScopedRateThrottle

from .models import PaymentTransaction, Purchase
from .serializers import (
    AdminExtendValiditySerializer,
    InitiatePaymentSerializer,
    LevelPurchasePreviewSerializer,
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
        tags=["Payments"],
        request=InitiatePaymentSerializer,
        responses={
            201: inline_serializer(
                "InitiatePaymentResponse",
                fields={
                    "transaction_id": drf_serializers.IntegerField(),
                    "razorpay_order_id": drf_serializers.CharField(),
                    "amount": drf_serializers.CharField(),
                    "currency": drf_serializers.CharField(),
                    "level_id": drf_serializers.IntegerField(),
                    "level_name": drf_serializers.CharField(),
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
            serializer.validated_data["level_id"],
        )
        if error == ErrorMessage.LEVEL_NOT_FOUND:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)
        if error == ErrorMessage.PAYMENT_GATEWAY_ERROR:
            return Response({"detail": error}, status=status.HTTP_502_BAD_GATEWAY)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_201_CREATED)


class VerifyPaymentView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(request=VerifyPaymentSerializer, responses={201: PurchaseSerializer}, tags=["Payments"])
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


class DevPurchaseView(APIView):
    """Bypass Razorpay — instantly creates a purchase for development/testing."""

    permission_classes = [IsStudent]

    @extend_schema(
        tags=["Payments"],
        request=InitiatePaymentSerializer,
        responses={201: PurchaseSerializer},
    )
    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        purchase, error = PaymentService.dev_purchase(
            request.user,
            serializer.validated_data["level_id"],
        )
        if error == ErrorMessage.LEVEL_NOT_FOUND:
            return Response({"detail": error}, status=status.HTTP_404_NOT_FOUND)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PurchaseSerializer(purchase).data, status=status.HTTP_201_CREATED)


class LevelPurchasePreviewView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(
        tags=["Payments"],
        summary="Get purchase preview for a level",
        responses={200: LevelPurchasePreviewSerializer},
    )
    def get(self, request, level_id):
        from apps.courses.models import Course, Session
        from apps.exams.models import Question
        from apps.levels.models import Level

        try:
            level = Level.objects.get(pk=level_id, is_active=True)
        except Level.DoesNotExist:
            return Response({"detail": ErrorMessage.LEVEL_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        courses = Course.objects.filter(level=level, is_active=True)

        video_count = Session.objects.filter(
            week__course__in=courses,
            session_type=Session.SessionType.VIDEO,
            is_active=True,
        ).count()

        question_count = Question.objects.filter(
            level=level,
            is_active=True,
        ).count()

        whats_included = []
        if video_count:
            whats_included.append(f"{video_count}+ Video Lectures")
        if question_count:
            whats_included.append(f"{question_count}+ Practice Questions")
        whats_included.append("Full Level Exam Access")
        whats_included.append("Doubt Clearing Support")

        syllabus = [{"id": c.id, "title": c.title} for c in courses]

        data = {
            "level_id": level.id,
            "level_name": level.name,
            "price": level.price,
            "validity_days": level.validity_days,
            "access": "Full Level",
            "whats_included": whats_included,
            "syllabus": syllabus,
        }
        return Response(LevelPurchasePreviewSerializer(data).data)


@extend_schema_view(
    list=extend_schema(tags=["Payments"], summary="List my purchases"),
)
class PurchaseHistoryView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = PurchaseSerializer
    pagination_class = SmallPagination
    filterset_fields = ["level", "status"]

    @swagger_safe(Purchase)
    def get_queryset(self):
        return Purchase.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).select_related("level")


@extend_schema_view(
    retrieve=extend_schema(tags=["Payments"], summary="Get one of my purchases"),
)
class PurchaseDetailView(generics.RetrieveAPIView):
    permission_classes = [IsStudent]
    serializer_class = PurchaseSerializer

    @swagger_safe(Purchase)
    def get_queryset(self):
        return Purchase.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).select_related("level", "student__user")


@extend_schema_view(
    list=extend_schema(tags=["Payments"], summary="List my transactions"),
)
class TransactionHistoryView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = PaymentTransactionSerializer
    pagination_class = SmallPagination
    filterset_fields = ["status"]

    @swagger_safe(PaymentTransaction)
    def get_queryset(self):
        return PaymentTransaction.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).select_related("student__user", "level", "purchase")


@extend_schema_view(
    retrieve=extend_schema(tags=["Payments"], summary="Get one of my payment transactions"),
)
class TransactionDetailView(generics.RetrieveAPIView):
    permission_classes = [IsStudent]
    serializer_class = PaymentTransactionSerializer

    @swagger_safe(PaymentTransaction)
    def get_queryset(self):
        return PaymentTransaction.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).select_related("student__user", "level", "purchase")


# ── Admin views ──


class AdminPaymentDashboardView(APIView):
    """Aggregated payment stats for the admin dashboard."""

    permission_classes = [IsAdmin]

    @extend_schema(
        tags=["Payments"],
        summary="Payment dashboard stats",
        responses={
            200: inline_serializer(
                "AdminPaymentDashboardResponse",
                fields={
                    "total_revenue": drf_serializers.CharField(),
                    "successful_payments": drf_serializers.IntegerField(),
                    "failed_payments": drf_serializers.IntegerField(),
                    "refunded_payments": drf_serializers.IntegerField(),
                    "revenue_trend": drf_serializers.ListField(child=drf_serializers.DictField()),
                    "top_purchased_levels": drf_serializers.ListField(child=drf_serializers.DictField()),
                },
            )
        },
    )
    def get(self, request):
        status_counts = PaymentTransaction.objects.aggregate(
            successful=Count("id", filter=Q(status=PaymentTransaction.Status.SUCCESS)),
            failed=Count("id", filter=Q(status=PaymentTransaction.Status.FAILED)),
            refunded=Count("id", filter=Q(status=PaymentTransaction.Status.REFUNDED)),
        )

        total_revenue = (
            PaymentTransaction.objects.filter(status=PaymentTransaction.Status.SUCCESS).aggregate(total=Sum("amount"))[
                "total"
            ]
            or 0
        )

        twelve_months_ago = timezone.now() - datetime.timedelta(days=365)
        revenue_trend = list(
            PaymentTransaction.objects.filter(
                status=PaymentTransaction.Status.SUCCESS,
                created_at__gte=twelve_months_ago,
            )
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(revenue=Sum("amount"), count=Count("id"))
            .order_by("month")
        )

        top_levels = list(
            Purchase.objects.filter(status=Purchase.Status.ACTIVE)
            .values("level__id", "level__name")
            .annotate(purchase_count=Count("id"))
            .order_by("-purchase_count")[:10]
        )

        return Response(
            {
                "total_revenue": str(total_revenue),
                "successful_payments": status_counts["successful"],
                "failed_payments": status_counts["failed"],
                "refunded_payments": status_counts["refunded"],
                "revenue_trend": [
                    {
                        "month": item["month"],
                        "revenue": str(item["revenue"]),
                        "count": item["count"],
                    }
                    for item in revenue_trend
                ],
                "top_purchased_levels": [
                    {
                        "level_id": item["level__id"],
                        "level_name": item["level__name"],
                        "purchase_count": item["purchase_count"],
                    }
                    for item in top_levels
                ],
            }
        )


class AdminExtendValidityView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(request=AdminExtendValiditySerializer, responses={200: PurchaseSerializer}, tags=["Payments"])
    def post(self, request):
        serializer = AdminExtendValiditySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        purchase, error = PaymentService.extend_validity(
            serializer.validated_data["purchase_id"],
            serializer.validated_data["extra_days"],
            request.user,
            serializer.validated_data.get("reason", "").strip(),
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
    queryset = Purchase.objects.select_related("level", "student__user")
    pagination_class = LargePagination
    filterset_fields = ["status", "level"]


@extend_schema_view(
    retrieve=extend_schema(tags=["Payments"], summary="Get a purchase (admin)"),
)
class AdminPurchaseDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdmin]
    serializer_class = PurchaseSerializer
    queryset = Purchase.objects.select_related("level", "student__user", "extended_by")


@extend_schema_view(
    retrieve=extend_schema(tags=["Payments"], summary="Get a payment transaction (admin)"),
)
class AdminTransactionDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdmin]
    serializer_class = PaymentTransactionSerializer
    queryset = PaymentTransaction.objects.select_related("student__user", "level", "purchase")
