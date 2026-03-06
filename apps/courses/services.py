from __future__ import annotations

from django.utils import timezone

from apps.levels.models import Level
from apps.payments.models import Purchase
from apps.users.models import StudentProfile


class CourseAccessService:
    @staticmethod
    def has_course_access(profile: StudentProfile, course_id: int) -> bool:
        return Purchase.objects.filter(
            student=profile,
            course_id=course_id,
            status=Purchase.Status.ACTIVE,
            expires_at__gt=timezone.now(),
        ).exists()

    @staticmethod
    def has_level_access(profile: StudentProfile, level: Level) -> bool:
        return Purchase.objects.filter(
            student=profile,
            course__level=level,
            status=Purchase.Status.ACTIVE,
            expires_at__gt=timezone.now(),
        ).exists()
