from rest_framework import serializers

from .models import AttemptQuestion, Exam, ExamAttempt, Option, ProctoringViolation, Question


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ["id", "text", "image_url"]


class OptionAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ["id", "question", "text", "image_url", "is_correct"]
        read_only_fields = ["id"]


class QuestionSerializer(serializers.ModelSerializer):
    """Student-facing — no correct answer exposed."""

    options = OptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ["id", "text", "image_url", "marks", "question_type", "options"]
        read_only_fields = fields


class QuestionAdminSerializer(serializers.ModelSerializer):
    options = OptionAdminSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "level",
            "week",
            "course",
            "text",
            "image_url",
            "difficulty",
            "question_type",
            "marks",
            "negative_marks",
            "explanation",
            "correct_text_answer",
            "is_active",
            "options",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ExamSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    week_name = serializers.CharField(source="week.name", default=None, read_only=True)
    course_title = serializers.CharField(source="course.title", default=None, read_only=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "level",
            "level_name",
            "week",
            "week_name",
            "course",
            "course_title",
            "exam_type",
            "title",
            "duration_minutes",
            "total_marks",
            "passing_percentage",
            "num_questions",
            "is_proctored",
            "max_warnings",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class AttemptQuestionSerializer(serializers.ModelSerializer):
    question = QuestionSerializer(read_only=True)
    selected_option_ids = serializers.PrimaryKeyRelatedField(  # type: ignore[var-annotated]
        source="selected_options",
        many=True,
        read_only=True,
    )

    class Meta:
        model = AttemptQuestion
        fields = ["id", "question", "selected_option", "selected_option_ids", "text_answer", "order"]
        read_only_fields = ["id", "question", "order"]


class AttemptQuestionResultSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.text", read_only=True)
    question_type = serializers.CharField(source="question.question_type", read_only=True)
    explanation = serializers.CharField(source="question.explanation", read_only=True)
    correct_text_answer = serializers.CharField(source="question.correct_text_answer", read_only=True)
    selected_option_ids = serializers.PrimaryKeyRelatedField(  # type: ignore[var-annotated]
        source="selected_options",
        many=True,
        read_only=True,
    )
    correct_option_ids = serializers.SerializerMethodField()

    class Meta:
        model = AttemptQuestion
        fields = [
            "id",
            "question",
            "question_text",
            "question_type",
            "selected_option",
            "selected_option_ids",
            "text_answer",
            "is_correct",
            "marks_awarded",
            "order",
            "explanation",
            "correct_text_answer",
            "correct_option_ids",
        ]
        read_only_fields = fields

    def get_correct_option_ids(self, obj):
        return list(obj.question.options.filter(is_correct=True).values_list("id", flat=True))


class ExamAttemptSerializer(serializers.ModelSerializer):
    exam_title = serializers.CharField(source="exam.title", read_only=True)

    class Meta:
        model = ExamAttempt
        fields = [
            "id",
            "exam",
            "exam_title",
            "started_at",
            "submitted_at",
            "status",
            "score",
            "total_marks",
            "is_passed",
            "is_disqualified",
        ]
        read_only_fields = fields


class ExamAttemptDetailSerializer(serializers.ModelSerializer):
    exam_title = serializers.CharField(source="exam.title", read_only=True)
    questions = AttemptQuestionSerializer(source="attempt_questions", many=True, read_only=True)

    class Meta:
        model = ExamAttempt
        fields = [
            "id",
            "exam",
            "exam_title",
            "started_at",
            "submitted_at",
            "status",
            "score",
            "total_marks",
            "is_passed",
            "is_disqualified",
            "questions",
        ]
        read_only_fields = fields


class SubmitAnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    option_id = serializers.IntegerField(allow_null=True, required=False)
    option_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        max_length=20,
        help_text="Selected option IDs for multi-select MCQ",
    )
    text_answer = serializers.CharField(
        required=False,
        default="",
        allow_blank=True,
        max_length=1000,
        help_text="Text answer for fill-in-the-blank questions",
    )


class SubmitExamSerializer(serializers.Serializer):
    answers = SubmitAnswerSerializer(many=True, max_length=200)  # type: ignore[call-arg]


class ProctoringViolationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProctoringViolation
        fields = ["id", "attempt", "violation_type", "warning_number", "details", "created_at"]
        read_only_fields = ["id", "warning_number", "created_at"]


class ReportViolationSerializer(serializers.Serializer):
    violation_type = serializers.ChoiceField(
        choices=ProctoringViolation.ViolationType.choices,
    )
    details = serializers.CharField(required=False, default="", allow_blank=True)
