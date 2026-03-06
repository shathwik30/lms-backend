from django.db import models

from core.models import TimeStampedModel


class Banner(TimeStampedModel):
    class LinkType(models.TextChoices):
        COURSE = "course", "Course"
        LEVEL = "level", "Level"
        URL = "url", "External URL"
        NONE = "none", "No Link"

    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    image_url = models.URLField(max_length=500)
    link_type = models.CharField(
        max_length=10,
        choices=LinkType.choices,
        default=LinkType.NONE,
    )
    link_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ID of the linked course/level (if link_type is course or level)",
    )
    link_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="External URL (if link_type is url)",
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "banners"
        ordering = ["order"]

    def __str__(self):
        return self.title
