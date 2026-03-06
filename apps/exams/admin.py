from django.contrib import admin
from django.utils.safestring import mark_safe

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
        "level",
        "week",
        "difficulty",
        "question_type",
        "marks",
        "negative_marks",
        "option_count",
        "is_active",
    )
    list_filter = (
        "level",
        "week",
        "difficulty",
        "question_type",
        "is_active",
    )
    list_editable = ("difficulty", "marks", "negative_marks", "is_active")
    search_fields = ("text",)
    inlines = [OptionInline]
    list_per_page = 30
    actions = [make_active, make_inactive, "export_as_csv"]

    @admin.display(description="Text")
    def text_preview(self, obj):
        if len(obj.text) > 80:
            return obj.text[:80] + "..."
        return obj.text

    @admin.display(description="Options")
    def option_count(self, obj):
        return obj.options.count()


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "title",
        "level",
        "week",
        "exam_type",
        "duration_minutes",
        "num_questions",
        "passing_percentage",
        "is_proctored",
        "max_warnings",
        "attempt_count",
        "is_active",
    )
    list_filter = ("level", "exam_type", "is_proctored", "is_active")
    list_editable = ("is_active",)
    search_fields = ("title",)
    list_per_page = 20
    actions = [make_active, make_inactive, "export_as_csv"]

    @admin.display(description="Attempts")
    def attempt_count(self, obj):
        return obj.attempts.count()


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
            return mark_safe('<span style="color:#e67e22;font-weight:bold;">DISQUALIFIED</span>')
        if obj.is_passed is None:
            return "—"
        if obj.is_passed:
            return mark_safe('<span style="color:#27ae60;font-weight:bold;">PASSED</span>')
        return mark_safe('<span style="color:#e74c3c;font-weight:bold;">FAILED</span>')


@admin.register(ProctoringViolation)
class ProctoringViolationAdmin(admin.ModelAdmin):
    list_display = ("attempt", "violation_type", "warning_number", "created_at")
    list_filter = ("violation_type",)
    search_fields = ("attempt__student__user__email",)
    readonly_fields = ("attempt", "violation_type", "warning_number", "details", "created_at")
    list_per_page = 50
