from rest_framework import serializers

from .models import DailyRevenue, LevelAnalytics


class DailyRevenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyRevenue
        fields = ["id", "date", "total_revenue", "total_transactions"]
        read_only_fields = fields


class LevelAnalyticsSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    pass_rate = serializers.SerializerMethodField()

    class Meta:
        model = LevelAnalytics
        fields = [
            "id",
            "level",
            "level_name",
            "date",
            "total_attempts",
            "total_passes",
            "total_failures",
            "total_purchases",
            "revenue",
            "pass_rate",
        ]
        read_only_fields = fields

    def get_pass_rate(self, obj) -> float | None:
        if obj.total_attempts == 0:
            return None
        return round((obj.total_passes / obj.total_attempts) * 100, 2)
