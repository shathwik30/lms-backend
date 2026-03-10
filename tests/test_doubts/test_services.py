from django.test import TestCase

from apps.doubts.models import DoubtTicket
from apps.doubts.services import DoubtService
from core.constants import ErrorMessage
from core.test_utils import TestFactory


class DoubtServiceValidateReplyAllowedTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        _, self.profile = self.factory.create_student()

    def _make_ticket(self, ticket_status):
        return DoubtTicket.objects.create(
            student=self.profile,
            title="Test",
            description="Desc",
            context_type=DoubtTicket.ContextType.TOPIC,
            status=ticket_status,
        )

    def test_open_ticket_returns_none(self):
        ticket = self._make_ticket(DoubtTicket.Status.OPEN)
        self.assertIsNone(DoubtService.validate_reply_allowed(ticket))

    def test_in_review_ticket_returns_none(self):
        ticket = self._make_ticket(DoubtTicket.Status.IN_REVIEW)
        self.assertIsNone(DoubtService.validate_reply_allowed(ticket))

    def test_answered_ticket_returns_none(self):
        ticket = self._make_ticket(DoubtTicket.Status.ANSWERED)
        self.assertIsNone(DoubtService.validate_reply_allowed(ticket))

    def test_closed_ticket_returns_error(self):
        ticket = self._make_ticket(DoubtTicket.Status.CLOSED)
        self.assertEqual(DoubtService.validate_reply_allowed(ticket), ErrorMessage.TICKET_CLOSED)
