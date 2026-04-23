from decimal import Decimal

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
            "exam",
            "level",
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
        extra_kwargs = {"level": {"required": False}}

    def create(self, validated_data):
        if "level" not in validated_data or validated_data["level"] is None:
            validated_data["level"] = validated_data["exam"].level
        return super().create(validated_data)


class BulkOptionSerializer(serializers.Serializer):
    text = serializers.CharField()
    image_url = serializers.URLField(required=False, default="", allow_blank=True)
    is_correct = serializers.BooleanField(default=False)


class BulkQuestionSerializer(serializers.Serializer):
    text = serializers.CharField()
    image_url = serializers.URLField(required=False, default="", allow_blank=True)
    difficulty = serializers.ChoiceField(choices=Question.Difficulty.choices)
    question_type = serializers.ChoiceField(
        choices=Question.QuestionType.choices,
        default=Question.QuestionType.MCQ,
    )
    marks = serializers.IntegerField(default=4, min_value=1)
    negative_marks = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal(0))
    explanation = serializers.CharField(required=False, default="", allow_blank=True)
    correct_text_answer = serializers.CharField(required=False, default="", allow_blank=True)
    is_active = serializers.BooleanField(default=True)
    options = BulkOptionSerializer(many=True, required=False, default=list)


class BulkQuestionCreateSerializer(serializers.Serializer):
    exam = serializers.PrimaryKeyRelatedField(queryset=Exam.objects.all())
    questions = BulkQuestionSerializer(many=True)

    def validate_questions(self, questions: list[dict]) -> list[dict]:
        if len(questions) == 0:
            raise serializers.ValidationError("At least one question is required.")
        for i, q in enumerate(questions):
            qtype = q.get("question_type", Question.QuestionType.MCQ)
            options = q.get("options", [])
            if qtype in (Question.QuestionType.MCQ, Question.QuestionType.MULTI_MCQ):
                if len(options) < 2:
                    raise serializers.ValidationError(
                        {str(i): f"MCQ question must have at least 2 options, got {len(options)}."}
                    )
                correct_count = sum(1 for o in options if o.get("is_correct"))
                if correct_count == 0:
                    raise serializers.ValidationError({str(i): "At least one option must be marked as correct."})
        return questions

    def create(self, validated_data):
        from django.db import transaction

        exam = validated_data["exam"]
        questions_data = validated_data["questions"]

        created_questions = []
        with transaction.atomic():
            for q_data in questions_data:
                options_data = q_data.pop("options", [])
                question = Question.objects.create(
                    exam=exam,
                    level=exam.level,
                    **q_data,
                )
                if options_data:
                    Option.objects.bulk_create([Option(question=question, **opt) for opt in options_data])
                created_questions.append(question)

        return created_questions


class ExamSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source="level.name", read_only=True)
    week_name = serializers.CharField(source="week.name", default=None, read_only=True)
    course_title = serializers.CharField(source="course.title", default=None, read_only=True)
    pool_size = serializers.SerializerMethodField()

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
            "pool_size",
            "is_proctored",
            "require_fullscreen",
            "detect_tab_switch",
            "max_warnings",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "pool_size"]

    _SINGLETON_EXAM_TYPES = (Exam.ExamType.LEVEL_FINAL, Exam.ExamType.ONBOARDING)

    def _deactivate_siblings(self, exam: Exam) -> None:
        if exam.exam_type in self._SINGLETON_EXAM_TYPES and exam.is_active:
            Exam.objects.filter(
                level=exam.level,
                exam_type=exam.exam_type,
                is_active=True,
            ).exclude(pk=exam.pk).update(is_active=False)

    def create(self, validated_data):
        exam = super().create(validated_data)
        self._deactivate_siblings(exam)
        return exam

    def update(self, instance, validated_data):
        exam = super().update(instance, validated_data)
        self._deactivate_siblings(exam)
        return exam

    def get_pool_size(self, obj: Exam) -> int:
        return obj.questions.filter(is_active=True).count()


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
    question_level = serializers.UUIDField(source="question.level_id", read_only=True)
    question_level_name = serializers.CharField(source="question.level.name", read_only=True)
    explanation = serializers.CharField(source="question.explanation", read_only=True)
    correct_text_answer = serializers.CharField(source="question.correct_text_answer", read_only=True)
    selected_option_detail = OptionSerializer(source="selected_option", read_only=True)
    selected_option_ids = serializers.PrimaryKeyRelatedField(  # type: ignore[var-annotated]
        source="selected_options",
        many=True,
        read_only=True,
    )
    selected_options_detail = OptionSerializer(source="selected_options", many=True, read_only=True)
    correct_option_ids = serializers.SerializerMethodField()
    correct_options = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()

    class Meta:
        model = AttemptQuestion
        fields = [
            "id",
            "question",
            "question_text",
            "question_type",
            "question_level",
            "question_level_name",
            "selected_option",
            "selected_option_detail",
            "selected_option_ids",
            "selected_options_detail",
            "text_answer",
            "is_correct",
            "marks_awarded",
            "order",
            "explanation",
            "correct_text_answer",
            "correct_option_ids",
            "correct_options",
            "options",
        ]
        read_only_fields = fields

    def get_correct_option_ids(self, obj):
        return list(obj.question.options.filter(is_correct=True).values_list("id", flat=True))

    def get_correct_options(self, obj):
        return OptionSerializer(obj.question.options.filter(is_correct=True), many=True).data

    def get_options(self, obj):
        selected_ids = set(obj.selected_options.values_list("id", flat=True))
        if obj.selected_option_id:
            selected_ids.add(obj.selected_option_id)

        return [
            {
                "id": option.id,
                "text": option.text,
                "image_url": option.image_url,
                "is_correct": option.is_correct,
                "is_selected": option.id in selected_ids,
            }
            for option in obj.question.options.all()
        ]


class AdminExamSerializer(ExamSerializer):
    subjects_included = serializers.SerializerMethodField()

    class Meta(ExamSerializer.Meta):
        fields = [*ExamSerializer.Meta.fields, "subjects_included"]

    def get_subjects_included(self, obj: Exam) -> list[str]:
        from apps.courses.models import Course

        return list(Course.objects.filter(level=obj.level, is_active=True).values_list("title", flat=True))


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


class AdminExamAttemptSerializer(serializers.ModelSerializer):
    """Admin-facing attempt serializer with student info and violation count."""

    exam_title = serializers.CharField(source="exam.title", read_only=True)
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    student_profile_picture = serializers.ImageField(source="student.user.profile_picture", read_only=True)
    violations_count = serializers.IntegerField(read_only=True)
    attempt_number = serializers.IntegerField(read_only=True)

    class Meta:
        model = ExamAttempt
        fields = [
            "id",
            "exam",
            "exam_title",
            "student",
            "student_name",
            "student_profile_picture",
            "started_at",
            "submitted_at",
            "status",
            "score",
            "total_marks",
            "is_passed",
            "is_disqualified",
            "violations_count",
            "attempt_number",
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
    question_id = serializers.UUIDField()
    option_id = serializers.UUIDField(allow_null=True, required=False)
    option_ids = serializers.ListField(
        child=serializers.UUIDField(),
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
