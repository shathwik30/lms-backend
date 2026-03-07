from django.contrib import admin

from core.admin import ExportCsvMixin

from .models import Banner


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = ("title", "link_type", "order", "is_active")
    list_filter = ("link_type", "is_active")
    list_editable = ("order", "is_active")
