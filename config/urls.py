from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from core.views import HealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Health check
    path("api/v1/health/", HealthCheckView.as_view(), name="health-check"),
    # Prometheus metrics
    path("metrics/", include("django_prometheus.urls")),
    # API v1
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/levels/", include("apps.levels.urls")),
    path("api/v1/courses/", include("apps.courses.urls")),
    path("api/v1/exams/", include("apps.exams.urls")),
    path("api/v1/payments/", include("apps.payments.urls")),
    path("api/v1/progress/", include("apps.progress.urls")),
    path("api/v1/doubts/", include("apps.doubts.urls")),
    path("api/v1/feedback/", include("apps.feedback.urls")),
    path("api/v1/analytics/", include("apps.analytics.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/certificates/", include("apps.certificates.urls")),
    path("api/v1/home/", include("apps.home.urls")),
    path("api/v1/search/", include("apps.search.urls")),
    # API docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
