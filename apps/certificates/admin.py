from django.contrib import admin

from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("certificate_number", "student", "level", "issued_at", "score")
    list_filter = ("level",)
    search_fields = ("certificate_number", "student__user__email")
    readonly_fields = ("certificate_number",)
