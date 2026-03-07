from rest_framework import serializers

from apps.courses.models import Course

from .models import Level, Week


class WeekSerializer(serializers.ModelSerializer):
    class Meta:
        model = Week
        fields = ["id", "course", "name", "order", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class CourseInLevelSerializer(serializers.ModelSerializer):
    weeks_count = serializers.IntegerField(source="weeks.count", read_only=True)

    class Meta:
        model = Course
        fields = ["id", "title", "description", "is_active", "weeks_count"]
        read_only_fields = fields


class LevelListSerializer(serializers.ModelSerializer):
    courses_count = serializers.IntegerField(source="courses.count", read_only=True)

    class Meta:
        model = Level
        fields = [
            "id",
            "name",
            "order",
            "description",
            "is_active",
            "passing_percentage",
            "price",
            "validity_days",
            "max_final_exam_attempts",
            "courses_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class LevelDetailSerializer(serializers.ModelSerializer):
    courses = CourseInLevelSerializer(many=True, read_only=True)

    class Meta:
        model = Level
        fields = [
            "id",
            "name",
            "order",
            "description",
            "is_active",
            "passing_percentage",
            "price",
            "validity_days",
            "max_final_exam_attempts",
            "courses",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
