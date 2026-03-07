from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone

from apps.levels.models import Level
from apps.payments.models import Purchase
from apps.progress.models import SessionProgress
from apps.users.models import StudentProfile
from core.services.eligibility import EligibilityService

if TYPE_CHECKING:
    from apps.courses.models import Session


class CourseAccessService:
    @staticmethod
    def has_course_access(profile: StudentProfile, course_id: int) -> bool:
        from apps.courses.models import Course

        try:
            course = Course.objects.select_related("level").get(pk=course_id, is_active=True)
        except Course.DoesNotExist:
            return False
        return Purchase.objects.filter(
            student=profile,
            level=course.level,
            status=Purchase.Status.ACTIVE,
            expires_at__gt=timezone.now(),
        ).exists()

    @staticmethod
    def has_level_access(profile: StudentProfile, level: Level) -> bool:
        return Purchase.objects.filter(
            student=profile,
            level=level,
            status=Purchase.Status.ACTIVE,
            expires_at__gt=timezone.now(),
        ).exists()

    @staticmethod
    def is_session_accessible(profile: StudentProfile, session) -> bool:
        return EligibilityService.is_session_accessible(profile, session)

    @staticmethod
    def get_next_session(profile: StudentProfile, course) -> Session | None:
        from apps.courses.models import Session

        # Single query: get all active sessions ordered by week then session order
        all_sessions = list(
            Session.objects.filter(
                week__course=course,
                week__is_active=True,
                is_active=True,
            )
            .order_by("week__order", "order")
            .values_list("id", flat=True)
        )
        if not all_sessions:
            return None

        # Single query: get completed session IDs
        completed_ids = set(
            SessionProgress.objects.filter(
                student=profile,
                session_id__in=all_sessions,
                is_completed=True,
            ).values_list("session_id", flat=True)
        )

        # Find first incomplete session
        for session_id in all_sessions:
            if session_id not in completed_ids:
                return Session.objects.get(pk=session_id)

        return None
