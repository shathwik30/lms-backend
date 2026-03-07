from rest_framework import serializers

from .models import DoubtReply, DoubtTicket


class DoubtReplySerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.full_name", read_only=True)
    author_role = serializers.SerializerMethodField()

    class Meta:
        model = DoubtReply
        fields = [
            "id",
            "ticket",
            "author",
            "author_name",
            "author_role",
            "message",
            "attachment",
            "created_at",
        ]
        read_only_fields = ["id", "ticket", "author", "author_name", "author_role", "created_at"]

    def get_author_role(self, obj) -> str:
        if obj.author.is_admin:
            return "admin"
        return "student"


class DoubtTicketListSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    replies_count = serializers.IntegerField(source="replies.count", read_only=True)

    class Meta:
        model = DoubtTicket
        fields = [
            "id",
            "student",
            "student_name",
            "title",
            "status",
            "context_type",
            "created_at",
            "replies_count",
        ]
        read_only_fields = fields


class DoubtTicketDetailSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    replies = DoubtReplySerializer(many=True, read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.full_name",
        default=None,
        read_only=True,
    )

    class Meta:
        model = DoubtTicket
        fields = [
            "id",
            "student",
            "student_name",
            "title",
            "description",
            "screenshot",
            "status",
            "context_type",
            "session",
            "exam_question",
            "assigned_to",
            "assigned_to_name",
            "bonus_marks",
            "created_at",
            "updated_at",
            "replies",
        ]
        read_only_fields = [
            "id",
            "student",
            "student_name",
            "status",
            "assigned_to",
            "assigned_to_name",
            "bonus_marks",
            "created_at",
            "updated_at",
            "replies",
        ]


class CreateDoubtSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoubtTicket
        fields = [
            "id",
            "title",
            "description",
            "screenshot",
            "context_type",
            "session",
            "exam_question",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]


class AdminAssignDoubtSerializer(serializers.Serializer):
    assigned_to = serializers.IntegerField()


class AdminBonusMarksSerializer(serializers.Serializer):
    bonus_marks = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)


class UpdateDoubtStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=DoubtTicket.Status.choices)
