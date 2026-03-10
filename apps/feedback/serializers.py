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
            "rating",
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
