from django.db import models

from core.models import TimeStampedModel


class Level(TimeStampedModel):
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    passing_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=60.00)

    class Meta:
        db_table = "levels"
        ordering = ["order"]

    def __str__(self):
        return f"Level {self.order}: {self.name}"


class Week(TimeStampedModel):
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name="weeks")
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "weeks"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["level", "order"], name="unique_week_per_level"),
        ]

    def __str__(self):
        return f"{self.level.name} → {self.name}"
