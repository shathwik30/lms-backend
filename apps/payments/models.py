from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class Purchase(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="purchases",
    )
    level = models.ForeignKey(
        "levels.Level",
        on_delete=models.CASCADE,
        related_name="purchases",
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    purchased_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    extended_by_days = models.PositiveIntegerField(default=0)
    extended_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="extensions_granted",
    )

    class Meta:
        db_table = "purchases"
        ordering = ["-purchased_at"]
        indexes = [
            models.Index(fields=["student", "status", "expires_at"], name="idx_purchase_access"),
        ]

    def __str__(self):
        return f"{self.student} → {self.level.name}"

    @property
    def is_valid(self):
        return self.status == self.Status.ACTIVE and self.expires_at > timezone.now()


class PaymentTransaction(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    purchase = models.ForeignKey(
        Purchase,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    student = models.ForeignKey(
        "users.StudentProfile",
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    level = models.ForeignKey(
        "levels.Level",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    gateway_order_id = models.CharField(max_length=200, unique=True)
    gateway_payment_id = models.CharField(max_length=200, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    class Meta:
        db_table = "payment_transactions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Txn {self.gateway_order_id} ({self.status})"
