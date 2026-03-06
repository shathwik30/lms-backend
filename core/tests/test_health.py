from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from core.constants import HealthStatus


class HealthCheckTests(TestCase):
    """Tests for the /api/v1/health/ endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/health/"

    def test_health_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_health_response_keys(self):
        response = self.client.get(self.url)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("database", data)
        self.assertIn("redis", data)

    def test_health_unauthenticated_access(self):
        """Endpoint must be accessible without any credentials."""
        client = APIClient()  # no credentials set
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_health_healthy_when_all_services_up(self):
        response = self.client.get(self.url)
        data = response.json()
        self.assertEqual(data["status"], HealthStatus.HEALTHY)
        self.assertTrue(data["database"])

    def test_health_degraded_when_db_down(self):
        with patch("core.views.connection") as mock_conn:
            mock_conn.cursor.side_effect = Exception("DB down")
            response = self.client.get(self.url)
            data = response.json()
            self.assertEqual(data["status"], HealthStatus.DEGRADED)
            self.assertFalse(data["database"])

    def test_health_degraded_when_cache_down(self):
        with patch("core.views.cache") as mock_cache:
            mock_cache.set.side_effect = Exception("Redis down")
            response = self.client.get(self.url)
            data = response.json()
            self.assertEqual(data["status"], HealthStatus.DEGRADED)
            self.assertFalse(data["redis"])
