from django.contrib import admin

from core.admin import ExportCsvMixin

from .models import SessionFeedback


@admin.register(SessionFeedback)
class SessionFeedbackAdmin(
    admin.ModelAdmin,
    ExportCsvMixin,
):
    list_display = (
        "student",
        "session",
        "rating",
        "difficulty_rating",
        "clarity_rating",
        "comment_preview",
        "created_at",
    )
    list_select_related = ("student__user", "session")
    list_filter = (
        "rating",
        "session__week__course__level",
    )
    search_fields = (
        "student__user__email",
        "session__title",
        "comment",
    )
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    list_per_page = 30
    actions = ["export_as_csv"]

    @admin.display(description="Comment")
    def comment_preview(self, obj):
        if not obj.comment:
            return "—"
        if len(obj.comment) > 60:
            return obj.comment[:60] + "..."
        return obj.comment
