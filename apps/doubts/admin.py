from django.contrib import admin
from django.utils.html import format_html

from core.admin import ExportCsvMixin

from .models import DoubtReply, DoubtTicket


class DoubtReplyInline(admin.StackedInline):
    model = DoubtReply
    extra = 0
    readonly_fields = ("author", "created_at")


@admin.register(DoubtTicket)
class DoubtTicketAdmin(
    admin.ModelAdmin,
    ExportCsvMixin,
):
    list_display = (
        "pk",
        "title_preview",
        "student",
        "status_badge",
        "context_type",
        "assigned_to",
        "reply_count",
        "bonus_marks",
        "created_at",
    )
    list_filter = (
        "status",
        "context_type",
        "assigned_to",
    )
    list_editable = ("bonus_marks",)
    search_fields = (
        "title",
        "student__user__email",
        "description",
    )
    raw_id_fields = ("student", "assigned_to")
    date_hierarchy = "created_at"
    inlines = [DoubtReplyInline]
    list_per_page = 30
    actions = [
        "export_as_csv",
        "mark_closed",
        "mark_answered",
    ]

    @admin.display(description="Title")
    def title_preview(self, obj):
        if len(obj.title) > 60:
            return obj.title[:60] + "..."
        return obj.title

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "open": "#3498db",
            "in_review": "#f39c12",
            "answered": "#27ae60",
            "closed": "#95a5a6",
        }
        color = colors.get(obj.status, "#95a5a6")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description="Replies")
    def reply_count(self, obj):
        return obj.replies.count()

    @admin.action(
        description="Mark selected as closed",
    )
    def mark_closed(self, request, queryset):
        queryset.update(
            status=DoubtTicket.Status.CLOSED,
        )

    @admin.action(
        description="Mark selected as answered",
    )
    def mark_answered(self, request, queryset):
        queryset.update(
            status=DoubtTicket.Status.ANSWERED,
        )
