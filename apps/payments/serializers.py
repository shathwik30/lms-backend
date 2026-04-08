from rest_framework import serializers

from .models import PaymentTransaction, Purchase


class PurchaseSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    is_valid = serializers.BooleanField(read_only=True)  # type: ignore[assignment]

    class Meta:
        model = Purchase
        fields = [
            "id",
            "level",
            "level_name",
            "amount_paid",
            "purchased_at",
            "expires_at",
            "status",
            "is_valid",
            "extended_by_days",
        ]
        read_only_fields = fields


class InitiatePaymentSerializer(serializers.Serializer):
    level_id = serializers.IntegerField()


class VerifyPaymentSerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "razorpay_order_id",
            "razorpay_payment_id",
            "amount",
            "status",
            "created_at",
        ]
        read_only_fields = fields


class AdminExtendValiditySerializer(serializers.Serializer):
    purchase_id = serializers.IntegerField()
    extra_days = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(required=False, allow_blank=True)
