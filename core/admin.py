import csv

from django.contrib import admin
from django.http import HttpResponse


def _sanitize_csv_value(value):
    """Prevent CSV injection by escaping values starting with formula characters."""
    s = str(value) if value is not None else ""
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


class ExportCsvMixin:
    """Admin mixin: 'Export selected to CSV' action."""

    def export_as_csv(self, request, queryset):
        meta = self.model._meta  # type: ignore[attr-defined]
        field_names = [f.name for f in meta.fields]

        response = HttpResponse(content_type="text/csv")
        filename = meta.verbose_name_plural
        response["Content-Disposition"] = f"attachment; filename={filename}.csv"

        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset.iterator():
            writer.writerow([_sanitize_csv_value(getattr(obj, f)) for f in field_names])

        return response

    export_as_csv.short_description = "Export selected to CSV"  # type: ignore[attr-defined]


def make_active(modeladmin, request, queryset):
    queryset.update(is_active=True)


make_active.short_description = "Mark selected as active"  # type: ignore[attr-defined]


def make_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)


make_inactive.short_description = "Mark selected as inactive"  # type: ignore[attr-defined]


# Custom admin site
admin.site.site_header = "LMS Administration"
admin.site.site_title = "LMS Admin"
admin.site.index_title = "Dashboard"
