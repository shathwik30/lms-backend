from __future__ import annotations

from django.db.models import Max

from apps.courses.models import Session

from .models import Exam


class ExamSessionSyncService:
    @staticmethod
    def _next_order(week_id: int, exclude_session_id: int | None = None) -> int:
        qs = Session.objects.filter(week_id=week_id)
        if exclude_session_id is not None:
            qs = qs.exclude(pk=exclude_session_id)
        max_order = qs.aggregate(max_order=Max("order"))["max_order"] or 0
        return max_order + 1

    @staticmethod
    def _session_type_for_exam(exam: Exam) -> str:
        if exam.is_proctored:
            return Session.SessionType.PROCTORED_EXAM
        return Session.SessionType.PRACTICE_EXAM

    @classmethod
    def get_linked_session(cls, exam: Exam) -> Session | None:
        return Session.objects.filter(exam=exam).order_by("pk").first()

    @classmethod
    def delete_linked_sessions(cls, exam: Exam) -> int:
        deleted, _ = Session.objects.filter(exam=exam).delete()
        return deleted

    @classmethod
    def sync_exam_session(cls, exam: Exam) -> Session | None:
        if exam.exam_type != Exam.ExamType.WEEKLY or not exam.week_id:
            cls.delete_linked_sessions(exam)
            return None

        session = cls.get_linked_session(exam)
        desired_duration = exam.duration_minutes * 60
        desired_type = cls._session_type_for_exam(exam)

        if session is None:
            return Session.objects.create(
                week_id=exam.week_id,
                title=exam.title,
                duration_seconds=desired_duration,
                order=cls._next_order(exam.week_id),
                session_type=desired_type,
                exam=exam,
                is_active=exam.is_active,
            )

        update_fields: list[str] = []
        if session.week_id != exam.week_id:
            session.week_id = exam.week_id
            session.order = cls._next_order(exam.week_id, exclude_session_id=session.pk)
            update_fields.extend(["week", "order"])
        if session.title != exam.title:
            session.title = exam.title
            update_fields.append("title")
        if session.duration_seconds != desired_duration:
            session.duration_seconds = desired_duration
            update_fields.append("duration_seconds")
        if session.session_type != desired_type:
            session.session_type = desired_type
            update_fields.append("session_type")
        if session.exam_id != exam.id:
            session.exam = exam
            update_fields.append("exam")
        if session.is_active != exam.is_active:
            session.is_active = exam.is_active
            update_fields.append("is_active")

        # Weekly exams should behave like exam sessions, not like videos/resources.
        if session.video_url:
            session.video_url = ""
            update_fields.append("video_url")
        if session.file_url:
            session.file_url = ""
            update_fields.append("file_url")
        if session.resource_type:
            session.resource_type = ""
            update_fields.append("resource_type")
        if session.markdown_content:
            session.markdown_content = ""
            update_fields.append("markdown_content")

        if update_fields:
            session.save(update_fields=update_fields)

        return session

    @classmethod
    def sync_weekly_exam_sessions_for_course(cls, course_id: int) -> None:
        exams = Exam.objects.filter(
            exam_type=Exam.ExamType.WEEKLY,
            week__course_id=course_id,
        ).select_related("week")
        for exam in exams:
            cls.sync_exam_session(exam)
