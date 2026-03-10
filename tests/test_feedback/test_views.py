from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.payments.models import Purchase
from core.test_utils import TestFactory


class FeedbackTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data = self.factory.setup_full_level(order=1)
        self.factory.create_purchase(self.profile, self.data["level"])

    def test_submit_feedback(self):
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 5, "difficulty_rating": 3, "clarity_rating": 4},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_submit_duplicate_feedback(self):
        session = self.data["sessions"][0]
        self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 5, "difficulty_rating": 3, "clarity_rating": 4},
        )
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 4, "difficulty_rating": 2, "clarity_rating": 3},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rating_zero_rejected(self):
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 0, "difficulty_rating": 3, "clarity_rating": 4},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rating_six_rejected(self):
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 6, "difficulty_rating": 3, "clarity_rating": 4},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_feedback_with_only_rating(self):
        """difficulty_rating and clarity_rating are optional, only rating is required."""
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 5},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["difficulty_rating"])
        self.assertIsNone(response.data["clarity_rating"])

    def test_missing_required_rating_rejected(self):
        """Submitting without the required rating field should return 400."""
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"difficulty_rating": 3, "clarity_rating": 4},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_feedback_with_partial_optional_ratings(self):
        """Submitting with only one optional rating should succeed."""
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 4, "difficulty_rating": 2},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["difficulty_rating"], 2)
        self.assertIsNone(response.data["clarity_rating"])

    def test_invalid_difficulty_rating_rejected(self):
        """difficulty_rating outside 1-5 should be rejected."""
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 5, "difficulty_rating": 0},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_clarity_rating_rejected(self):
        """clarity_rating outside 1-5 should be rejected."""
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 5, "clarity_rating": 6},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_feedback_nonexistent_session_returns_404(self):
        response = self.client.post(
            "/api/v1/feedback/sessions/99999/",
            {"rating": 5, "difficulty_rating": 3, "clarity_rating": 4},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_feedback_list(self):
        session = self.data["sessions"][0]
        self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 5, "difficulty_rating": 3, "clarity_rating": 4},
        )
        response = self.client.get("/api/v1/feedback/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_admin_feedback_list(self):
        admin = self.factory.create_admin()
        admin_client = self.factory.get_auth_client(admin)
        response = admin_client.get("/api/v1/feedback/admin/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_cannot_access_admin_feedback(self):
        response = self.client.get("/api/v1/feedback/admin/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_submit_feedback(self):
        anon = APIClient()
        session = self.data["sessions"][0]
        response = anon.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 5, "difficulty_rating": 3, "clarity_rating": 4},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class FeedbackDataIsolationTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user_a, self.profile_a = self.factory.create_student(email="a@test.com")
        self.user_b, self.profile_b = self.factory.create_student(email="b@test.com")
        self.client_a = self.factory.get_auth_client(self.user_a)
        self.client_b = self.factory.get_auth_client(self.user_b)
        self.data = self.factory.setup_full_level(order=1)
        self.factory.create_purchase(self.profile_a, self.data["level"])
        self.factory.create_purchase(self.profile_b, self.data["level"])

    def test_student_cannot_see_others_feedback(self):
        session = self.data["sessions"][0]
        self.client_a.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 5, "difficulty_rating": 3, "clarity_rating": 4},
        )
        response = self.client_b.get("/api/v1/feedback/")
        self.assertEqual(response.data["count"], 0)


class FeedbackPurchaseRequirementTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1)
        self.client = self.factory.get_auth_client(self.user)

    def test_feedback_without_purchase_returns_403(self):
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 5, "difficulty_rating": 3, "clarity_rating": 4},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_feedback_with_purchase_returns_201(self):
        self.factory.create_purchase(self.profile, self.data["level"])
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 5, "difficulty_rating": 3, "clarity_rating": 4},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_feedback_with_expired_purchase_returns_403(self):
        purchase = self.factory.create_purchase(self.profile, self.data["level"])
        purchase.status = Purchase.Status.EXPIRED
        purchase.save()
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/feedback/sessions/{session.pk}/",
            {"rating": 5, "difficulty_rating": 3, "clarity_rating": 4},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
