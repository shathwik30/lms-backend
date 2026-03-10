from django.contrib import admin
from django.utils.html import format_html

from core.admin import ExportCsvMixin

from .models import PaymentTransaction, Purchase


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "student",
        "level",
        "amount_paid",
        "status_badge",
        "validity_badge",
        "purchased_at",
        "expires_at",
        "extended_by_days",
    )
    list_select_related = ("student__user", "level")
    list_filter = ("status", "level")
    search_fields = (
        "student__user__email",
        "level__name",
    )
    readonly_fields = ("purchased_at",)
    date_hierarchy = "purchased_at"
    list_per_page = 30
    actions = ["export_as_csv", "mark_revoked"]

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "active": "#27ae60",
            "expired": "#e67e22",
            "revoked": "#e74c3c",
        }
        color = colors.get(obj.status, "#95a5a6")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description="Valid?", boolean=True)
    def validity_badge(self, obj):
        return obj.is_valid

    @admin.action(
        description="Revoke selected purchases",
    )
    def mark_revoked(self, request, queryset):
        queryset.update(status=Purchase.Status.REVOKED)


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(
    admin.ModelAdmin,
    ExportCsvMixin,
):
    list_display = (
        "razorpay_order_id",
        "student",
        "level",
        "amount",
        "status_badge",
        "created_at",
    )
    list_select_related = ("student__user", "level")
    list_filter = ("status",)
    search_fields = (
        "razorpay_order_id",
        "razorpay_payment_id",
        "student__user__email",
    )
    readonly_fields = (
        "created_at",
        "razorpay_order_id",
        "razorpay_payment_id",
    )
    date_hierarchy = "created_at"
    list_per_page = 30
    actions = ["export_as_csv"]

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "pending": "#f39c12",
            "success": "#27ae60",
            "failed": "#e74c3c",
            "refunded": "#9b59b6",
        }
        color = colors.get(obj.status, "#95a5a6")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
