from rest_framework import serializers

from .models import LevelProgress, SessionProgress


class SessionProgressSerializer(serializers.ModelSerializer):
    session_title = serializers.CharField(source="session.title", read_only=True)
    total_duration = serializers.IntegerField(source="session.duration_seconds", read_only=True)

    class Meta:
        model = SessionProgress
        fields = [
            "id",
            "session",
            "session_title",
            "total_duration",
            "watched_seconds",
            "is_completed",
            "completed_at",
        ]
        read_only_fields = ["id", "is_completed", "completed_at"]


class UpdateProgressSerializer(serializers.Serializer):
    watched_seconds = serializers.IntegerField(min_value=0)


class LevelProgressSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    level_order = serializers.IntegerField(source="level.order", read_only=True)

    class Meta:
        model = LevelProgress
        fields = [
            "id",
            "level",
            "level_name",
            "level_order",
            "status",
            "started_at",
            "completed_at",
        ]
        read_only_fields = fields


class DashboardSerializer(serializers.Serializer):
    current_level = serializers.DictField(read_only=True)
    level_progress = LevelProgressSerializer(many=True, read_only=True)
    next_action = serializers.CharField(read_only=True)


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    student_id = serializers.IntegerField()
    full_name = serializers.CharField()
    profile_picture = serializers.CharField(allow_blank=True)
    levels_cleared = serializers.IntegerField()
    total_score = serializers.FloatField()
    exams_passed = serializers.IntegerField()
