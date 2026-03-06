from rest_framework import serializers

from .models import Level, Week


class WeekSerializer(serializers.ModelSerializer):
    class Meta:
        model = Week
        fields = ["id", "level", "name", "order", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class LevelListSerializer(serializers.ModelSerializer):
    weeks_count = serializers.IntegerField(source="weeks.count", read_only=True)

    class Meta:
        model = Level
        fields = [
            "id",
            "name",
            "order",
            "description",
            "is_active",
            "passing_percentage",
            "weeks_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class LevelDetailSerializer(serializers.ModelSerializer):
    weeks = WeekSerializer(many=True, read_only=True)

    class Meta:
        model = Level
        fields = [
            "id",
            "name",
            "order",
            "description",
            "is_active",
            "passing_percentage",
            "weeks",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
