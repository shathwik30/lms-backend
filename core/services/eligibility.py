from django.utils import timezone

from apps.courses.models import Session
from apps.exams.models import Exam
from apps.feedback.models import SessionFeedback
from apps.payments.models import Purchase
from apps.progress.models import LevelProgress, SessionProgress
from core.constants import NextAction, NextActionMessage


class EligibilityService:
    @staticmethod
    def is_syllabus_complete(student, level):
        all_sessions = Session.objects.filter(week__level=level, is_active=True)
        total = all_sessions.count()
        if total == 0:
            return True

        completed = SessionProgress.objects.filter(
            student=student,
            session__in=all_sessions,
            is_completed=True,
        ).count()
        feedbacks = SessionFeedback.objects.filter(
            student=student,
            session__in=all_sessions,
        ).count()
        return completed == total and feedbacks == total

    @staticmethod
    def has_active_purchase(student, level):
        return Purchase.objects.filter(
            student=student,
            course__level=level,
            status=Purchase.Status.ACTIVE,
            expires_at__gt=timezone.now(),
        ).exists()

    @staticmethod
    def has_cleared_level(student, level):
        return LevelProgress.objects.filter(
            student=student,
            level=level,
            status=LevelProgress.Status.EXAM_PASSED,
        ).exists()

    @staticmethod
    def has_cleared_previous_level(student, level):
        if level.order <= 1:
            return True
        return LevelProgress.objects.filter(
            student=student,
            level__order=level.order - 1,
            status=LevelProgress.Status.EXAM_PASSED,
        ).exists()

    @classmethod
    def can_attempt_exam(cls, student, exam):
        level = exam.level

        if level.order == 1 and exam.exam_type == Exam.ExamType.LEVEL_FINAL:
            failed_before = LevelProgress.objects.filter(
                student=student,
                level=level,
                status=LevelProgress.Status.EXAM_FAILED,
            ).exists()
            if failed_before:
                if not cls.has_active_purchase(student, level):
                    return False
                return cls.is_syllabus_complete(student, level)
            return True

        if exam.exam_type == Exam.ExamType.WEEKLY:
            if not cls.has_active_purchase(student, level):
                return False
            if exam.week:
                week_sessions = Session.objects.filter(week=exam.week, is_active=True)
                completed = SessionProgress.objects.filter(
                    student=student,
                    session__in=week_sessions,
                    is_completed=True,
                ).count()
                feedbacks = SessionFeedback.objects.filter(
                    student=student,
                    session__in=week_sessions,
                ).count()
                total = week_sessions.count()
                return completed == total and feedbacks == total
            return True

        if not cls.has_cleared_previous_level(student, level):
            return False

        if cls.has_active_purchase(student, level):
            return cls.is_syllabus_complete(student, level)

        return True

    @classmethod
    def can_purchase_course(cls, student, course):
        level = course.level
        if level.order == 1:
            return True
        return cls.has_cleared_previous_level(student, level)

    @classmethod
    def get_next_action(cls, student):
        from apps.levels.models import Level

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

        progress = LevelProgress.objects.filter(
            student=student,
            level=next_level,
        ).first()

        if not progress:
            return {
                "action": NextAction.ATTEMPT_EXAM,
                "level": level_info,
                "message": NextActionMessage.attempt_exam(next_level.order),
            }

        if progress.status == LevelProgress.Status.EXAM_FAILED:
            if cls.has_active_purchase(student, next_level):
                if cls.is_syllabus_complete(student, next_level):
                    return {
                        "action": NextAction.ATTEMPT_EXAM,
                        "level": level_info,
                        "message": NextActionMessage.retry_exam(next_level.order),
                    }
                return {
                    "action": NextAction.COMPLETE_SYLLABUS,
                    "level": level_info,
                    "message": NextActionMessage.complete_syllabus_to_unlock(next_level.order),
                }
            return {
                "action": NextAction.PURCHASE_COURSE,
                "level": level_info,
                "message": NextActionMessage.purchase_course_to_retry(next_level.order),
            }

        if progress.status == LevelProgress.Status.IN_PROGRESS:
            return {
                "action": NextAction.COMPLETE_SYLLABUS,
                "level": level_info,
                "message": NextActionMessage.complete_syllabus(next_level.order),
            }

        if progress.status == LevelProgress.Status.SYLLABUS_COMPLETE:
            return {
                "action": NextAction.ATTEMPT_EXAM,
                "level": level_info,
                "message": NextActionMessage.syllabus_complete_attempt(next_level.order),
            }

        return {
            "action": NextAction.ATTEMPT_EXAM,
            "level": level_info,
            "message": NextActionMessage.attempt_exam(next_level.order),
        }
