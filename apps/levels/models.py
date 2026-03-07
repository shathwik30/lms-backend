from django.db import models

from core.models import TimeStampedModel


class Level(TimeStampedModel):
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    passing_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=60.00)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    validity_days = models.PositiveIntegerField(default=365)
    max_final_exam_attempts = models.PositiveIntegerField(default=3)

    class Meta:
        db_table = "levels"
        ordering = ["order"]

    def __str__(self):
        return f"Level {self.order}: {self.name}"


class Week(TimeStampedModel):
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="weeks",
    )
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "weeks"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["course", "order"], name="unique_week_per_course"),
        ]

    @property
    def level(self):
        return self.course.level

    def __str__(self):
        return f"{self.course.title} → {self.name}"
