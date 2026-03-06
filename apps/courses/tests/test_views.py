from django.db import IntegrityError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Resource
from core.test_utils import TestFactory


class CourseAccessTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data = self.factory.setup_full_level(order=1)

    def test_list_courses_for_level(self):
        response = self.client.get(f"/api/v1/courses/level/{self.data['level'].pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_session_detail_requires_purchase(self):
        session = self.data["sessions"][0]
        response = self.client.get(f"/api/v1/courses/sessions/{session.pk}/")
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_session_detail_with_purchase(self):
        self.factory.create_purchase(self.profile, self.data["course"])
        session = self.data["sessions"][0]
        response = self.client.get(f"/api/v1/courses/sessions/{session.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("video_url", response.data)

    def test_course_sessions_requires_purchase(self):
        response = self.client.get(f"/api/v1/courses/{self.data['course'].pk}/sessions/")
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_course_sessions_with_purchase(self):
        self.factory.create_purchase(self.profile, self.data["course"])
        response = self.client.get(f"/api/v1/courses/{self.data['course'].pk}/sessions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_session_detail_nonexistent_returns_404(self):
        self.factory.create_purchase(self.profile, self.data["course"])
        response = self.client.get("/api/v1/courses/sessions/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_session_detail_inactive_returns_404(self):
        self.factory.create_purchase(self.profile, self.data["course"])
        session = self.data["sessions"][0]
        session.is_active = False
        session.save()
        response = self.client.get(f"/api/v1/courses/sessions/{session.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_session_detail_expired_purchase_denied(self):
        """Expired purchase should NOT grant session access."""
        self.factory.create_expired_purchase(self.profile, self.data["course"])
        session = self.data["sessions"][0]
        response = self.client.get(f"/api/v1/courses/sessions/{session.pk}/")
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_course_sessions_expired_purchase_denied(self):
        """Expired purchase should NOT grant session list access."""
        self.factory.create_expired_purchase(self.profile, self.data["course"])
        response = self.client.get(f"/api/v1/courses/{self.data['course'].pk}/sessions/")
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_unauthenticated_cannot_access_sessions(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        session = self.data["sessions"][0]
        response = anon.get(f"/api/v1/courses/sessions/{session.pk}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminCourseAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.level = self.factory.create_level(order=1)
        self.week = self.factory.create_week(self.level)

    def test_admin_create_course(self):
        response = self.admin_client.post(
            "/api/v1/courses/admin/",
            {
                "level": self.level.pk,
                "title": "Test Course",
                "price": "999.00",
                "validity_days": 45,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_create_session(self):
        response = self.admin_client.post(
            "/api/v1/courses/admin/sessions/",
            {
                "week": self.week.pk,
                "title": "Session 1",
                "video_url": "https://example.com/video.mp4",
                "duration_seconds": 2700,
                "order": 1,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_create_resource_for_session(self):
        session = self.factory.create_session(self.week, order=1)
        response = self.admin_client.post(
            "/api/v1/courses/admin/resources/",
            {
                "title": "Notes PDF",
                "file_url": "https://example.com/notes.pdf",
                "resource_type": "pdf",
                "session": session.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_create_resource_for_week(self):
        response = self.admin_client.post(
            "/api/v1/courses/admin/resources/",
            {
                "title": "Week Notes",
                "file_url": "https://example.com/week.pdf",
                "resource_type": "note",
                "week": self.week.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_create_resource_orphan_rejected(self):
        response = self.admin_client.post(
            "/api/v1/courses/admin/resources/",
            {
                "title": "Orphan",
                "file_url": "https://example.com/orphan.pdf",
                "resource_type": "pdf",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_list_resources(self):
        session = self.factory.create_session(self.week, order=1)
        Resource.objects.create(
            title="R1",
            file_url="https://example.com/r1.pdf",
            resource_type="pdf",
            session=session,
        )
        response = self.admin_client.get("/api/v1/courses/admin/resources/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_admin_update_resource(self):
        session = self.factory.create_session(self.week, order=1)
        resource = Resource.objects.create(
            title="Old",
            file_url="https://example.com/old.pdf",
            resource_type="pdf",
            session=session,
        )
        response = self.admin_client.patch(
            f"/api/v1/courses/admin/resources/{resource.pk}/",
            {"title": "Updated"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resource.refresh_from_db()
        self.assertEqual(resource.title, "Updated")

    def test_admin_delete_resource(self):
        session = self.factory.create_session(self.week, order=1)
        resource = Resource.objects.create(
            title="Delete Me",
            file_url="https://example.com/del.pdf",
            resource_type="pdf",
            session=session,
        )
        response = self.admin_client.delete(f"/api/v1/courses/admin/resources/{resource.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Resource.objects.filter(pk=resource.pk).exists())

    def test_student_cannot_admin_courses(self):
        user, _ = self.factory.create_student()
        student_client = self.factory.get_auth_client(user)
        response = student_client.get("/api/v1/courses/admin/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ResourceModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.level = self.factory.create_level(order=1)
        self.week = self.factory.create_week(self.level)

    def test_resource_constraint_rejects_orphan(self):
        with self.assertRaises(IntegrityError):
            Resource.objects.create(
                title="Orphan",
                file_url="https://example.com/orphan.pdf",
                resource_type="pdf",
            )

    def test_resource_constraint_accepts_session(self):
        session = self.factory.create_session(self.week, order=1)
        resource = Resource.objects.create(
            title="OK",
            file_url="https://example.com/ok.pdf",
            resource_type="pdf",
            session=session,
        )
        self.assertIsNotNone(resource.pk)

    def test_resource_constraint_accepts_week(self):
        resource = Resource.objects.create(
            title="OK",
            file_url="https://example.com/ok.pdf",
            resource_type="pdf",
            week=self.week,
        )
        self.assertIsNotNone(resource.pk)
