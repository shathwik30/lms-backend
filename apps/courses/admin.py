from django.contrib import admin
from django.db.models import Count

from core.admin import ExportCsvMixin, make_active, make_inactive

from .models import Course, Resource, Session


class ResourceInline(admin.TabularInline):
    model = Resource
    fk_name = "session"
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "title",
        "level",
        "price",
        "validity_days",
        "purchase_count",
        "is_active",
    )
    list_filter = ("level", "is_active")
    list_editable = ("price", "is_active")
    list_select_related = ("level",)
    search_fields = ("title",)
    autocomplete_fields = ("level",)
    list_per_page = 20
    actions = [make_active, make_inactive, "export_as_csv"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_purchase_count=Count("purchases"))

    @admin.display(description="Purchases")
    def purchase_count(self, obj):
        return getattr(obj, "_purchase_count", obj.purchases.count())


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "title",
        "week",
        "order",
        "duration_display",
        "is_active",
    )
    list_filter = ("week__level", "is_active")
    list_editable = ("order", "is_active")
    list_select_related = ("week__level",)
    search_fields = ("title",)
    ordering = (
        "week__level__order",
        "week__order",
        "order",
    )
    inlines = [ResourceInline]
    list_per_page = 30
    actions = [make_active, make_inactive, "export_as_csv"]

    @admin.display(description="Duration")
    def duration_display(self, obj):
        mins, secs = divmod(obj.duration_seconds, 60)
        return f"{mins}m {secs}s"


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "title",
        "resource_type",
        "session",
        "week",
        "created_at",
    )
    list_filter = ("resource_type", "session__week__level")
    search_fields = ("title",)
    list_per_page = 30
    actions = ["export_as_csv"]
