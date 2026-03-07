from django.test import TestCase

from apps.doubts.models import DoubtTicket
from core.constants import ErrorMessage
from core.test_utils import TestFactory


class AdminDoubtReplyViewTests(TestCase):
    """Tests for AdminDoubtReplyView covering the ticket-not-found path."""

    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.student_user, self.profile = self.factory.create_student()

    def test_ticket_not_found_returns_404(self):
        """Replying to a non-existent ticket returns 404."""
        response = self.admin_client.post(
            "/api/v1/doubts/admin/99999/reply/",
            data={"message": "This is a reply"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)

    def test_reply_to_existing_ticket_success(self):
        """Successfully replying to an existing open ticket returns 201."""
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="Test doubt",
            description="I have a question",
            context_type=DoubtTicket.ContextType.TOPIC,
            status=DoubtTicket.Status.OPEN,
        )

        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{ticket.pk}/reply/",
            data={"message": "Here is the answer"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Here is the answer")

    def test_reply_to_closed_ticket_returns_400(self):
        """Replying to a closed ticket returns 400."""
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="Closed doubt",
            description="Already resolved",
            context_type=DoubtTicket.ContextType.TOPIC,
            status=DoubtTicket.Status.CLOSED,
        )

        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{ticket.pk}/reply/",
            data={"message": "Late reply"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], ErrorMessage.TICKET_CLOSED)


class AdminAssignDoubtViewTests(TestCase):
    """Tests for AdminAssignDoubtView covering the ticket-not-found path."""

    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.student_user, self.profile = self.factory.create_student()

    def test_ticket_not_found_returns_404(self):
        """Assigning a non-existent ticket returns 404."""
        response = self.admin_client.post(
            "/api/v1/doubts/admin/99999/assign/",
            data={"assigned_to": self.admin.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)

    def test_assign_ticket_to_admin_success(self):
        """Assigning a ticket to an admin user succeeds."""
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="Assign test",
            description="Need assignment",
            context_type=DoubtTicket.ContextType.TOPIC,
            status=DoubtTicket.Status.OPEN,
        )

        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{ticket.pk}/assign/",
            data={"assigned_to": self.admin.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_to, self.admin)
        self.assertEqual(ticket.status, DoubtTicket.Status.IN_REVIEW)

    def test_assign_ticket_to_non_admin_returns_400(self):
        """Assigning a ticket to a non-admin user returns 400."""
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="Assign to student",
            description="Should fail",
            context_type=DoubtTicket.ContextType.TOPIC,
            status=DoubtTicket.Status.OPEN,
        )

        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{ticket.pk}/assign/",
            data={"assigned_to": self.student_user.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], ErrorMessage.ASSIGN_STAFF_ONLY)

    def test_assign_ticket_to_nonexistent_user_returns_404(self):
        """Assigning a ticket to a non-existent user returns 404."""
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="Assign to ghost",
            description="Should fail",
            context_type=DoubtTicket.ContextType.TOPIC,
            status=DoubtTicket.Status.OPEN,
        )

        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{ticket.pk}/assign/",
            data={"assigned_to": 99999},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.USER_NOT_FOUND)


class AdminDoubtStatusViewTests(TestCase):
    """Tests for AdminDoubtStatusView covering the ticket-not-found path."""

    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.student_user, self.profile = self.factory.create_student()

    def test_ticket_not_found_returns_404(self):
        """Updating status of a non-existent ticket returns 404."""
        response = self.admin_client.post(
            "/api/v1/doubts/admin/99999/status/",
            data={"status": DoubtTicket.Status.CLOSED},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)

    def test_update_status_success(self):
        """Updating status of an existing ticket succeeds."""
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="Status test",
            description="Test description",
            context_type=DoubtTicket.ContextType.TOPIC,
            status=DoubtTicket.Status.OPEN,
        )

        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{ticket.pk}/status/",
            data={"status": DoubtTicket.Status.ANSWERED},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, DoubtTicket.Status.ANSWERED)


class AdminBonusMarksViewTests(TestCase):
    """Tests for AdminBonusMarksView covering not-found and success paths."""

    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.student_user, self.profile = self.factory.create_student()

    def test_ticket_not_found_returns_404(self):
        """Setting bonus marks on a non-existent ticket returns 404."""
        response = self.admin_client.post(
            "/api/v1/doubts/admin/99999/bonus/",
            data={"bonus_marks": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)

    def test_bonus_marks_success(self):
        """Successfully setting bonus marks returns 200 with updated ticket."""
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="Bonus test",
            description="Deserves bonus",
            context_type=DoubtTicket.ContextType.TOPIC,
            status=DoubtTicket.Status.ANSWERED,
        )

        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{ticket.pk}/bonus/",
            data={"bonus_marks": "7.50"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        ticket.refresh_from_db()
        self.assertEqual(float(ticket.bonus_marks), 7.50)

    def test_bonus_marks_zero(self):
        """Setting bonus marks to zero works."""
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="Zero bonus",
            description="Reset bonus",
            context_type=DoubtTicket.ContextType.TOPIC,
            status=DoubtTicket.Status.OPEN,
            bonus_marks=10,
        )

        response = self.admin_client.post(
            f"/api/v1/doubts/admin/{ticket.pk}/bonus/",
            data={"bonus_marks": 0},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        ticket.refresh_from_db()
        self.assertEqual(float(ticket.bonus_marks), 0.0)
