import logging

from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import ScopedRateThrottle

logger = logging.getLogger(__name__)


class SafeScopedRateThrottle(ScopedRateThrottle):
    """ScopedRateThrottle that skips throttling when the scope has no rate configured."""

    def allow_request(self, request, view):
        self.scope = getattr(view, "throttle_scope", None)
        if not self.scope:
            return True
        self.rate = self.get_rate()
        if self.rate is None:
            return True
        return super().allow_request(request, view)

    def get_rate(self) -> str | None:
        try:
            return super().get_rate()
        except ImproperlyConfigured:
            return None
