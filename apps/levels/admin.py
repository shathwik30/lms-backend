from django.contrib import admin
from django.db.models import Count

from core.admin import ExportCsvMixin, make_active, make_inactive

from .models import Level, Week


class WeekInline(admin.TabularInline):
    model = Week
    extra = 1
    ordering = ("order",)
    show_change_link = True


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "name",
        "order",
        "passing_percentage",
        "week_count",
        "question_count",
        "is_active",
    )
    list_filter = ("is_active",)
    list_editable = ("passing_percentage", "is_active")
    search_fields = ("name",)
    ordering = ("order",)
    inlines = [WeekInline]
    list_per_page = 20
    actions = [make_active, make_inactive, "export_as_csv"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _week_count=Count("weeks", distinct=True),
                _question_count=Count("questions", distinct=True),
            )
        )

    @admin.display(description="Weeks")
    def week_count(self, obj):
        return getattr(obj, "_week_count", obj.weeks.count())

    @admin.display(description="Questions")
    def question_count(self, obj):
        return getattr(obj, "_question_count", obj.questions.count())


@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "level",
        "order",
        "session_count",
        "is_active",
    )
    list_filter = ("level", "is_active")
    list_editable = ("is_active",)
    list_select_related = ("level",)
    ordering = ("level__order", "order")
    actions = [make_active, make_inactive]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_session_count=Count("sessions"))

    @admin.display(description="Sessions")
    def session_count(self, obj):
        return getattr(obj, "_session_count", obj.sessions.count())
