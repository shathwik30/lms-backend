from __future__ import annotations

from typing import Any

from django.db.models import Q

from apps.courses.models import Course, Session
from apps.exams.models import Question
from apps.levels.models import Level
from core.constants import SearchConstants


class SearchService:
    @staticmethod
    def search(query: str, level_id: int | str | None = None, week_id: int | str | None = None) -> dict[str, Any]:
        if level_id:
            levels = Level.objects.none()
        else:
            levels = Level.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query),
                is_active=True,
            )[: SearchConstants.MAX_LEVELS]

        courses_qs = Course.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query),
            is_active=True,
        ).select_related("level")
        if level_id:
            courses_qs = courses_qs.filter(level_id=level_id)
        courses = courses_qs[: SearchConstants.MAX_COURSES]

        sessions_qs = Session.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query),
            is_active=True,
        ).select_related("week")
        if level_id:
            sessions_qs = sessions_qs.filter(week__level_id=level_id)
        if week_id:
            sessions_qs = sessions_qs.filter(week_id=week_id)
        sessions = sessions_qs[: SearchConstants.MAX_SESSIONS]

        questions_qs = Question.objects.filter(
            Q(text__icontains=query),
            is_active=True,
        )
        if level_id:
            questions_qs = questions_qs.filter(level_id=level_id)
        if week_id:
            questions_qs = questions_qs.filter(week_id=week_id)
        questions_count = questions_qs.count()

        return {
            "levels": levels,
            "courses": courses,
            "sessions": sessions,
            "questions_count": questions_count,
        }
