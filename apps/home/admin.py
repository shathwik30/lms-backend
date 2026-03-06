from django.contrib import admin

from .models import Banner


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("title", "link_type", "order", "is_active")
    list_filter = ("link_type", "is_active")
    list_editable = ("order", "is_active")
