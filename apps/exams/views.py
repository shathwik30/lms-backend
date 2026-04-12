from django.db.models import Avg, Count, OuterRef, Subquery
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics, status
from rest_framework import serializers as drf_serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import ErrorMessage
from core.decorators import swagger_safe
from core.pagination import LargePagination, SmallPagination
from core.permissions import IsAdmin, IsStudent
from core.throttling import SafeScopedRateThrottle

from .models import Exam, ExamAttempt, Option, ProctoringViolation, Question
from .serializers import (
    AdminExamAttemptSerializer,
    AdminExamSerializer,
    AttemptQuestionResultSerializer,
    BulkQuestionCreateSerializer,
    ExamAttemptDetailSerializer,
    ExamAttemptSerializer,
    ExamSerializer,
    OptionAdminSerializer,
    ProctoringViolationSerializer,
    QuestionAdminSerializer,
    ReportViolationSerializer,
    SubmitExamSerializer,
)
from .services import ExamService

# ── Student views ──


class ExamDetailView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(responses={200: ExamSerializer}, tags=["Exams"])
    def get(self, request, pk):
        profile = request.user.student_profile
        exam, eligible = ExamService.get_exam_with_eligibility(profile, pk)
        if not exam:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        data = ExamSerializer(exam).data
        data["is_eligible"] = eligible
        return Response(data)


class ExamStartView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(request=None, responses={201: ExamAttemptDetailSerializer}, tags=["Exams"])
    def post(self, request, pk):
        try:
            exam = Exam.objects.select_related("level", "week", "course").get(pk=pk, is_active=True)
        except Exam.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        attempt, created = ExamService.start_exam(request.user.student_profile, exam)
        if attempt is None:
            return Response(
                {"detail": ErrorMessage.NO_QUESTIONS_AVAILABLE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if created is False:
            return Response(ExamAttemptDetailSerializer(attempt).data, status=status.HTTP_200_OK)

        return Response(ExamAttemptDetailSerializer(attempt).data, status=status.HTTP_201_CREATED)


class ExamSubmitView(APIView):
    permission_classes = [IsStudent]
    throttle_classes = [SafeScopedRateThrottle]
    throttle_scope = "exam_submit"

    @extend_schema(request=SubmitExamSerializer, responses={200: ExamAttemptSerializer}, tags=["Exams"])
    def post(self, request, pk):
        try:
            attempt = ExamAttempt.objects.select_related("exam__level").get(
                pk=pk,
                student=request.user.student_profile,
            )
        except ExamAttempt.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        serializer = SubmitExamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result, error = ExamService.submit_exam(
            request.user,
            attempt,
            serializer.validated_data["answers"],
        )
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ExamAttemptSerializer(result).data)


class AttemptResultView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(responses={200: ExamAttemptDetailSerializer}, tags=["Exams"])
    def get(self, request, pk):
        try:
            attempt = ExamAttempt.objects.get(
                pk=pk,
                student=request.user.student_profile,
            )
        except ExamAttempt.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        if attempt.status == ExamAttempt.Status.IN_PROGRESS:
            return Response(
                {"detail": ErrorMessage.EXAM_NOT_SUBMITTED},
                status=status.HTTP_400_BAD_REQUEST,
            )

        questions = attempt.attempt_questions.select_related(
            "question",
            "question__level",
            "selected_option",
        ).prefetch_related(
            "question__options",
            "selected_options",
        )
        data = ExamAttemptSerializer(attempt).data
        data["questions"] = AttemptQuestionResultSerializer(questions, many=True).data
        return Response(data)


@extend_schema_view(
    list=extend_schema(tags=["Exams"], summary="List my exam attempts"),
)
class StudentAttemptListView(generics.ListAPIView):
    permission_classes = [IsStudent]
    serializer_class = ExamAttemptSerializer
    pagination_class = SmallPagination
    filterset_fields = ["exam", "status", "is_passed"]

    @swagger_safe(ExamAttempt)
    def get_queryset(self):
        return ExamAttempt.objects.filter(
            student=self.request.user.student_profile,  # type: ignore[union-attr]
        ).select_related("exam")


# ── Proctoring views ──


class ReportViolationView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(request=ReportViolationSerializer, responses={201: ProctoringViolationSerializer}, tags=["Exams"])
    def post(self, request, pk):
        try:
            attempt = ExamAttempt.objects.select_related("exam").get(
                pk=pk,
                student=request.user.student_profile,
                status=ExamAttempt.Status.IN_PROGRESS,
            )
        except ExamAttempt.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReportViolationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result, error = ExamService.report_violation(
            attempt,
            serializer.validated_data["violation_type"],
            serializer.validated_data.get("details", ""),
        )
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        assert result is not None
        data = ProctoringViolationSerializer(result["violation"]).data
        data["total_warnings"] = result["total_warnings"]
        data["max_warnings"] = result["max_warnings"]
        data["is_disqualified"] = result["is_disqualified"]
        return Response(data, status=status.HTTP_201_CREATED)


class AttemptViolationsView(APIView):
    permission_classes = [IsStudent]

    @extend_schema(responses={200: ProctoringViolationSerializer(many=True)}, tags=["Exams"])
    def get(self, request, pk):
        try:
            attempt = ExamAttempt.objects.select_related("exam").get(
                pk=pk,
                student=request.user.student_profile,
            )
        except ExamAttempt.DoesNotExist:
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        violations = attempt.violations.all()
        return Response(
            {
                "violations": ProctoringViolationSerializer(violations, many=True).data,
                "total_warnings": violations.count(),
                "max_warnings": attempt.exam.max_warnings,
                "is_disqualified": attempt.is_disqualified,
            }
        )


# ── Admin views ──


@extend_schema_view(
    list=extend_schema(tags=["Exams"], summary="List questions (admin)"),
    create=extend_schema(tags=["Exams"], summary="Create a question"),
)
class AdminQuestionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = QuestionAdminSerializer
    queryset = Question.objects.select_related("exam", "level").prefetch_related("options")
    pagination_class = LargePagination
    filterset_fields = ["exam", "level", "difficulty", "question_type", "is_active"]


@extend_schema_view(
    retrieve=extend_schema(tags=["Exams"], summary="Get question details (admin)"),
    update=extend_schema(tags=["Exams"], summary="Update a question"),
    partial_update=extend_schema(tags=["Exams"], summary="Partially update a question"),
    destroy=extend_schema(tags=["Exams"], summary="Delete a question"),
)
class AdminQuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    serializer_class = QuestionAdminSerializer
    queryset = Question.objects.all()


@extend_schema_view(
    list=extend_schema(tags=["Exams"], summary="List options for a question (admin)"),
    create=extend_schema(tags=["Exams"], summary="Create an option"),
)
class AdminOptionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = OptionAdminSerializer
    pagination_class = None

    @swagger_safe(Option)
    def get_queryset(self):
        return Option.objects.filter(question_id=self.kwargs["question_pk"])

    def perform_create(self, serializer):
        serializer.save(question_id=self.kwargs["question_pk"])


class AdminBulkQuestionCreateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        request=BulkQuestionCreateSerializer,
        responses={201: QuestionAdminSerializer(many=True)},
        tags=["Exams"],
        summary="Bulk create questions with options",
    )
    def post(self, request):
        serializer = BulkQuestionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        questions = serializer.save()
        return Response(
            QuestionAdminSerializer(questions, many=True).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    list=extend_schema(tags=["Exams"], summary="List exams (admin)"),
    create=extend_schema(tags=["Exams"], summary="Create an exam"),
)
class AdminExamListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdmin]
    queryset = Exam.objects.select_related("level", "week", "course")
    pagination_class = LargePagination
    filterset_fields = ["level", "exam_type", "is_active"]

    def get_serializer_class(self) -> type[ExamSerializer] | type[AdminExamSerializer]:
        if self.request.method == "POST":
            return ExamSerializer
        return AdminExamSerializer


