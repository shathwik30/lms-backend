from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.safestring import mark_safe

from core.admin import ExportCsvMixin

from .models import StudentProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin, ExportCsvMixin):
    list_display = (
        "email",
        "full_name",
        "phone",
        "role_badge",
        "is_active",
        "created_at",
    )
    list_filter = (
        "is_student",
        "is_admin",
        "is_active",
        "created_at",
    )
    search_fields = ("email", "full_name", "phone")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_per_page = 30
    actions = ["export_as_csv"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal Info",
            {
                "fields": ("full_name", "phone"),
            },
        ),
        (
            "Roles",
            {
                "fields": (
                    "is_student",
                    "is_admin",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "password1",
                    "password2",
                    "is_student",
                    "is_admin",
                ),
            },
        ),
    )

    @admin.display(description="Role")
    def role_badge(self, obj):
        if obj.is_admin:
            return mark_safe('<span style="color:#e74c3c;font-weight:bold;">Admin</span>')
        if obj.is_student:
            return mark_safe('<span style="color:#3498db;">Student</span>')
        return "—"


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = (
        "user",
        "user_email",
        "current_level",
        "highest_cleared_level",
        "created_at",
    )
    list_filter = ("current_level", "highest_cleared_level")
    search_fields = ("user__email", "user__full_name")
    raw_id_fields = ("user",)
    autocomplete_fields = (
        "current_level",
        "highest_cleared_level",
    )
    list_per_page = 30
    actions = ["export_as_csv"]

    @admin.display(
        description="Email",
        ordering="user__email",
    )
    def user_email(self, obj):
        return obj.user.email
