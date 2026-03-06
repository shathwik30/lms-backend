from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.payments.models import Purchase
from apps.users.models import StudentProfile
from apps.users.models import User as UserModel
from core.constants import ErrorMessage

from .models import DoubtReply, DoubtTicket

User = get_user_model()


class DoubtService:
    @staticmethod
    def validate_doubt_access(profile: StudentProfile, context_type: str, validated_data: dict) -> None:
        level = None
        if context_type == DoubtTicket.ContextType.SESSION:
            session = validated_data.get("session")
            if session:
                level = session.week.level
        elif context_type == DoubtTicket.ContextType.EXAM_QUESTION:
            question = validated_data.get("exam_question")
            if question:
                level = question.level

        if level is not None:
            has_purchase = Purchase.objects.filter(
                student=profile,
                course__level=level,
                status=Purchase.Status.ACTIVE,
            ).exists()
            if not has_purchase:
                raise PermissionDenied(ErrorMessage.PURCHASE_REQUIRED_FOR_DOUBT)

    @staticmethod
    def admin_reply(ticket: DoubtTicket, author: UserModel, reply: DoubtReply) -> None:
        if ticket.status == DoubtTicket.Status.OPEN:
            ticket.status = DoubtTicket.Status.IN_REVIEW
            ticket.save()

        student_user = ticket.student.user

        NotificationService.create(
            user=student_user,
            title=f"New reply on: {ticket.title}",
            message=reply.message[:200],
            notification_type=Notification.NotificationType.DOUBT_REPLY,
            data={"ticket_id": ticket.id},
        )

        from core.tasks import send_doubt_reply_task

        send_doubt_reply_task.delay(
            email=student_user.email,
            full_name=student_user.full_name,
            ticket_title=ticket.title,
            reply_author=author.full_name,
            reply_preview=reply.message[:200],
        )

    @staticmethod
    def assign_ticket(ticket: DoubtTicket, faculty_id: int) -> tuple[DoubtTicket | None, str | None]:
        try:
            faculty = User.objects.get(pk=faculty_id)
        except User.DoesNotExist:
            return None, ErrorMessage.USER_NOT_FOUND

        if not (faculty.is_staff or faculty.is_superuser):
            return None, ErrorMessage.ASSIGN_STAFF_ONLY

        ticket.assigned_to = faculty
        ticket.status = DoubtTicket.Status.IN_REVIEW
        ticket.save()

        return ticket, None

    @staticmethod
    def update_status(ticket: DoubtTicket, new_status: str) -> tuple[DoubtTicket | None, str | None]:
        if new_status not in dict(DoubtTicket.Status.choices):
            return None, f"Invalid status. Choose from: {list(dict(DoubtTicket.Status.choices).keys())}"

        ticket.status = new_status
        ticket.save()
        return ticket, None

    @staticmethod
    def update_bonus_marks(ticket: DoubtTicket, bonus_marks: int) -> DoubtTicket:
        ticket.bonus_marks = bonus_marks
        ticket.save()
        return ticket
