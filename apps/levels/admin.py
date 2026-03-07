from django.contrib import admin
from django.db.models import Count

from core.admin import ExportCsvMixin, make_active, make_inactive

from .models import Level, Week


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "name",
        "order",
        "price",
        "validity_days",
        "max_final_exam_attempts",
        "passing_percentage",
        "course_count",
        "question_count",
        "is_active",
    )
    list_filter = ("is_active",)
    list_editable = ("price", "validity_days", "max_final_exam_attempts", "passing_percentage", "is_active")
    search_fields = ("name",)
    ordering = ("order",)
    list_per_page = 20
    actions = [make_active, make_inactive, "export_as_csv"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _course_count=Count("courses", distinct=True),
                _question_count=Count("questions", distinct=True),
            )
        )

    @admin.display(description="Courses")
    def course_count(self, obj):
        return getattr(obj, "_course_count", obj.courses.count())

    @admin.display(description="Questions")
    def question_count(self, obj):
        return getattr(obj, "_question_count", obj.questions.count())


@admin.register(Week)
class WeekAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "name",
        "course",
        "order",
        "session_count",
        "is_active",
    )
    list_filter = ("course__level", "is_active")
    list_editable = ("is_active",)
    list_select_related = ("course",)
    ordering = ("course__level__order", "course__title", "order")
    actions = [make_active, make_inactive]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_session_count=Count("sessions"))

    @admin.display(description="Sessions")
    def session_count(self, obj):
        return getattr(obj, "_session_count", obj.sessions.count())
