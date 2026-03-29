from rest_framework import status
from rest_framework.test import APITestCase

from apps.feedback.models import SessionFeedback
from core.test_utils import TestFactory

ADMIN_FEEDBACK_URL = "/api/v1/feedback/admin/"


class AdminFeedbackEnrichedFieldsTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=3)
        self.factory.create_purchase(self.profile, self.data["level"])

    def test_admin_feedback_has_student_name(self):
        session = self.data["sessions"][0]
        SessionFeedback.objects.create(
            student=self.profile,
            session=session,
            overall_rating=4,
        )
        response = self.admin_client.get(ADMIN_FEEDBACK_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fb = response.data["results"][0]
        self.assertEqual(fb["student_name"], self.user.full_name)

    def test_admin_feedback_has_level_name(self):
        session = self.data["sessions"][0]
        SessionFeedback.objects.create(
            student=self.profile,
            session=session,
            overall_rating=5,
        )
        response = self.admin_client.get(ADMIN_FEEDBACK_URL)
        fb = response.data["results"][0]
        self.assertEqual(fb["level_name"], self.data["level"].name)

    def test_admin_feedback_has_subject_name(self):
        session = self.data["sessions"][0]
        SessionFeedback.objects.create(
            student=self.profile,
            session=session,
            overall_rating=3,
        )
        response = self.admin_client.get(ADMIN_FEEDBACK_URL)
        fb = response.data["results"][0]
        self.assertEqual(fb["subject_name"], self.data["course"].title)

    def test_admin_feedback_has_session_title(self):
        session = self.data["sessions"][0]
        SessionFeedback.objects.create(
            student=self.profile,
            session=session,
            overall_rating=4,
        )
        response = self.admin_client.get(ADMIN_FEEDBACK_URL)
        fb = response.data["results"][0]
        self.assertEqual(fb["session_title"], session.title)
