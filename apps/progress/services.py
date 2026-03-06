from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, FloatField, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.courses.models import Session
from apps.feedback.models import SessionFeedback
from apps.users.models import StudentProfile, User
from core.constants import ErrorMessage, ProgressConstants
from core.services.eligibility import EligibilityService

from .models import LevelProgress, SessionProgress


class ProgressService:
    @staticmethod
    def update_session_progress(
        profile: StudentProfile, session_pk: int, watched_seconds: int
    ) -> tuple[SessionProgress | None, str | None]:
        try:
            session = Session.objects.get(pk=session_pk, is_active=True)
        except Session.DoesNotExist:
            return None, ErrorMessage.SESSION_NOT_FOUND

        progress, _ = SessionProgress.objects.get_or_create(
            student=profile,
            session=session,
        )

        capped = min(watched_seconds, session.duration_seconds)
        progress.watched_seconds = max(progress.watched_seconds, capped)

        if not progress.is_completed:
            threshold = session.duration_seconds * ProgressConstants.SESSION_COMPLETION_THRESHOLD
            has_feedback = SessionFeedback.objects.filter(
                student=profile,
                session=session,
            ).exists()
            if progress.watched_seconds >= threshold and has_feedback:
                progress.is_completed = True
                progress.completed_at = timezone.now()

        progress.save()

        level = session.week.level
        if EligibilityService.is_syllabus_complete(profile, level):
            LevelProgress.objects.filter(
                student=profile,
                level=level,
                status=LevelProgress.Status.IN_PROGRESS,
            ).update(status=LevelProgress.Status.SYLLABUS_COMPLETE)

        return progress, None

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

        return {
            "current_level": next_info["level"],
            "level_progress": progress_qs,
            "next_action": next_info["action"],
            "message": next_info["message"],
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
    def _build_ranked_leaderboard(
        level_id: int | str | None, limit: int
    ) -> tuple[list[dict[str, Any]], list[tuple[int, dict[str, Any]]]]:
        """Build the ranked leaderboard data (expensive, cached)."""
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
            sid = entry["student_id"]
            student_stats[sid] = {
                "exams_passed": entry["exams_passed"],
                "total_score": float(entry["total_score"]),
                "levels_cleared": 0,
            }

        for entry in levels_cleared:
            sid = entry["student_id"]
            if sid not in student_stats:
                student_stats[sid] = {
                    "exams_passed": 0,
                    "total_score": 0.0,
                    "levels_cleared": 0,
                }
            student_stats[sid]["levels_cleared"] = entry["levels_cleared"]

        ranked = sorted(
            student_stats.items(),
            key=lambda x: (x[1]["levels_cleared"], x[1]["total_score"]),
            reverse=True,
        )

        top_ids = [sid for sid, _ in ranked[:limit]]
        profiles = {p.id: p for p in StudentProfile.objects.filter(id__in=top_ids).select_related("user")}

        leaderboard = []
        for rank, (sid, stats) in enumerate(ranked[:limit], start=1):
            profile = profiles.get(sid)
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
        cached = cache.get(cache_key)

        if cached:
            leaderboard, ranked = cached
        else:
            leaderboard, ranked = ProgressService._build_ranked_leaderboard(level_id, limit)
            cache.set(cache_key, (leaderboard, ranked), settings.CACHE_TTL_SHORT)

        my_rank = None
        if user.is_student and hasattr(user, "student_profile"):
            my_id = user.student_profile.id
            for i, (sid, _) in enumerate(ranked, start=1):
                if sid == my_id:
                    my_rank = i
                    break

        return {"leaderboard": leaderboard, "my_rank": my_rank}