@extend_schema_view(
    retrieve=extend_schema(tags=["Exams"], summary="Get exam details (admin)"),
    update=extend_schema(tags=["Exams"], summary="Update an exam"),
    partial_update=extend_schema(tags=["Exams"], summary="Partially update an exam"),
    destroy=extend_schema(tags=["Exams"], summary="Delete an exam"),
)
class AdminExamDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    queryset = Exam.objects.select_related("level", "week", "course")

    def get_serializer_class(self) -> type[ExamSerializer] | type[AdminExamSerializer]:
        if self.request.method == "GET":
            return AdminExamSerializer
        return ExamSerializer


@extend_schema_view(
    list=extend_schema(tags=["Exams"], summary="List all attempts (admin)"),
)
class AdminAttemptListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = AdminExamAttemptSerializer
    pagination_class = LargePagination
    filterset_fields = ["exam", "status", "is_passed", "is_disqualified", "exam__level"]

    @swagger_safe(ExamAttempt)
    def get_queryset(self):
        return (
            ExamAttempt.objects.select_related("exam", "student__user")
            .annotate(
                violations_count=Count("violations"),
                attempt_number=Subquery(
                    ExamAttempt.objects.filter(
                        student=OuterRef("student"),
                        exam=OuterRef("exam"),
                        started_at__lte=OuterRef("started_at"),
                    )
                    .order_by()
                    .values("student", "exam")
                    .annotate(n=Count("id"))
                    .values("n")[:1]
                ),
            )
            .order_by("-started_at")
        )


class AdminExamStatsView(APIView):
    """Aggregated stats for a single exam (admin)."""

    permission_classes = [IsAdmin]

    @extend_schema(
        tags=["Exams"],
        summary="Exam-level analytics",
        responses={
            200: inline_serializer(
                "AdminExamStatsResponse",
                fields={
                    "total_attempts": drf_serializers.IntegerField(),
                    "pass_rate": drf_serializers.FloatField(allow_null=True),
                    "average_score": drf_serializers.FloatField(allow_null=True),
                    "total_violations": drf_serializers.IntegerField(),
                },
            )
        },
    )
    def get(self, request, exam_pk):
        if not Exam.objects.filter(pk=exam_pk).exists():
            return Response({"detail": ErrorMessage.NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)

        attempts = ExamAttempt.objects.filter(exam_id=exam_pk).exclude(
            status=ExamAttempt.Status.IN_PROGRESS,
        )
        total_attempts = attempts.count()
        passed = attempts.filter(is_passed=True).count()
        pass_rate = round((passed / total_attempts) * 100, 2) if total_attempts else None

        avg_score = attempts.aggregate(avg=Avg("score"))["avg"]
        average_score = round(float(avg_score), 2) if avg_score is not None else None

        total_violations = ProctoringViolation.objects.filter(attempt__exam_id=exam_pk).count()

        return Response(
            {
                "total_attempts": total_attempts,
                "pass_rate": pass_rate,
                "average_score": average_score,
                "total_violations": total_violations,
            }
        )


@extend_schema_view(
    retrieve=extend_schema(tags=["Exams"], summary="Get option details (admin)"),
    update=extend_schema(tags=["Exams"], summary="Update an option"),
    partial_update=extend_schema(tags=["Exams"], summary="Partially update an option"),
    destroy=extend_schema(tags=["Exams"], summary="Delete an option"),
)
class AdminOptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    serializer_class = OptionAdminSerializer
    queryset = Option.objects.all()
