from rest_framework import serializers

from core.serializer_fields import UUIDOrLegacyIntegerField

from .models import PaymentTransaction, Purchase


class PurchaseSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    student_email = serializers.EmailField(source="student.user.email", read_only=True)
    student_profile_picture = serializers.ImageField(source="student.user.profile_picture", read_only=True)
    is_valid = serializers.BooleanField(read_only=True)  # type: ignore[assignment]

    class Meta:
        model = Purchase
        fields = [
            "id",
            "level",
            "level_name",
            "student",
            "student_name",
            "student_email",
            "student_profile_picture",
            "amount_paid",
            "purchased_at",
            "expires_at",
            "status",
            "is_valid",
            "extended_by_days",
        ]
        read_only_fields = fields


class InitiatePaymentSerializer(serializers.Serializer):
    level_id = UUIDOrLegacyIntegerField()


class VerifyPaymentSerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()


class PaymentTransactionSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True, default=None)
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    student_email = serializers.EmailField(source="student.user.email", read_only=True)
    student_profile_picture = serializers.ImageField(source="student.user.profile_picture", read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "purchase",
            "student",
            "student_name",
            "student_email",
            "student_profile_picture",
            "level",
            "level_name",
            "razorpay_order_id",
            "razorpay_payment_id",
            "amount",
            "status",
            "created_at",
        ]
        read_only_fields = fields


class AdminExtendValiditySerializer(serializers.Serializer):
    purchase_id = UUIDOrLegacyIntegerField()
    extra_days = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(required=False, allow_blank=True)


class LevelPurchasePreviewSerializer(serializers.Serializer):
    level_id = serializers.UUIDField()
    level_name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    validity_days = serializers.IntegerField()
    access = serializers.CharField()
    whats_included = serializers.ListField(child=serializers.CharField())
    syllabus = serializers.ListField(child=serializers.DictField())
