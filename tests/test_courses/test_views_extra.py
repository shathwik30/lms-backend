from django.test import TestCase

from apps.courses.models import Session
from core.constants import ErrorMessage, SuccessMessage
from core.test_utils import TestFactory


class SessionDetailViewTests(TestCase):
    """Tests for SessionDetailView covering uncovered error paths."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)

    def test_session_not_found_returns_404(self):
        """Requesting a non-existent session returns 404."""
        response = self.client.get("/api/v1/courses/sessions/99999/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)

    def test_session_not_accessible_ordering_enforced(self):
        """Accessing a later session without completing prior ones raises SessionNotAccessible."""
        level = self.factory.create_level(order=1)
        course = self.factory.create_course(level)
        week = self.factory.create_week(course, order=1)
        self.factory.create_session(week, order=1)
        session2 = self.factory.create_session(week, order=2)

        # Purchase the level so access is granted
        self.factory.create_purchase(self.profile, level)

        # Try to access session2 without completing session1
        response = self.client.get(f"/api/v1/courses/sessions/{session2.pk}/")
        self.assertEqual(response.status_code, 403)

    def test_session_accessible_when_prior_completed(self):
        """Accessing a session after completing prior ones succeeds."""
        level = self.factory.create_level(order=1)
        course = self.factory.create_course(level)
        week = self.factory.create_week(course, order=1)
        session1 = self.factory.create_session(week, order=1)
        session2 = self.factory.create_session(week, order=2)

        self.factory.create_purchase(self.profile, level)
        self.factory.complete_session(self.profile, session1)

        response = self.client.get(f"/api/v1/courses/sessions/{session2.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_session_first_in_week_accessible(self):
        """First session in a week is accessible with purchase."""
        level = self.factory.create_level(order=1)
        course = self.factory.create_course(level)
        week = self.factory.create_week(course, order=1)
        session1 = self.factory.create_session(week, order=1)

        self.factory.create_purchase(self.profile, level)

        response = self.client.get(f"/api/v1/courses/sessions/{session1.pk}/")
        self.assertEqual(response.status_code, 200)


class CompleteResourceSessionViewTests(TestCase):
    """Tests for CompleteResourceSessionView covering uncovered error and success paths."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)

    def test_complete_resource_session_not_found(self):
        """Completing a non-existent session returns 404."""
        response = self.client.post("/api/v1/courses/sessions/99999/complete-resource/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.SESSION_NOT_FOUND)

    def test_complete_resource_session_wrong_type(self):
        """Completing a VIDEO session via resource endpoint returns 404."""
        level = self.factory.create_level(order=1)
        course = self.factory.create_course(level)
        week = self.factory.create_week(course, order=1)
        video_session = self.factory.create_session(week, order=1, session_type=Session.SessionType.VIDEO)

        response = self.client.post(f"/api/v1/courses/sessions/{video_session.pk}/complete-resource/")
        self.assertEqual(response.status_code, 404)

    def test_complete_resource_session_success(self):
        """Successfully completing a RESOURCE session returns 200."""
        level = self.factory.create_level(order=1)
        course = self.factory.create_course(level)
        week = self.factory.create_week(course, order=1)
        resource_session = self.factory.create_session(week, order=1, session_type=Session.SessionType.RESOURCE)

        response = self.client.post(f"/api/v1/courses/sessions/{resource_session.pk}/complete-resource/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["detail"], SuccessMessage.RESOURCE_SESSION_COMPLETED)

    def test_complete_resource_session_idempotent(self):
        """Completing an already-completed resource session still returns 200."""
        level = self.factory.create_level(order=1)
        course = self.factory.create_course(level)
        week = self.factory.create_week(course, order=1)
        resource_session = self.factory.create_session(week, order=1, session_type=Session.SessionType.RESOURCE)

        # Complete once
        self.client.post(f"/api/v1/courses/sessions/{resource_session.pk}/complete-resource/")
        # Complete again
        response = self.client.post(f"/api/v1/courses/sessions/{resource_session.pk}/complete-resource/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["detail"], SuccessMessage.RESOURCE_SESSION_COMPLETED)
