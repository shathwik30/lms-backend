from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.courses.models import Session
from apps.payments.models import Purchase
from apps.users.models import StudentProfile
from core.constants import ErrorMessage

from .models import SessionFeedback


class FeedbackService:
    @staticmethod
    def submit(
        profile: StudentProfile, session_pk: int, validated_data: dict[str, Any]
    ) -> tuple[SessionFeedback | None, str | None]:
        try:
            session = Session.objects.select_related("week__course__level").get(
                pk=session_pk,
                is_active=True,
            )
        except Session.DoesNotExist:
            return None, ErrorMessage.SESSION_NOT_FOUND

        level = session.week.course.level
        has_purchase = Purchase.objects.filter(
            student=profile,
            level=level,
            status=Purchase.Status.ACTIVE,
            expires_at__gt=timezone.now(),
        ).exists()
        if not has_purchase:
            return None, ErrorMessage.PURCHASE_REQUIRED_FOR_FEEDBACK

        if SessionFeedback.objects.filter(student=profile, session=session).exists():
            return None, ErrorMessage.FEEDBACK_ALREADY_SUBMITTED

        feedback = SessionFeedback.objects.create(
            student=profile,
            session=session,
            **validated_data,
        )
        return feedback, None
