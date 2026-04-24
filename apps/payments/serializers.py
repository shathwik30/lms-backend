from rest_framework import serializers

from core.serializer_fields import UUIDOrLegacyIntegerField

from .models import PaymentTransaction, Purchase


class PurchaseSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    student_email = serializers.EmailField(source="student.user.email", read_only=True)
    student_profile_picture = serializers.ImageField(source="student.user.profile_picture", read_only=True)
    is_valid = serializers.BooleanField(read_only=True)  # type: ignore[assignment]
    transaction_id = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    payment_gateway = serializers.SerializerMethodField()

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
            "transaction_id",
            "payment_status",
            "payment_method",
            "payment_gateway",
        ]
        read_only_fields = fields

    def _get_latest_transaction(self, obj: Purchase):
        if not hasattr(obj, "_cached_latest_txn"):
            txns = list(obj.transactions.all())
            txns.sort(key=lambda t: t.created_at, reverse=True)
            successful = next((t for t in txns if t.status == PaymentTransaction.Status.SUCCESS), None)
            obj._cached_latest_txn = successful or (txns[0] if txns else None)
        return obj._cached_latest_txn

    def get_transaction_id(self, obj: Purchase) -> str | None:
        txn = self._get_latest_transaction(obj)
        if not txn:
            return None
        return txn.razorpay_payment_id or txn.razorpay_order_id

    def get_payment_status(self, obj: Purchase) -> str | None:
        txn = self._get_latest_transaction(obj)
        return txn.status if txn else None

    def get_payment_method(self, obj: Purchase) -> str | None:
        txn = self._get_latest_transaction(obj)
        return "razorpay" if txn else None

    def get_payment_gateway(self, obj: Purchase) -> str:
        return "razorpay"


class InitiatePaymentSerializer(serializers.Serializer):
    level_id = UUIDOrLegacyIntegerField()


class InitiatePaymentResponseSerializer(serializers.Serializer):
    transaction_id = UUIDOrLegacyIntegerField()
    razorpay_order_id = serializers.CharField(allow_null=True)
    amount = serializers.CharField()
    currency = serializers.CharField()
    level_id = UUIDOrLegacyIntegerField()
    level_name = serializers.CharField()
    razorpay_key = serializers.CharField(allow_null=True)
    is_free = serializers.BooleanField()
    purchase_id = UUIDOrLegacyIntegerField(allow_null=True, required=False)
    expires_at = serializers.DateTimeField(allow_null=True, required=False)


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
