from django.contrib import admin
from django.db.models import Count

from apps.levels.models import Week
from core.admin import ExportCsvMixin, make_active, make_inactive

from .models import Course, Session


class WeekInline(admin.TabularInline):
    model = Week
    extra = 1
    ordering = ("order",)
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "title",
        "level",
        "week_count",
        "is_active",
    )
    list_filter = ("level", "is_active")
    list_editable = ("is_active",)
    list_select_related = ("level",)
    search_fields = ("title",)
    autocomplete_fields = ("level",)
    inlines = [WeekInline]
    list_per_page = 20
    actions = [make_active, make_inactive, "export_as_csv"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_week_count=Count("weeks"))

    @admin.display(description="Weeks")
    def week_count(self, obj):
        return getattr(obj, "_week_count", obj.weeks.count())


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "title",
        "week",
        "order",
        "session_type",
        "duration_display",
        "is_active",
    )
    list_filter = ("week__course__level", "session_type", "is_active")
    list_editable = ("order", "is_active")
    list_select_related = ("week__course__level",)
    search_fields = ("title",)
    ordering = (
        "week__course__level__order",
        "week__course__title",
        "week__order",
        "order",
    )
    list_per_page = 30
    actions = [make_active, make_inactive, "export_as_csv"]

    @admin.display(description="Duration")
    def duration_display(self, obj):
        if obj.duration_seconds == 0:
            return "—"
        mins, secs = divmod(obj.duration_seconds, 60)
        return f"{mins}m {secs}s"
