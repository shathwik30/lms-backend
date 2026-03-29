from rest_framework import serializers

from .models import SessionFeedback


class SessionFeedbackSerializer(serializers.ModelSerializer):
    session_title = serializers.CharField(source="session.title", read_only=True)

    class Meta:
        model = SessionFeedback
        fields = [
            "id",
            "session",
            "session_title",
            "overall_rating",
            "difficulty_rating",
            "clarity_rating",
            "comment",
            "created_at",
        ]
        read_only_fields = ["id", "session", "session_title", "created_at"]
        extra_kwargs = {
            "difficulty_rating": {"required": False},
            "clarity_rating": {"required": False},
        }


class AdminFeedbackSerializer(serializers.ModelSerializer):
    session_title = serializers.CharField(source="session.title", read_only=True)
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    level_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()

    class Meta:
        model = SessionFeedback
        fields = [
            "id",
            "student",
            "student_name",
            "session",
            "session_title",
            "level_name",
            "subject_name",
            "overall_rating",
            "difficulty_rating",
            "clarity_rating",
            "comment",
            "created_at",
        ]
        read_only_fields = fields

    def get_level_name(self, obj) -> str | None:
        try:
            return obj.session.week.course.level.name
        except AttributeError:
            return None

    def get_subject_name(self, obj) -> str | None:
        try:
            return obj.session.week.course.title
        except AttributeError:
            return None
