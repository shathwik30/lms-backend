import logging

from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import HealthCheckConstants, HealthStatus

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            200: inline_serializer(
                "HealthCheckResponse",
                fields={
                    "status": serializers.ChoiceField(choices=["healthy", "degraded"]),
                    "database": serializers.BooleanField(),
                    "redis": serializers.BooleanField(),
                },
            )
        },
        tags=["Health"],
    )
    def get(self, request):
        db_ok = self._check_database()
        redis_ok = self._check_cache()

        status_label = HealthStatus.HEALTHY if (db_ok and redis_ok) else HealthStatus.DEGRADED
        return Response(
            {"status": status_label, "database": db_ok, "redis": redis_ok},
            status=200,
        )

    @staticmethod
    def _check_database():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            logger.warning("Health check: database unreachable")
            return False

    @staticmethod
    def _check_cache():
        try:
            cache.set(
                HealthCheckConstants.CACHE_KEY,
                HealthCheckConstants.CACHE_VALUE,
                timeout=HealthCheckConstants.CACHE_TIMEOUT,
            )
            if cache.get(HealthCheckConstants.CACHE_KEY) != HealthCheckConstants.CACHE_VALUE:
                raise ValueError("Cache read-back failed")
            return True
        except Exception:
            logger.warning("Health check: cache/Redis unreachable")
            return False
