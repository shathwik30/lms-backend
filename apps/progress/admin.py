from django.contrib import admin
from django.utils.html import format_html

from core.admin import ExportCsvMixin

from .models import CourseProgress, LevelProgress, SessionProgress


@admin.register(SessionProgress)
class SessionProgressAdmin(
    admin.ModelAdmin,
    ExportCsvMixin,
):
    list_display = (
        "student",
        "session",
        "watch_progress",
        "is_completed",
        "is_exam_passed",
        "completed_at",
    )
    list_select_related = ("student__user", "session")
    list_filter = ("is_completed", "is_exam_passed")
    search_fields = (
        "student__user__email",
        "session__title",
    )
    readonly_fields = ("completed_at",)
    list_per_page = 30
    actions = ["export_as_csv"]

    @admin.display(description="Progress")
    def watch_progress(self, obj):
        total = obj.session.duration_seconds
        if total == 0:
            return "—"
        pct = min(100, obj.watched_seconds / total * 100)
        if pct >= 90:
            color = "#27ae60"
        elif pct >= 50:
            color = "#f39c12"
        else:
            color = "#e74c3c"
        return format_html(
            '<span style="color:{};">{}%</span> ({}/{}s)',
            color,
            f"{pct:.0f}",
            obj.watched_seconds,
            total,
        )


@admin.register(CourseProgress)
class CourseProgressAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "student",
        "course",
        "status",
        "started_at",
        "completed_at",
    )
    list_select_related = ("student__user", "course")
    list_filter = ("status", "course__level")
    search_fields = (
        "student__user__email",
        "course__title",
    )
    readonly_fields = ("started_at", "completed_at")
    list_per_page = 30
    actions = ["export_as_csv"]


@admin.register(LevelProgress)
class LevelProgressAdmin(
    admin.ModelAdmin,
    ExportCsvMixin,
):
    list_display = (
        "student",
        "level",
        "status_badge",
        "final_exam_attempts_used",
        "started_at",
        "completed_at",
    )
    list_select_related = ("student__user", "level")
    list_filter = ("status", "level")
    search_fields = (
        "student__user__email",
        "level__name",
    )
    readonly_fields = ("started_at", "completed_at")
    list_per_page = 30
    actions = ["export_as_csv"]

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "not_started": "#95a5a6",
            "in_progress": "#3498db",
            "syllabus_complete": "#f39c12",
            "exam_passed": "#27ae60",
            "exam_failed": "#e74c3c",
        }
        color = colors.get(obj.status, "#95a5a6")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
