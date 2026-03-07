from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.doubts.models import DoubtTicket
from apps.payments.models import Purchase
from core.test_utils import TestFactory


class StudentDoubtTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)

    def test_create_doubt(self):
        response = self.client.post(
            "/api/v1/doubts/",
            {
                "title": "Need help with derivatives",
                "description": "I don't understand the chain rule.",
                "context_type": "topic",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "open")

    def test_list_own_doubts(self):
        self.client.post(
            "/api/v1/doubts/",
            {
                "title": "Doubt 1",
                "description": "Desc",
                "context_type": "topic",
            },
        )
        response = self.client.get("/api/v1/doubts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_doubt_detail(self):
        r = self.client.post(
            "/api/v1/doubts/",
            {
                "title": "Doubt 1",
                "description": "Desc",
                "context_type": "topic",
            },
        )
        doubt_id = r.data["id"]
        response = self.client.get(f"/api/v1/doubts/{doubt_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_reply(self):
        r = self.client.post(
            "/api/v1/doubts/",
            {
                "title": "Doubt 1",
                "description": "Desc",
                "context_type": "topic",
            },
        )
        doubt_id = r.data["id"]
        response = self.client.post(
            f"/api/v1/doubts/{doubt_id}/reply/",
            {
                "message": "Can you give an example?",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_reply_to_closed_ticket(self):
        r = self.client.post(
            "/api/v1/doubts/",
            {
                "title": "Doubt 1",
                "description": "Desc",
                "context_type": "topic",
            },
        )
        doubt_id = r.data["id"]
        ticket = DoubtTicket.objects.get(pk=doubt_id)
        ticket.status = DoubtTicket.Status.CLOSED
        ticket.save()
        response = self.client.post(
            f"/api/v1/doubts/{doubt_id}/reply/",
            {
                "message": "More info",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_cannot_create_doubt(self):
        anon = APIClient()
        response = anon.post(
            "/api/v1/doubts/",
            {
                "title": "Test",
                "description": "Desc",
                "context_type": "topic",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DoubtDataIsolationTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user_a, self.profile_a = self.factory.create_student(email="a@test.com")
        self.user_b, self.profile_b = self.factory.create_student(email="b@test.com")
        self.client_a = self.factory.get_auth_client(self.user_a)
        self.client_b = self.factory.get_auth_client(self.user_b)

    def test_student_cannot_see_others_doubts(self):
        self.client_a.post(
            "/api/v1/doubts/",
            {
                "title": "A's doubt",
                "description": "Desc",
                "context_type": "topic",
            },
        )
        response = self.client_b.get("/api/v1/doubts/")
        self.assertEqual(response.data["count"], 0)

    def test_student_cannot_access_others_doubt_detail(self):
        r = self.client_a.post(
            "/api/v1/doubts/",
            {
                "title": "A's doubt",
                "description": "Desc",
                "context_type": "topic",
            },
        )
        response = self.client_b.get(f"/api/v1/doubts/{r.data['id']}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_cannot_reply_to_others_doubt(self):
        r = self.client_a.post(
            "/api/v1/doubts/",
            {
                "title": "A's doubt",
                "description": "Desc",
                "context_type": "topic",
            },
        )
        response = self.client_b.post(
            f"/api/v1/doubts/{r.data['id']}/reply/",
            {
                "message": "I'm not A!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminDoubtTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.user, self.profile = self.factory.create_student()
        self.student_client = self.factory.get_auth_client(self.user)

        r = self.student_client.post(
            "/api/v1/doubts/",
            {
                "title": "Help needed",
                "description": "Please explain.",
                "context_type": "topic",
            },
        )
        self.doubt_id = r.data["id"]

    def test_admin_list_doubts(self):
        response = self.admin_client.get("/api/v1/doubts/admin/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_admin_reply(self):
        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{self.doubt_id}/reply/",
            {"message": "Here is the explanation."},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_admin_reply_sends_notification_email(self):
        from django.core import mail

        self.admin_client.post(
            f"/api/v1/doubts/admin/{self.doubt_id}/reply/",
            {"message": "The answer is to use integration by parts."},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("New Reply", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_admin_reply_updates_status_to_in_review(self):
        self.admin_client.post(
            f"/api/v1/doubts/admin/{self.doubt_id}/reply/",
            {"message": "Looking into it."},
        )
        ticket = DoubtTicket.objects.get(pk=self.doubt_id)
        self.assertEqual(ticket.status, DoubtTicket.Status.IN_REVIEW)

    def test_admin_reply_does_not_change_status_if_not_open(self):
        """Admin reply should only change status from OPEN to IN_REVIEW."""
        ticket = DoubtTicket.objects.get(pk=self.doubt_id)
        ticket.status = DoubtTicket.Status.ANSWERED
        ticket.save()
        self.admin_client.post(
            f"/api/v1/doubts/admin/{self.doubt_id}/reply/",
            {"message": "Follow-up."},
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, DoubtTicket.Status.ANSWERED)

    def test_admin_assign(self):
        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{self.doubt_id}/assign/",
            {"assigned_to": self.admin.pk},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_assign_nonexistent_user_returns_404(self):
        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{self.doubt_id}/assign/",
            {"assigned_to": 99999},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_assign_student_returns_400(self):
        """Assigning a doubt to a student (non-staff) should fail."""
        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{self.doubt_id}/assign/",
            {"assigned_to": self.user.pk},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("staff or admin", response.data["detail"])

    def test_admin_change_status(self):
        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{self.doubt_id}/status/",
            {"status": "answered"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_change_status_invalid(self):
        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{self.doubt_id}/status/",
            {"status": "invalid_status"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_bonus_marks(self):
        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{self.doubt_id}/bonus/",
            {"bonus_marks": "2.50"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_cannot_reply_to_closed_ticket(self):
        ticket = DoubtTicket.objects.get(pk=self.doubt_id)
        ticket.status = DoubtTicket.Status.CLOSED
        ticket.save()
        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{self.doubt_id}/reply/",
            {"message": "This should be blocked."},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_cannot_access_admin_doubts(self):
        response = self.student_client.get("/api/v1/doubts/admin/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DoubtPurchaseRequirementTests(APITestCase):
    """Purchase check for session/exam_question context doubts."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data = self.factory.setup_full_level(order=1, num_questions=2)

    def test_topic_doubt_allowed_without_purchase(self):
        response = self.client.post(
            "/api/v1/doubts/",
            {
                "title": "General question",
                "description": "What is calculus?",
                "context_type": "topic",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_session_doubt_blocked_without_purchase(self):
        session = self.data["sessions"][0]
        response = self.client.post(
            "/api/v1/doubts/",
            {
                "title": "Session question",
                "description": "I don't understand this video.",
                "context_type": "session",
                "session": session.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("purchase", response.data["detail"].lower())

    def test_session_doubt_allowed_with_purchase(self):
        session = self.data["sessions"][0]
        self.factory.create_purchase(self.profile, self.data["level"])
        response = self.client.post(
            "/api/v1/doubts/",
            {
                "title": "Session question",
                "description": "I don't understand this video.",
                "context_type": "session",
                "session": session.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_exam_question_doubt_blocked_without_purchase(self):
        question, _ = self.data["questions"][0]
        response = self.client.post(
            "/api/v1/doubts/",
            {
                "title": "Exam question doubt",
                "description": "Why is option B correct?",
                "context_type": "exam_question",
                "exam_question": question.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_exam_question_doubt_allowed_with_purchase(self):
        question, _ = self.data["questions"][0]
        self.factory.create_purchase(self.profile, self.data["level"])
        response = self.client.post(
            "/api/v1/doubts/",
            {
                "title": "Exam question doubt",
                "description": "Why is option B correct?",
                "context_type": "exam_question",
                "exam_question": question.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_expired_purchase_blocks_session_doubt(self):
        session = self.data["sessions"][0]
        self.factory.create_expired_purchase(self.profile, self.data["level"])
        # Expire it
        Purchase.objects.filter(student=self.profile).update(
            status=Purchase.Status.EXPIRED,
        )
        response = self.client.post(
            "/api/v1/doubts/",
            {
                "title": "Session question",
                "description": "Help please.",
                "context_type": "session",
                "session": session.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
