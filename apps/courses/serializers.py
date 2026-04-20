from rest_framework import serializers

from .models import Bookmark, Course, Session


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
    class Meta:
        model = Session
        fields = [
            "id",
            "week",
            "title",
            "description",
            "video_url",
            "file_url",
            "resource_type",
            "markdown_content",
            "thumbnail_url",
            "duration_seconds",
            "order",
            "session_type",
            "exam",
            "is_active",
        ]
        read_only_fields = ["id"]


class BookmarkSerializer(serializers.ModelSerializer):
    session_title = serializers.CharField(source="session.title", read_only=True)
    session_week = serializers.UUIDField(source="session.week_id", read_only=True)

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


class AdminCourseSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    weeks_count = serializers.IntegerField(source="weeks.count", read_only=True)
    price = serializers.DecimalField(source="level.price", max_digits=10, decimal_places=2, read_only=True)
    students_enrolled = serializers.SerializerMethodField()
    exam_linked = serializers.SerializerMethodField()

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
            "price",
            "students_enrolled",
            "exam_linked",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_students_enrolled(self, obj: Course) -> int:
        from apps.progress.models import CourseProgress

        return CourseProgress.objects.filter(
            course=obj,
            status__in=[CourseProgress.Status.IN_PROGRESS, CourseProgress.Status.COMPLETED],
        ).count()

    def get_exam_linked(self, obj: Course) -> list[str]:
        from apps.exams.models import Exam

        return list(Exam.objects.filter(course=obj, is_active=True).values_list("title", flat=True))
