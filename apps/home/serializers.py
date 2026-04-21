from rest_framework import serializers

from apps.exams.models import Exam

from .models import Banner


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = [
            "id",
            "title",
            "subtitle",
            "image_url",
            "link_type",
            "link_id",
            "link_url",
            "order",
            "is_active",
        ]


class BannerReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = [
            "id",
            "title",
            "subtitle",
            "image_url",
            "link_type",
            "link_id",
            "link_url",
        ]
        read_only_fields = fields


class HomeLevelExamSerializer(serializers.ModelSerializer):
    week_name = serializers.CharField(source="week.name", default=None, read_only=True)
    course_title = serializers.CharField(source="course.title", default=None, read_only=True)
    is_eligible = serializers.SerializerMethodField()
    is_passed = serializers.SerializerMethodField()
    best_score = serializers.SerializerMethodField()
    last_attempt_status = serializers.SerializerMethodField()
    attempts_count = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            "id",
            "title",
            "exam_type",
            "duration_minutes",
            "total_marks",
            "passing_percentage",
            "num_questions",
            "is_proctored",
            "week",
            "week_name",
            "course",
            "course_title",
            "is_eligible",
            "is_passed",
            "best_score",
            "last_attempt_status",
            "attempts_count",
        ]
        read_only_fields = fields

    def _attempt_stats(self, obj: Exam) -> dict | None:
        stats_map = self.context.get("attempt_stats") or {}
        return stats_map.get(obj.id)

    def get_is_eligible(self, obj: Exam) -> bool | None:
        return self.context.get("eligibility_map", {}).get(obj.id)

    def get_is_passed(self, obj: Exam) -> bool | None:
        stats = self._attempt_stats(obj)
        return stats["is_passed"] if stats else None

    def get_best_score(self, obj: Exam):
        stats = self._attempt_stats(obj)
        return stats["best_score"] if stats else None

    def get_last_attempt_status(self, obj: Exam) -> str | None:
        stats = self._attempt_stats(obj)
        return stats["last_status"] if stats else None

    def get_attempts_count(self, obj: Exam) -> int:
        stats = self._attempt_stats(obj)
        return stats["count"] if stats else 0
