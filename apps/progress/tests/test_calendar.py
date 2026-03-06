from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.progress.models import SessionProgress
from core.test_utils import TestFactory


class CalendarAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data = self.factory.setup_full_level(order=1)

    def test_calendar_empty(self):
        now = timezone.now()
        response = self.client.get(f"/api/v1/progress/calendar/?year={now.year}&month={now.month}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["active_dates"]), 0)

    def test_calendar_with_activity(self):
        session = self.data["sessions"][0]
        SessionProgress.objects.create(
            student=self.profile,
            session=session,
            watched_seconds=100,
        )
        now = timezone.now()
        response = self.client.get(f"/api/v1/progress/calendar/?year={now.year}&month={now.month}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["active_dates"]), 0)
        self.assertGreater(response.data["active_dates"][0]["sessions_watched"], 0)

    def test_calendar_missing_params(self):
        response = self.client.get("/api/v1/progress/calendar/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_calendar_missing_month(self):
        response = self.client.get("/api/v1/progress/calendar/?year=2026")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_calendar_invalid_params(self):
        response = self.client.get("/api/v1/progress/calendar/?year=abc&month=xyz")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_calendar_different_month_empty(self):
        session = self.data["sessions"][0]
        SessionProgress.objects.create(
            student=self.profile,
            session=session,
            watched_seconds=100,
        )
        # Query a different month
        response = self.client.get("/api/v1/progress/calendar/?year=2020&month=1")
        self.assertEqual(len(response.data["active_dates"]), 0)

    def test_unauthenticated_denied(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.get("/api/v1/progress/calendar/?year=2026&month=3")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
