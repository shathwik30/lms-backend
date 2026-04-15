from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from core.admin import ExportCsvMixin, make_active, make_inactive

from .models import (
    AttemptQuestion,
    Exam,
    ExamAttempt,
    Option,
    ProctoringViolation,
    Question,
)


class OptionInline(admin.TabularInline):
    model = Option
    extra = 4


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "pk",
        "text_preview",
        "exam",
        "level",
        "difficulty",
        "question_type",
        "marks",
        "negative_marks",
        "option_count",
        "is_active",
    )
    list_select_related = ("exam", "level")
    list_filter = (
        "exam",
        "exam__level",
        "exam__exam_type",
        "difficulty",
        "question_type",
        "is_active",
    )
    list_editable = ("difficulty", "marks", "negative_marks", "is_active")
    search_fields = ("text",)
    inlines = [OptionInline]
    list_per_page = 30
    actions = [make_active, make_inactive, "export_as_csv"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_option_count=Count("options"))

    @admin.display(description="Text")
    def text_preview(self, obj):
        if len(obj.text) > 80:
            return obj.text[:80] + "..."
        return obj.text

    @admin.display(description="Options")
    def option_count(self, obj):
        return getattr(obj, "_option_count", obj.options.count())


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "title",
        "level",
        "week",
        "course",
        "exam_type",
        "duration_minutes",
        "num_questions",
        "passing_percentage",
        "is_proctored",
        "require_fullscreen",
        "detect_tab_switch",
        "max_warnings",
        "question_count",
        "attempt_count",
        "is_active",
    )
    list_select_related = ("level", "week", "course")
    list_filter = ("level", "course", "exam_type", "is_proctored", "is_active")
    list_editable = ("is_active",)
    search_fields = ("title",)
    list_per_page = 20
    actions = [make_active, make_inactive, "export_as_csv"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _question_count=Count("questions", distinct=True),
                _attempt_count=Count("attempts", distinct=True),
            )
        )

    @admin.display(description="Pool")
    def question_count(self, obj):
        return getattr(obj, "_question_count", obj.questions.count())

    @admin.display(description="Attempts")
    def attempt_count(self, obj):
        return getattr(obj, "_attempt_count", obj.attempts.count())


class AttemptQuestionInline(admin.TabularInline):
    model = AttemptQuestion
    extra = 0
    readonly_fields = (
        "question",
        "selected_option",
        "is_correct",
        "marks_awarded",
        "order",
    )
    can_delete = False


class ViolationInline(admin.TabularInline):
    model = ProctoringViolation
    extra = 0
    readonly_fields = ("violation_type", "warning_number", "details", "created_at")
    can_delete = False


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "student",
        "exam",
        "status",
        "score_display",
        "pass_badge",
        "is_disqualified",
        "started_at",
        "submitted_at",
    )
    list_select_related = ("student__user", "exam")
    list_filter = (
        "status",
        "is_passed",
        "is_disqualified",
        "exam__level",
        "exam__exam_type",
    )
    search_fields = (
        "student__user__email",
        "exam__title",
    )
    readonly_fields = (
        "started_at",
        "submitted_at",
        "score",
        "total_marks",
        "is_passed",
        "is_disqualified",
    )
    date_hierarchy = "started_at"
    inlines = [AttemptQuestionInline, ViolationInline]
    list_per_page = 30
    actions = ["export_as_csv"]

    @admin.display(description="Score")
    def score_display(self, obj):
        if obj.score is not None:
            if obj.total_marks:
                pct = obj.score / obj.total_marks * 100
            else:
                pct = 0
            return f"{obj.score}/{obj.total_marks} ({pct:.0f}%)"
        return "—"

    @admin.display(
        description="Result",
        ordering="is_passed",
    )
    def pass_badge(self, obj):
        if obj.is_disqualified:
            return format_html('<span style="color:{};font-weight:bold;">{}</span>', "#e67e22", "DISQUALIFIED")
        if obj.is_passed is None:
            return "—"
        if obj.is_passed:
            return format_html('<span style="color:{};font-weight:bold;">{}</span>', "#27ae60", "PASSED")
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', "#e74c3c", "FAILED")


@admin.register(ProctoringViolation)
class ProctoringViolationAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = ("attempt", "violation_type", "warning_number", "created_at")
    list_select_related = ("attempt__student__user", "attempt__exam")
    list_filter = ("violation_type",)
    search_fields = ("attempt__student__user__email",)
    readonly_fields = ("attempt", "violation_type", "warning_number", "details", "created_at")
    list_per_page = 50
