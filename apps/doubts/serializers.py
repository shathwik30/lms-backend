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
    level_name = serializers.SerializerMethodField()
    course_name = serializers.SerializerMethodField()

    class Meta:
        model = DoubtTicket
        fields = [
            "id",
            "student",
            "student_name",
            "title",
            "status",
            "context_type",
            "level_name",
            "course_name",
            "created_at",
            "replies_count",
        ]
        read_only_fields = fields

    def get_level_name(self, obj: DoubtTicket) -> str | None:
        if obj.session_id:
            try:
                return obj.session.week.course.level.name  # type: ignore[union-attr]
            except AttributeError:
                return None
        if obj.exam_question_id:
            try:
                return obj.exam_question.exam.level.name  # type: ignore[union-attr]
            except AttributeError:
                return None
        return None

    def get_course_name(self, obj: DoubtTicket) -> str | None:
        if obj.session_id:
            try:
                return obj.session.week.course.title  # type: ignore[union-attr]
            except AttributeError:
                return None
        if obj.exam_question_id:
            try:
                exam = obj.exam_question.exam  # type: ignore[union-attr]
                return exam.course.title if exam.course else None
            except AttributeError:
                return None
        return None


class DoubtTicketDetailSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    student_profile_picture = serializers.ImageField(source="student.user.profile_picture", read_only=True)
    replies = DoubtReplySerializer(many=True, read_only=True)
    assigned_to_name = serializers.CharField(
        source="assigned_to.full_name",
        default=None,
        read_only=True,
    )
    level_name = serializers.SerializerMethodField()

    class Meta:
        model = DoubtTicket
        fields = [
            "id",
            "student",
            "student_name",
            "student_profile_picture",
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
            "level_name",
            "created_at",
            "updated_at",
            "replies",
        ]
        read_only_fields = [
            "id",
            "student",
            "student_name",
            "student_profile_picture",
            "status",
            "assigned_to",
            "assigned_to_name",
            "bonus_marks",
            "level_name",
            "created_at",
            "updated_at",
            "replies",
        ]

    def get_level_name(self, obj: DoubtTicket) -> str | None:
        if obj.session_id:
            try:
                return obj.session.week.course.level.name  # type: ignore[union-attr]
            except AttributeError:
                return None
        if obj.exam_question_id:
            try:
                return obj.exam_question.exam.level.name  # type: ignore[union-attr]
            except AttributeError:
                return None
        return None


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
    assigned_to = serializers.UUIDField()


class AdminBonusMarksSerializer(serializers.Serializer):
    bonus_marks = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100)


class UpdateDoubtStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=DoubtTicket.Status.choices)
