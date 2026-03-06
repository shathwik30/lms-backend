from django.db import models

from core.models import TimeStampedModel


class DailyRevenue(TimeStampedModel):
    date = models.DateField(unique=True)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_transactions = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "daily_revenue"
        ordering = ["-date"]

    def __str__(self):
        return f"Revenue: {self.date}"


class LevelAnalytics(TimeStampedModel):
    level = models.ForeignKey(
        "levels.Level",
        on_delete=models.CASCADE,
        related_name="analytics",
    )
    date = models.DateField(db_index=True)
    total_attempts = models.PositiveIntegerField(default=0)
    total_passes = models.PositiveIntegerField(default=0)
    total_failures = models.PositiveIntegerField(default=0)
    total_purchases = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "level_analytics"
        unique_together = ("level", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.level.name} analytics: {self.date}"
