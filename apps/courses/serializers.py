from rest_framework import serializers

from .models import Bookmark, Course, Resource, Session


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ["id", "title", "file_url", "resource_type", "session", "week"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        session = attrs.get("session", getattr(self.instance, "session", None) if self.instance else None)
        week = attrs.get("week", getattr(self.instance, "week", None) if self.instance else None)
        if not session and not week:
            raise serializers.ValidationError("A resource must be linked to a session or a week.")
        return attrs


class SessionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = [
            "id",
            "week",
            "title",
            "description",
            "duration_seconds",
            "order",
            "session_type",
            "is_active",
        ]
        read_only_fields = ["id"]


class SessionDetailSerializer(serializers.ModelSerializer):
    resources = ResourceSerializer(many=True, read_only=True)

    class Meta:
        model = Session
        fields = [
            "id",
            "week",
            "title",
            "description",
            "video_url",
            "duration_seconds",
            "order",
            "session_type",
            "exam",
            "is_active",
            "resources",
        ]
        read_only_fields = ["id"]


class BookmarkSerializer(serializers.ModelSerializer):
    session_title = serializers.CharField(source="session.title", read_only=True)
    session_week = serializers.IntegerField(source="session.week_id", read_only=True)

    class Meta:
        model = Bookmark
        fields = ["id", "session", "session_title", "session_week", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_session(self, value):
        request = self.context.get("request")
        if (
            request
            and hasattr(request.user, "student_profile")
            and Bookmark.objects.filter(
                student=request.user.student_profile,
                session=value,
            ).exists()
        ):
            raise serializers.ValidationError("You have already bookmarked this session.")
        return value


class CourseSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    weeks_count = serializers.IntegerField(source="weeks.count", read_only=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "level",
            "level_name",
            "title",
            "description",
            "is_active",
            "weeks_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
