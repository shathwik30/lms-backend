from django.contrib import admin

from core.admin import ExportCsvMixin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = ("user", "title", "notification_type", "is_read", "created_at")
    list_select_related = ("user",)
    list_filter = ("notification_type", "is_read")
    search_fields = ("user__email", "title")
