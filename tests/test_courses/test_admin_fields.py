from rest_framework import status
from rest_framework.test import APITestCase

from apps.progress.models import CourseProgress
from core.test_utils import TestFactory

ADMIN_COURSES_URL = "/api/v1/courses/admin/"


class AdminCourseEnrichedFieldsTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.data = self.factory.setup_full_level(order=1, num_questions=3)

    def test_admin_course_has_price_from_level(self):
        response = self.admin_client.get(ADMIN_COURSES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        course = response.data["results"][0]
        self.assertEqual(float(course["price"]), float(self.data["level"].price))

    def test_admin_course_has_students_enrolled(self):
        user, profile = self.factory.create_student()
        CourseProgress.objects.create(
            student=profile,
            course=self.data["course"],
            status=CourseProgress.Status.IN_PROGRESS,
        )
        response = self.admin_client.get(ADMIN_COURSES_URL)
        course = response.data["results"][0]
        self.assertEqual(course["students_enrolled"], 1)

    def test_admin_course_students_enrolled_excludes_not_started(self):
        user, profile = self.factory.create_student()
        CourseProgress.objects.create(
            student=profile,
            course=self.data["course"],
            status=CourseProgress.Status.NOT_STARTED,
        )
        response = self.admin_client.get(ADMIN_COURSES_URL)
        course = response.data["results"][0]
        self.assertEqual(course["students_enrolled"], 0)

    def test_admin_course_has_exam_linked(self):
        # setup_full_level creates an exam but doesn't link it to the course
        # Create one linked to the course
        exam = self.factory.create_exam(
            self.data["level"],
            course=self.data["course"],
            num_questions=3,
        )
        response = self.admin_client.get(ADMIN_COURSES_URL)
        course = response.data["results"][0]
        self.assertIn(exam.title, course["exam_linked"])

    def test_admin_course_exam_linked_empty_when_none(self):
        response = self.admin_client.get(ADMIN_COURSES_URL)
        course = response.data["results"][0]
        self.assertEqual(course["exam_linked"], [])

    def test_admin_course_detail_has_enriched_fields(self):
        course_id = self.data["course"].pk
        response = self.admin_client.get(f"{ADMIN_COURSES_URL}{course_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("price", response.data)
        self.assertIn("students_enrolled", response.data)
        self.assertIn("exam_linked", response.data)

    def test_admin_course_create_still_works(self):
        response = self.admin_client.post(
            ADMIN_COURSES_URL,
            {"level": self.data["level"].pk, "title": "New Course"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
