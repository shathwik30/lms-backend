from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Session
from core.test_utils import TestFactory

ADMIN_EXAMS_URL = "/api/v1/exams/admin/"


class AdminExamEnrichedFieldsTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.data = self.factory.setup_full_level(order=1, num_questions=3)

    def test_admin_exam_has_subjects_included(self):
        response = self.admin_client.get(ADMIN_EXAMS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        exam = response.data["results"][0]
        self.assertIn("subjects_included", exam)
        self.assertIsInstance(exam["subjects_included"], list)
        # Course title should be in subjects_included
        self.assertIn(self.data["course"].title, exam["subjects_included"])

    def test_admin_exam_detail_has_subjects_included(self):
        exam_id = self.data["exam"].pk
        response = self.admin_client.get(f"{ADMIN_EXAMS_URL}{exam_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("subjects_included", response.data)

    def test_admin_exam_create_still_works(self):
        response = self.admin_client.post(
            ADMIN_EXAMS_URL,
            {
                "level": self.data["level"].pk,
                "exam_type": "weekly",
                "title": "New Exam",
                "duration_minutes": 30,
                "total_marks": 20,
                "passing_percentage": 50,
                "num_questions": 5,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_create_weekly_exam_auto_creates_session(self):
        response = self.admin_client.post(
            ADMIN_EXAMS_URL,
            {
                "level": self.data["level"].pk,
                "week": self.data["week"].pk,
                "course": self.data["course"].pk,
                "exam_type": "weekly",
                "title": "Kinematics Quiz",
                "duration_minutes": 15,
                "total_marks": 20,
                "passing_percentage": 50,
                "num_questions": 5,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        session = Session.objects.get(exam_id=response.data["id"])
        self.assertEqual(session.week_id, self.data["week"].pk)
        self.assertEqual(session.session_type, Session.SessionType.PRACTICE_EXAM)
        self.assertEqual(session.title, "Kinematics Quiz")

    def test_subjects_included_excludes_inactive_courses(self):
        # Deactivate the course
        self.data["course"].is_active = False
        self.data["course"].save()
        response = self.admin_client.get(ADMIN_EXAMS_URL)
        exam = response.data["results"][0]
        self.assertEqual(exam["subjects_included"], [])
