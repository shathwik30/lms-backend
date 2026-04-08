from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Session
from apps.exams.models import Exam
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
        self.factory.create_purchase(self.profile, self.data["level"])
        session = self.data["sessions"][0]
        response = self.client.get(f"/api/v1/courses/sessions/{session.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("video_url", response.data)

    def test_session_detail_resource_fields(self):
        """Resource sessions include file_url and resource_type in detail."""
        level = self.factory.create_level(order=99)
        course = self.factory.create_course(level)
        week = self.factory.create_week(course)
        self.factory.create_purchase(self.profile, level)
        session = Session.objects.create(
            week=week,
            title="Notes PDF",
            session_type=Session.SessionType.RESOURCE,
            file_url="https://example.com/notes.pdf",
            resource_type=Session.ResourceType.PDF,
            order=1,
        )
        response = self.client.get(f"/api/v1/courses/sessions/{session.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["file_url"], "https://example.com/notes.pdf")
        self.assertEqual(response.data["resource_type"], "pdf")

    def test_course_sessions_requires_purchase(self):
        response = self.client.get(f"/api/v1/courses/{self.data['course'].pk}/sessions/")
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_course_sessions_with_purchase(self):
        self.factory.create_purchase(self.profile, self.data["level"])
        response = self.client.get(f"/api/v1/courses/{self.data['course'].pk}/sessions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_course_sessions_include_weekly_exam_as_practice_session(self):
        weekly_exam = self.factory.create_exam(
            self.data["level"],
            week=self.data["week"],
            course=self.data["course"],
            exam_type=Exam.ExamType.WEEKLY,
            num_questions=3,
        )
        for _ in range(3):
            self.factory.create_question(weekly_exam)

        self.factory.create_purchase(self.profile, self.data["level"])
        response = self.client.get(f"/api/v1/courses/{self.data['course'].pk}/sessions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sessions = response.data["weeks"][0]["sessions"]
        exam_session = next(item for item in sessions if item["exam_id"] == weekly_exam.pk)
        self.assertEqual(exam_session["session_type"], "practice_exam")
        self.assertEqual(exam_session["title"], weekly_exam.title)
        self.assertTrue(exam_session["is_locked"])

    def test_session_detail_nonexistent_returns_404(self):
        self.factory.create_purchase(self.profile, self.data["level"])
        response = self.client.get("/api/v1/courses/sessions/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_session_detail_inactive_returns_404(self):
        self.factory.create_purchase(self.profile, self.data["level"])
        session = self.data["sessions"][0]
        session.is_active = False
        session.save()
        response = self.client.get(f"/api/v1/courses/sessions/{session.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_session_detail_expired_purchase_denied(self):
        """Expired purchase should NOT grant session access."""
        self.factory.create_expired_purchase(self.profile, self.data["level"])
        session = self.data["sessions"][0]
        response = self.client.get(f"/api/v1/courses/sessions/{session.pk}/")
        self.assertEqual(response.status_code, status.HTTP_402_PAYMENT_REQUIRED)

    def test_course_sessions_expired_purchase_denied(self):
        """Expired purchase should NOT grant session list access."""
        self.factory.create_expired_purchase(self.profile, self.data["level"])
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
        self.course = self.factory.create_course(self.level)
        self.week = self.factory.create_week(self.course)

    def test_admin_create_course(self):
        response = self.admin_client.post(
            "/api/v1/courses/admin/",
            {
                "level": self.level.pk,
                "title": "Test Course",
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

    def test_admin_create_resource_session(self):
        """Admin can create a resource session with file_url and resource_type."""
        response = self.admin_client.post(
            "/api/v1/courses/admin/sessions/",
            {
                "week": self.week.pk,
                "title": "Notes PDF",
                "session_type": "resource",
                "file_url": "https://example.com/notes.pdf",
                "resource_type": "pdf",
                "order": 1,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["file_url"], "https://example.com/notes.pdf")
        self.assertEqual(response.data["resource_type"], "pdf")

    def test_admin_update_resource_session(self):
        """Admin can update file_url on a resource session."""
        session = Session.objects.create(
            week=self.week,
            title="Old Notes",
            session_type=Session.SessionType.RESOURCE,
            file_url="https://example.com/old.pdf",
            resource_type=Session.ResourceType.PDF,
            order=1,
        )
        response = self.admin_client.patch(
            f"/api/v1/courses/admin/sessions/{session.pk}/",
            {"title": "Updated Notes", "file_url": "https://example.com/new.pdf"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertEqual(session.title, "Updated Notes")
        self.assertEqual(session.file_url, "https://example.com/new.pdf")

    def test_admin_list_sessions_filter_by_type(self):
        """Admin can filter sessions by session_type including resource."""
        Session.objects.create(
            week=self.week,
            title="Video 1",
            session_type=Session.SessionType.VIDEO,
            order=1,
        )
        Session.objects.create(
            week=self.week,
            title="Notes PDF",
            session_type=Session.SessionType.RESOURCE,
            file_url="https://example.com/notes.pdf",
            resource_type=Session.ResourceType.PDF,
            order=2,
        )
        response = self.admin_client.get("/api/v1/courses/admin/sessions/?session_type=resource")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["session_type"], "resource")

    def test_admin_delete_resource_session(self):
        """Admin can delete a resource session."""
        session = Session.objects.create(
            week=self.week,
            title="Delete Me",
            session_type=Session.SessionType.RESOURCE,
            file_url="https://example.com/del.pdf",
            resource_type=Session.ResourceType.PDF,
            order=1,
        )
        response = self.admin_client.delete(f"/api/v1/courses/admin/sessions/{session.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Session.objects.filter(pk=session.pk).exists())

    def test_admin_create_markdown_resource_session(self):
        """Admin can create a markdown resource session with markdown_content."""
        response = self.admin_client.post(
            "/api/v1/courses/admin/sessions/",
            {
                "week": self.week.pk,
                "title": "Markdown Notes",
                "session_type": "resource",
                "resource_type": "markdown",
                "markdown_content": "# Hello\n\nThis is **markdown** content.",
                "order": 1,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["resource_type"], "markdown")
        self.assertEqual(response.data["markdown_content"], "# Hello\n\nThis is **markdown** content.")

    def test_admin_update_markdown_content(self):
        """Admin can update markdown_content on a markdown session."""
        session = Session.objects.create(
            week=self.week,
            title="MD Notes",
            session_type=Session.SessionType.RESOURCE,
            resource_type=Session.ResourceType.MARKDOWN,
            markdown_content="# Old Content",
            order=1,
        )
        response = self.admin_client.patch(
            f"/api/v1/courses/admin/sessions/{session.pk}/",
            {"markdown_content": "# Updated Content\n\nNew text."},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertEqual(session.markdown_content, "# Updated Content\n\nNew text.")

    def test_student_can_view_markdown_session(self):
        """Student with purchase can view markdown_content in session detail."""
        user, profile = self.factory.create_student(email="mdviewer@test.com")
        self.factory.create_purchase(profile, self.level)
        session = Session.objects.create(
            week=self.week,
            title="Markdown Session",
            session_type=Session.SessionType.RESOURCE,
            resource_type=Session.ResourceType.MARKDOWN,
            markdown_content="# Study Notes\n\n- Point 1\n- Point 2",
            order=1,
        )
        client = self.factory.get_auth_client(user)
        response = client.get(f"/api/v1/courses/sessions/{session.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["resource_type"], "markdown")
        self.assertEqual(response.data["markdown_content"], "# Study Notes\n\n- Point 1\n- Point 2")

    def test_student_cannot_admin_courses(self):
        user, _ = self.factory.create_student()
        student_client = self.factory.get_auth_client(user)
        response = student_client.get("/api/v1/courses/admin/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
