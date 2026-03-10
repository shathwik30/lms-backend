from django.contrib import admin
from django.utils.html import format_html

from core.admin import ExportCsvMixin

from .models import DailyRevenue, LevelAnalytics


@admin.register(DailyRevenue)
class DailyRevenueAdmin(
    admin.ModelAdmin,
    ExportCsvMixin,
):
    list_display = (
        "date",
        "total_revenue_display",
        "total_transactions",
    )
    ordering = ("-date",)
    date_hierarchy = "date"
    list_per_page = 30
    actions = ["export_as_csv"]

    @admin.display(
        description="Revenue",
        ordering="total_revenue",
    )
    def total_revenue_display(self, obj):
        return format_html(
            "<strong>\u20b9{}</strong>",
            obj.total_revenue,
        )


@admin.register(LevelAnalytics)
class LevelAnalyticsAdmin(
    admin.ModelAdmin,
    ExportCsvMixin,
):
    list_display = (
        "level",
        "date",
        "total_attempts",
        "total_passes",
        "total_failures",
        "pass_rate",
        "total_purchases",
        "revenue_display",
    )
    list_filter = ("level",)
    ordering = ("-date",)
    date_hierarchy = "date"
    list_per_page = 30
    actions = ["export_as_csv"]

    @admin.display(description="Pass Rate")
    def pass_rate(self, obj):
        total = obj.total_passes + obj.total_failures
        if total == 0:
            return "—"
        pass_rate_value = obj.total_passes / total * 100
        if pass_rate_value >= 60:
            color = "#27ae60"
        else:
            color = "#e74c3c"
        return format_html(
            '<span style="color:{};">{}%</span>',
            color,
            f"{pass_rate_value:.0f}",
        )

    @admin.display(
        description="Revenue",
        ordering="revenue",
    )
    def revenue_display(self, obj):
        return format_html(
            "<strong>\u20b9{}</strong>",
            obj.revenue,
        )
