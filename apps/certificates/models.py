import uuid

from django.db import IntegrityError, models, transaction

from core.constants import CertificateConstants
from core.models import TimeStampedModel


class Certificate(TimeStampedModel):
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    level = models.ForeignKey(
        "levels.Level",
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    certificate_number = models.CharField(max_length=50, unique=True, editable=False)
    issued_at = models.DateTimeField(auto_now_add=True)
    certificate_url = models.URLField(max_length=500, blank=True)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    total_marks = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "certificates"
        ordering = ["-issued_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "level"], name="unique_certificate_per_level"),
        ]

    def _generate_certificate_number(self):
        return f"{CertificateConstants.NUMBER_PREFIX}{uuid.uuid4().hex[:16].upper()}"

    def save(self, *args, **kwargs):
        if not self.certificate_number:
            for _ in range(5):
                self.certificate_number = self._generate_certificate_number()
                try:
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    continue
            self.certificate_number = f"{CertificateConstants.NUMBER_PREFIX}{uuid.uuid4().hex.upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.user.email} — {self.level.name} ({self.certificate_number})"
