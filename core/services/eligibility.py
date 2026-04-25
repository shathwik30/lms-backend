from __future__ import annotations

from typing import Any

from django.db.models import Count, Q
from django.utils import timezone

from apps.courses.models import Course, Session
from apps.exams.models import Exam
from apps.levels.models import Level, Week
from apps.payments.models import Purchase
from apps.progress.models import LevelProgress, SessionProgress
from apps.users.models import StudentProfile
from core.constants import NextAction, NextActionMessage


class EligibilityService:
    @staticmethod
    def get_onboarding_exam(level: Level | None) -> Exam | None:
        if level is None:
            return None
        return (
            Exam.objects.filter(
                exam_type=Exam.ExamType.ONBOARDING,
                is_active=True,
                level=level,
            )
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def has_completed_onboarding_attempt(student: StudentProfile, exam: Exam | None) -> bool:
        if exam is None:
            return False

        from apps.exams.models import ExamAttempt

        return (
            ExamAttempt.objects.filter(student=student, exam=exam)
            .exclude(status=ExamAttempt.Status.IN_PROGRESS)
            .exists()
        )

    @staticmethod
    def get_onboarding_target_level(student: StudentProfile) -> Level | None:
        if student.current_level and student.current_level.is_active:
            return student.current_level

        if student.highest_cleared_level:
            next_level = Level.objects.filter(
                order=student.highest_cleared_level.order + 1,
                is_active=True,
            ).first()
            if next_level:
                return next_level

        return Level.objects.filter(is_active=True).order_by("order").first()

    @staticmethod
    def is_syllabus_complete(student: StudentProfile, level: Level) -> bool:
        total_sessions = Session.objects.filter(
            week__course__level=level,
            week__course__is_active=True,
            is_active=True,
        ).count()

        if total_sessions == 0:
            return True

        completed = SessionProgress.objects.filter(
            student=student,
            session__week__course__level=level,
            session__is_active=True,
            is_completed=True,
        ).count()

        return completed >= total_sessions

    @staticmethod
    def is_course_complete(student: StudentProfile, course: Course) -> bool:
        total = Session.objects.filter(week__course=course, is_active=True).count()
        if total == 0:
            return True
        completed = SessionProgress.objects.filter(
            student=student,
            session__week__course=course,
            session__is_active=True,
            is_completed=True,
        ).count()
        return completed == total

    @staticmethod
    def is_week_complete(student: StudentProfile, week: Week) -> bool:
        total = Session.objects.filter(week=week, is_active=True).count()
        if total == 0:
            return True
        completed = SessionProgress.objects.filter(
            student=student,
            session__week=week,
            session__is_active=True,
            is_completed=True,
        ).count()
        return completed == total

    @staticmethod
    def has_active_purchase(student: StudentProfile, level: Level) -> bool:
        return Purchase.objects.filter(
            student=student,
            level=level,
            status=Purchase.Status.ACTIVE,
            expires_at__gt=timezone.now(),
        ).exists()

    @staticmethod
    def has_cleared_level(student: StudentProfile, level: Level) -> bool:
        return LevelProgress.objects.filter(
            student=student,
            level=level,
            status=LevelProgress.Status.EXAM_PASSED,
        ).exists()

    @staticmethod
    def has_cleared_previous_level(student: StudentProfile, level: Level) -> bool:
        if level.order <= 1:
            return True
        return LevelProgress.objects.filter(
            student=student,
            level__order=level.order - 1,
            status=LevelProgress.Status.EXAM_PASSED,
        ).exists()

    @classmethod
    def can_attempt_exam(cls, student: StudentProfile, exam: Exam) -> bool:
        if exam.exam_type == Exam.ExamType.ONBOARDING:
            if cls.has_completed_onboarding_attempt(student, exam):
                return False
            target_level = cls.get_onboarding_target_level(student)
            return bool(target_level and exam.level_id == target_level.id)

        level = exam.level

        if exam.exam_type == Exam.ExamType.LEVEL_FINAL:
            if not cls.has_active_purchase(student, level):
                return False
            if not cls.is_syllabus_complete(student, level):
                return False
            progress = LevelProgress.objects.filter(student=student, level=level).first()
            return not (progress and progress.final_exam_attempts_used >= level.max_final_exam_attempts)

        if exam.exam_type == Exam.ExamType.WEEKLY:
            if not cls.has_active_purchase(student, level):
                return False

            from apps.exams.session_sync import ExamSessionSyncService

            session = ExamSessionSyncService.sync_exam_session(exam)
            if session is None:
                return True
            return cls.is_session_accessible(student, session)

        return False

    @classmethod
    def can_purchase_level(cls, student: StudentProfile, level: Level) -> bool:
        if level.order <= 1:
            return True
        return cls.has_cleared_previous_level(student, level)

    @staticmethod
    def is_session_accessible(student: StudentProfile, session: Session) -> bool:
        from apps.progress.services import ProgressService

        week = session.week
        course = week.course
        ProgressService.sync_passed_weekly_exam_progress(student, course=course)

        # Bulk check: count total vs completed sessions for all prior weeks
        prior_week_ids = list(course.weeks.filter(order__lt=week.order, is_active=True).values_list("id", flat=True))
        if prior_week_ids:
            prior_stats = (
                Session.objects.filter(week_id__in=prior_week_ids, is_active=True)
                .values("week_id")
                .annotate(
                    total=Count("id"),
                    completed=Count(
                        "id",
                        filter=Q(
                            progress_records__student=student,
                            progress_records__is_completed=True,
                        ),
                    ),
                )
            )
            for stat in prior_stats:
                if stat["completed"] < stat["total"]:
                    return False

            # Check for weeks with no sessions (they are complete by definition — skip)

        # Bulk check: all prior sessions in current week are complete
        prior_session_ids = list(
            week.sessions.filter(order__lt=session.order, is_active=True).values_list("id", flat=True)
        )
        if prior_session_ids:
            completed_count = SessionProgress.objects.filter(
                student=student,
                session_id__in=prior_session_ids,
                is_completed=True,
            ).count()
            if completed_count < len(prior_session_ids):
                return False

        return True

    @classmethod
    def get_next_action(cls, student: StudentProfile) -> dict[str, Any]:
        # Check onboarding status — recommend the placement test if the student
        # has not yet attempted the onboarding exam at their target level.
        onboarding_level = cls.get_onboarding_target_level(student)
        onboarding_exam = cls.get_onboarding_exam(onboarding_level)
        if onboarding_exam and not cls.has_completed_onboarding_attempt(student, onboarding_exam):
            return {
                "action": NextAction.TAKE_ONBOARDING_EXAM,
                "level": {
                    "id": onboarding_level.id,
                    "name": onboarding_level.name,
                    "order": onboarding_level.order,
                },
                "exam_id": onboarding_exam.id,
                "message": NextActionMessage.take_onboarding(),
            }
        if onboarding_level is None and not student.highest_cleared_level:
            return {
                "action": NextAction.NO_LEVELS,
                "level": None,
                "message": NextActionMessage.NO_LEVELS,
            }

        # Determine current level
        if student.highest_cleared_level:
            cleared_order = student.highest_cleared_level.order
            next_level = Level.objects.filter(
                order=cleared_order + 1,
                is_active=True,
            ).first()

            if not next_level:
                return {
                    "action": NextAction.ALL_COMPLETE,
                    "level": None,
                    "message": NextActionMessage.ALL_COMPLETE,
                }
        else:
            next_level = Level.objects.filter(is_active=True).order_by("order").first()
            if not next_level:
                return {
                    "action": NextAction.NO_LEVELS,
                    "level": None,
                    "message": NextActionMessage.NO_LEVELS,
                }

        level_info = {
            "id": next_level.id,
            "name": next_level.name,
            "order": next_level.order,
        }

        # Check purchase
        if not cls.has_active_purchase(student, next_level):
            return {
                "action": NextAction.PURCHASE_LEVEL,
                "level": level_info,
                "message": NextActionMessage.purchase_level(next_level.order),
            }

        # Check progress
        progress = LevelProgress.objects.filter(
            student=student,
            level=next_level,
        ).first()

        if (
            progress
            and progress.status == LevelProgress.Status.EXAM_FAILED
            and progress.final_exam_attempts_used >= next_level.max_final_exam_attempts
        ):
            return {
                "action": NextAction.REDO_LEVEL,
                "level": level_info,
                "message": NextActionMessage.redo_level(next_level.order),
            }

        if cls.is_syllabus_complete(student, next_level):
            return {
                "action": NextAction.TAKE_FINAL_EXAM,
                "level": level_info,
                "message": NextActionMessage.take_final_exam(next_level.order),
            }

        return {
            "action": NextAction.COMPLETE_COURSES,
            "level": level_info,
            "message": NextActionMessage.complete_courses(next_level.order),
        }
