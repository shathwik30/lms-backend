from rest_framework import serializers

from .models import CourseProgress, LevelProgress, SessionProgress


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
            "is_exam_passed",
        ]
        read_only_fields = ["id", "is_completed", "completed_at", "is_exam_passed"]


class UpdateProgressSerializer(serializers.Serializer):
    watched_seconds = serializers.IntegerField(min_value=0)


class CourseProgressSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    level_name = serializers.CharField(source="course.level.name", read_only=True)

    class Meta:
        model = CourseProgress
        fields = [
            "id",
            "course",
            "course_title",
            "level_name",
            "status",
            "started_at",
            "completed_at",
        ]
        read_only_fields = fields


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
            "final_exam_attempts_used",
        ]
        read_only_fields = fields


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    student_id = serializers.IntegerField()
    full_name = serializers.CharField()
    profile_picture = serializers.CharField(allow_blank=True)
    levels_cleared = serializers.IntegerField()
    total_score = serializers.FloatField()
    exams_passed = serializers.IntegerField()
