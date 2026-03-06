from rest_framework import serializers

from .models import PaymentTransaction, Purchase


class PurchaseSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    level_name = serializers.CharField(source="course.level.name", read_only=True)
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Purchase
        fields = [
            "id",
            "course",
            "course_title",
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
    course_id = serializers.IntegerField()


class VerifyPaymentSerializer(serializers.Serializer):
    gateway_order_id = serializers.CharField()
    gateway_payment_id = serializers.CharField()
    gateway_signature = serializers.CharField()


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "gateway_order_id",
            "gateway_payment_id",
            "amount",
            "status",
            "created_at",
        ]
        read_only_fields = fields


class AdminExtendValiditySerializer(serializers.Serializer):
    purchase_id = serializers.IntegerField()
    extra_days = serializers.IntegerField(min_value=1)
