from rest_framework import status
from rest_framework.test import APITestCase

from apps.doubts.models import DoubtTicket
from core.test_utils import TestFactory

ADMIN_DOUBTS_URL = "/api/v1/doubts/admin/"


class AdminDoubtEnrichedFieldsTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=3)

    def test_session_doubt_has_level_and_course(self):
        session = self.data["sessions"][0]
        DoubtTicket.objects.create(
            student=self.profile,
            title="Session doubt",
            description="desc",
            context_type="session",
            session=session,
        )
        response = self.admin_client.get(ADMIN_DOUBTS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        doubt = response.data["results"][0]
        self.assertEqual(doubt["level_name"], self.data["level"].name)
        self.assertEqual(doubt["course_name"], self.data["course"].title)

    def test_exam_question_doubt_has_level(self):
        question, _ = self.data["questions"][0]
        DoubtTicket.objects.create(
            student=self.profile,
            title="Exam doubt",
            description="desc",
            context_type="exam_question",
            exam_question=question,
        )
        response = self.admin_client.get(ADMIN_DOUBTS_URL)
        doubt = response.data["results"][0]
        self.assertEqual(doubt["level_name"], self.data["level"].name)

    def test_topic_doubt_has_null_level_and_course(self):
        DoubtTicket.objects.create(
            student=self.profile,
            title="Topic doubt",
            description="desc",
            context_type="topic",
        )
        response = self.admin_client.get(ADMIN_DOUBTS_URL)
        doubt = response.data["results"][0]
        self.assertIsNone(doubt["level_name"])
        self.assertIsNone(doubt["course_name"])

    def test_exam_doubt_course_name_null_when_no_course(self):
        """Exam not linked to a course should return null course_name."""
        question, _ = self.data["questions"][0]
        # The exam created by setup_full_level has no course linked
        DoubtTicket.objects.create(
            student=self.profile,
            title="Exam doubt no course",
            description="desc",
            context_type="exam_question",
            exam_question=question,
        )
        response = self.admin_client.get(ADMIN_DOUBTS_URL)
        doubt = response.data["results"][0]
        self.assertIsNone(doubt["course_name"])
