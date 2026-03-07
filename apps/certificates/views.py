from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import ErrorMessage
from core.pagination import LargePagination
from core.permissions import IsAdmin, IsStudent

from .models import Certificate
from .serializers import CertificateSerializer


@extend_schema_view(
    list=extend_schema(tags=["Certificates"], summary="List my certificates"),
)
class StudentCertificateListView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = CertificateSerializer
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Certificate.objects.none()
        return Certificate.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).select_related("level", "student__user")


class StudentCertificateDetailView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(responses={200: CertificateSerializer})
    def get(self, request, pk):
        try:
            cert = Certificate.objects.select_related(
                "level",
                "student__user",
            ).get(pk=pk, student=request.user.student_profile)
        except Certificate.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        return Response(CertificateSerializer(cert).data)


@extend_schema_view(
    list=extend_schema(tags=["Certificates"], summary="List all certificates (admin)"),
)
class AdminCertificateListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = CertificateSerializer
    queryset = Certificate.objects.select_related("level", "student__user")
    pagination_class = LargePagination
    filterset_fields = ["level", "student"]
    search_fields = ["student__user__email", "student__user__full_name", "certificate_number"]
