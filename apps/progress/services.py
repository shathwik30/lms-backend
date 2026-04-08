from __future__ import annotations

import datetime
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, FloatField, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.courses.models import Course, Session
from apps.levels.models import Level, Week
from apps.users.models import StudentProfile, User
from core.constants import ErrorMessage, ProgressConstants
from core.services.eligibility import EligibilityService

from .models import CourseProgress, LevelProgress, SessionProgress


class ProgressService:
    @staticmethod
    def update_session_progress(
        profile: StudentProfile, session_pk: int, watched_seconds: int
    ) -> tuple[SessionProgress | None, str | None]:
        try:
            session = Session.objects.select_related("week__course__level").get(pk=session_pk, is_active=True)
        except Session.DoesNotExist:
            return None, ErrorMessage.SESSION_NOT_FOUND

        # Only applicable for VIDEO sessions
        if session.session_type != Session.SessionType.VIDEO:
            return None, ErrorMessage.SESSION_NOT_FOUND

        with transaction.atomic():
            progress, _ = SessionProgress.objects.select_for_update().get_or_create(
                student=profile,
                session=session,
            )

            capped = min(watched_seconds, session.duration_seconds) if session.duration_seconds > 0 else 0
            progress.watched_seconds = max(progress.watched_seconds, capped)

            if not progress.is_completed and session.duration_seconds > 0:
                threshold = session.duration_seconds * ProgressConstants.SESSION_COMPLETION_THRESHOLD
                if progress.watched_seconds >= threshold:
                    progress.is_completed = True
                    progress.completed_at = timezone.now()

            progress.save(update_fields=["watched_seconds", "is_completed", "completed_at"])

            if progress.is_completed:
                ProgressService._check_cascading_completion(profile, session)

        return progress, None

    @staticmethod
    def complete_resource_session(
        profile: StudentProfile, session_pk: int
    ) -> tuple[SessionProgress | None, str | None]:
        try:
            session = Session.objects.select_related("week__course__level").get(pk=session_pk, is_active=True)
        except Session.DoesNotExist:
            return None, ErrorMessage.SESSION_NOT_FOUND

        if session.session_type != Session.SessionType.RESOURCE:
            return None, ErrorMessage.SESSION_NOT_FOUND

        with transaction.atomic():
            progress, _ = SessionProgress.objects.get_or_create(
                student=profile,
                session=session,
            )
            if not progress.is_completed:
                progress.is_completed = True
                progress.completed_at = timezone.now()
                progress.save(update_fields=["is_completed", "completed_at"])
                ProgressService._check_cascading_completion(profile, session)

        return progress, None

    @staticmethod
    def complete_exam_session(
        profile: StudentProfile, session: Session, is_passed: bool
    ) -> tuple[SessionProgress | None, str | None]:
        with transaction.atomic():
            progress, _ = SessionProgress.objects.get_or_create(
                student=profile,
                session=session,
            )
            if is_passed:
                update_fields: list[str] = []
                if progress.is_exam_passed is not True:
                    progress.is_exam_passed = True
                    update_fields.append("is_exam_passed")
                if not progress.is_completed:
                    progress.is_completed = True
                    update_fields.append("is_completed")
                if progress.completed_at is None:
                    progress.completed_at = timezone.now()
                    update_fields.append("completed_at")
                if update_fields:
                    progress.save(update_fields=update_fields)
                ProgressService._check_cascading_completion(profile, session)
            else:
                # A later failed retake should not undo an already-cleared exam session.
                if progress.is_exam_passed is True or progress.is_completed:
                    return progress, None

                if progress.is_exam_passed is not False:
                    progress.is_exam_passed = False
                    progress.save(update_fields=["is_exam_passed"])
                # Proctored exam failure → reset week progress
                if session.session_type == Session.SessionType.PROCTORED_EXAM:
                    ProgressService.reset_week_progress(profile, session.week)

        return progress, None

    @staticmethod
    def sync_passed_weekly_exam_progress(
        profile: StudentProfile,
        *,
        course: Course | None = None,
        session_ids: list[int] | None = None,
    ) -> None:
        from apps.exams.models import Exam, ExamAttempt

        session_qs = Session.objects.filter(
            is_active=True,
            exam__isnull=False,
            exam__exam_type=Exam.ExamType.WEEKLY,
            exam__is_active=True,
        ).select_related("week__course__level")

        if course is not None:
            session_qs = session_qs.filter(week__course=course)

        if session_ids is not None:
            if not session_ids:
                return
            session_qs = session_qs.filter(pk__in=session_ids)

        sessions = list(session_qs)
        if not sessions:
            return

        progress_map = {
            progress.session_id: progress
            for progress in SessionProgress.objects.filter(
                student=profile,
                session_id__in=[session.id for session in sessions],
            )
        }

        passed_exam_ids = set(
            ExamAttempt.objects.filter(
                student=profile,
                exam_id__in=[session.exam_id for session in sessions if session.exam_id],
                status__in=[ExamAttempt.Status.SUBMITTED, ExamAttempt.Status.TIMED_OUT],
                is_passed=True,
            )
            .values_list("exam_id", flat=True)
            .distinct()
        )

        for session in sessions:
            progress = progress_map.get(session.id)
            needs_repair = progress is None or progress.is_exam_passed is not True or not progress.is_completed
            if session.exam_id in passed_exam_ids and needs_repair:
                ProgressService.complete_exam_session(profile, session, is_passed=True)

    @staticmethod
    def _check_cascading_completion(profile: StudentProfile, session: Session) -> None:
        week = session.week
        course = week.course
        level = course.level

        if not EligibilityService.is_week_complete(profile, week):
            return
        if not EligibilityService.is_course_complete(profile, course):
            return

        CourseProgress.objects.update_or_create(
            student=profile,
            course=course,
            defaults={
                "status": CourseProgress.Status.COMPLETED,
                "completed_at": timezone.now(),
            },
        )

        if EligibilityService.is_syllabus_complete(profile, level):
            LevelProgress.objects.filter(
                student=profile,
                level=level,
                status__in=[
                    LevelProgress.Status.IN_PROGRESS,
                    LevelProgress.Status.EXAM_FAILED,
                ],
            ).update(status=LevelProgress.Status.SYLLABUS_COMPLETE)

    @staticmethod
    def reset_week_progress(profile: StudentProfile, week: Week) -> None:
        SessionProgress.objects.filter(
            student=profile,
            session__week=week,
            session__is_active=True,
        ).delete()

    @staticmethod
    def reset_level_progress(profile: StudentProfile, level: Level) -> None:
        sessions = Session.objects.filter(
            week__course__level=level,
            is_active=True,
        )
        SessionProgress.objects.filter(
            student=profile,
            session__in=sessions,
        ).delete()

        CourseProgress.objects.filter(
            student=profile,
            course__level=level,
        ).delete()

        LevelProgress.objects.filter(
            student=profile,
            level=level,
        ).update(
            status=LevelProgress.Status.IN_PROGRESS,
            completed_at=None,
            final_exam_attempts_used=0,
        )

    @staticmethod
    def get_course_progress(profile: StudentProfile, course: Course) -> dict[str, Any]:
        # Two queries instead of 2*N: aggregate per-week stats
        week_stats = (
            Week.objects.filter(course=course, is_active=True)
            .order_by("order")
            .annotate(
                total_sessions=Count(
                    "sessions",
                    filter=Q(sessions__is_active=True),
                ),
                completed_sessions=Count(
                    "sessions",
                    filter=Q(
                        sessions__is_active=True,
                        sessions__progress_records__student=profile,
                        sessions__progress_records__is_completed=True,
                    ),
                ),
            )
            .values("id", "name", "order", "total_sessions", "completed_sessions")
        )

        week_data = [
            {
                "week_id": week_stat["id"],
                "week_name": week_stat["name"],
                "week_order": week_stat["order"],
                "total_sessions": week_stat["total_sessions"],
                "completed_sessions": week_stat["completed_sessions"],
                "is_complete": week_stat["completed_sessions"] == week_stat["total_sessions"]
                and week_stat["total_sessions"] > 0,
            }
            for week_stat in week_stats
        ]

        cp = CourseProgress.objects.filter(student=profile, course=course).first()
        return {
            "course_id": course.id,
            "course_title": course.title,
            "status": cp.status if cp else CourseProgress.Status.NOT_STARTED,
            "weeks": week_data,
        }

    @staticmethod
    def get_dashboard(profile: StudentProfile) -> dict[str, Any]:
        progress_qs = (
            LevelProgress.objects.filter(
                student=profile,
            )
            .select_related("level")
            .order_by("level__order")
        )

        next_info = EligibilityService.get_next_action(profile)

        course_progress_qs = CourseProgress.objects.filter(
            student=profile,
        ).select_related("course")

        return {
            "current_level": next_info["level"],
            "level_progress": progress_qs,
            "course_progress": course_progress_qs,
            "next_action": next_info["action"],
            "message": next_info["message"],
            "is_onboarding_exam_attempted": profile.is_onboarding_exam_attempted,
            "exam_id": next_info.get("exam_id"),
        }

    @staticmethod
    def get_calendar_data(profile: StudentProfile, year: int, month: int) -> list[dict[str, Any]]:
        activity = (
            SessionProgress.objects.filter(
                student=profile,
                updated_at__year=year,
                updated_at__month=month,
            )
            .annotate(date=TruncDate("updated_at"))
            .values("date")
            .annotate(sessions_watched=Count("id"))
            .order_by("date")
        )

        from apps.exams.models import ExamAttempt

        exam_dates = (
            ExamAttempt.objects.filter(
                student=profile,
                started_at__year=year,
                started_at__month=month,
            )
            .annotate(date=TruncDate("started_at"))
            .values("date")
            .annotate(exams_taken=Count("id"))
            .order_by("date")
        )

        calendar_data: dict[str, dict[str, Any]] = {}
        for entry in activity:
            date_str = entry["date"].isoformat()
            calendar_data.setdefault(date_str, {"date": date_str, "sessions_watched": 0, "exams_taken": 0})
            calendar_data[date_str]["sessions_watched"] = entry["sessions_watched"]

        for entry in exam_dates:
            date_str = entry["date"].isoformat()
            calendar_data.setdefault(date_str, {"date": date_str, "sessions_watched": 0, "exams_taken": 0})
            calendar_data[date_str]["exams_taken"] = entry["exams_taken"]

        return sorted(calendar_data.values(), key=lambda x: x["date"])

    @staticmethod
    def get_streak_data(profile: StudentProfile) -> dict[str, Any]:
        """Calculate current streak, longest streak, and streak goal progress."""
        today = timezone.now().date()

        dates: list[datetime.date] = list(
            SessionProgress.objects.filter(student=profile)
            .values_list("updated_at__date", flat=True)
            .distinct()
            .order_by("-updated_at__date")
        )

        from apps.exams.models import ExamAttempt

        exam_dates: list[datetime.date] = list(
            ExamAttempt.objects.filter(student=profile).values_list("started_at__date", flat=True).distinct()
        )

        all_active = sorted(set(dates) | set(exam_dates), reverse=True)

        # Current streak (consecutive days ending today or yesterday)
        current_streak = 0
        expected = today
        for d in all_active:
            if d == expected:
                current_streak += 1
                expected -= datetime.timedelta(days=1)
            elif d < expected:
                break

        # Longest streak (scan all dates)
        longest_streak = 0
        if all_active:
            sorted_asc = sorted(set(all_active))
            streak = 1
            for i in range(1, len(sorted_asc)):
                if (sorted_asc[i] - sorted_asc[i - 1]).days == 1:
                    streak += 1
                else:
                    longest_streak = max(longest_streak, streak)
                    streak = 1
            longest_streak = max(longest_streak, streak)

        # Streak goal and milestone
        streak_goal = 30
        if current_streak >= 15:
            next_milestone = 30
        elif current_streak >= 7:
            next_milestone = 15
        else:
            next_milestone = 7
        days_to_milestone = max(next_milestone - current_streak, 0)

        return {
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "streak_goal": streak_goal,
            "next_milestone": next_milestone,
            "days_to_milestone": days_to_milestone,
        }

    @staticmethod
    def _build_ranked_leaderboard(
        level_id: int | str | None, limit: int
    ) -> tuple[list[dict[str, Any]], list[tuple[int, dict[str, Any]]]]:
        """Build the ranked leaderboard data (expensive)."""
        from apps.exams.models import ExamAttempt

        attempts_qs = ExamAttempt.objects.filter(
            status=ExamAttempt.Status.SUBMITTED,
            is_passed=True,
            is_disqualified=False,
        )
        levels_qs = LevelProgress.objects.filter(
            status=LevelProgress.Status.EXAM_PASSED,
        )

        if level_id:
            attempts_qs = attempts_qs.filter(exam__level_id=level_id)
            levels_qs = levels_qs.filter(level_id=level_id)

        passed_attempts = attempts_qs.values("student_id").annotate(
            exams_passed=Count("id"),
            total_score=Coalesce(Sum("score"), 0.0, output_field=FloatField()),
        )

        levels_cleared = levels_qs.values("student_id").annotate(
            levels_cleared=Count("id"),
        )

        student_stats: dict[int, dict[str, Any]] = {}
        for entry in passed_attempts:
            student_id = entry["student_id"]
            student_stats[student_id] = {
                "exams_passed": entry["exams_passed"],
                "total_score": float(entry["total_score"]),
                "levels_cleared": 0,
            }

        for entry in levels_cleared:
            student_id = entry["student_id"]
            if student_id not in student_stats:
                student_stats[student_id] = {
                    "exams_passed": 0,
                    "total_score": 0.0,
                    "levels_cleared": 0,
                }
            student_stats[student_id]["levels_cleared"] = entry["levels_cleared"]

        ranked = sorted(
            student_stats.items(),
            key=lambda x: (x[1]["levels_cleared"], x[1]["total_score"]),
            reverse=True,
        )

        top_ids = [student_id for student_id, _ in ranked[:limit]]
        profiles = {p.id: p for p in StudentProfile.objects.filter(id__in=top_ids).select_related("user")}

        leaderboard = []
        for rank, (student_id, stats) in enumerate(ranked[:limit], start=1):
            profile = profiles.get(student_id)
            if not profile:
                continue
            leaderboard.append(
                {
                    "rank": rank,
                    "student_id": profile.id,
                    "full_name": profile.user.full_name,
                    "profile_picture": profile.user.profile_picture.url if profile.user.profile_picture else "",
                    "levels_cleared": stats["levels_cleared"],
                    "total_score": stats["total_score"],
                    "exams_passed": stats["exams_passed"],
                }
            )

        return leaderboard, ranked

    @staticmethod
    def get_leaderboard(
        user: User, level_id: int | str | None = None, limit: int = ProgressConstants.DEFAULT_LEADERBOARD_LIMIT
    ) -> dict[str, Any]:
        cache_key = f"leaderboard:{level_id or 'all'}:{limit}"
        leaderboard = cache.get(cache_key)

        ranked = None
        if leaderboard is None:
            leaderboard, ranked = ProgressService._build_ranked_leaderboard(level_id, limit)
            cache.set(cache_key, leaderboard, settings.CACHE_TTL_SHORT)

        my_rank = None
        if user.is_student and hasattr(user, "student_profile"):
            current_student_id = user.student_profile.id
            for entry in leaderboard:
                if entry["student_id"] == current_student_id:
                    my_rank = entry["rank"]
                    break
            if my_rank is None and ranked is not None:
                for i, (student_id, _) in enumerate(ranked, start=1):
                    if student_id == current_student_id:
                        my_rank = i
                        break

        return {"leaderboard": leaderboard, "my_rank": my_rank}
