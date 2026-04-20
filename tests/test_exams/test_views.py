from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.exams.models import AttemptQuestion, Exam, ExamAttempt
from apps.progress.models import LevelProgress
from core.test_utils import TestFactory


def _make_eligible(factory, profile, data):
    """Create purchase and complete all sessions so student can attempt the level final exam."""
    factory.create_purchase(profile, data["level"])
    for s in data["sessions"]:
        factory.complete_session(profile, s)


class ExamFlowTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data = self.factory.setup_full_level(order=1, num_questions=5)
        _make_eligible(self.factory, self.profile, self.data)

    def test_exam_detail_shows_eligibility(self):
        response = self.client.get(f"/api/v1/exams/{self.data['exam'].pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("is_eligible", response.data)

    def test_exam_detail_nonexistent_returns_404(self):
        response = self.client.get("/api/v1/exams/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_exam_detail_inactive_returns_404(self):
        exam = self.data["exam"]
        exam.is_active = False
        exam.save()
        response = self.client.get(f"/api/v1/exams/{exam.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_start_exam_creates_attempt(self):
        response = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

    def test_start_exam_returns_existing_attempt(self):
        r1 = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        r2 = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data["id"], r2.data["id"])

    def test_submit_exam_pass(self):
        start = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        attempt_id = start.data["id"]

        aqs = AttemptQuestion.objects.filter(attempt_id=attempt_id).select_related("question")
        answers = []
        for aq in aqs:
            correct = aq.question.options.filter(is_correct=True).first()
            assert correct is not None
            answers.append({"question_id": aq.question_id, "option_id": correct.pk})

        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_passed"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_submit_exam_sends_result_email(self):
        from django.core import mail

        start = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        attempt_id = start.data["id"]
        aqs = AttemptQuestion.objects.filter(attempt_id=attempt_id).select_related("question")
        answers = [
            {"question_id": aq.question_id, "option_id": aq.question.options.filter(is_correct=True).first().pk}  # type: ignore[union-attr]
            for aq in aqs
        ]
        self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Exam Result", mail.outbox[0].subject)
        self.assertIn("PASSED", mail.outbox[0].subject)

    def test_submit_exam_pass_updates_level_progress(self):
        """Passing a level_final exam should set LevelProgress to EXAM_PASSED."""
        start = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        attempt_id = start.data["id"]

        aqs = AttemptQuestion.objects.filter(attempt_id=attempt_id).select_related("question")
        answers = [
            {"question_id": aq.question_id, "option_id": aq.question.options.filter(is_correct=True).first().pk}  # type: ignore[union-attr]
            for aq in aqs
        ]

        self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )

        progress = LevelProgress.objects.get(student=self.profile, level=self.data["level"])
        self.assertEqual(progress.status, LevelProgress.Status.EXAM_PASSED)
        self.assertIsNotNone(progress.completed_at)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.highest_cleared_level, self.data["level"])

    def test_submit_exam_fail_updates_level_progress(self):
        """Failing a level_final exam should set LevelProgress to EXAM_FAILED."""
        start = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        attempt_id = start.data["id"]

        aqs = AttemptQuestion.objects.filter(attempt_id=attempt_id).select_related("question")
        answers = [
            {"question_id": aq.question_id, "option_id": aq.question.options.filter(is_correct=False).first().pk}  # type: ignore[union-attr]
            for aq in aqs
        ]

        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertFalse(response.data["is_passed"])

        progress = LevelProgress.objects.get(student=self.profile, level=self.data["level"])
        self.assertEqual(progress.status, LevelProgress.Status.EXAM_FAILED)

    def test_fail_does_not_downgrade_passed_level(self):
        """Failing a retake should NOT overwrite EXAM_PASSED status."""
        # First pass the exam
        start1 = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        aqs = AttemptQuestion.objects.filter(attempt_id=start1.data["id"]).select_related("question")
        answers = [
            {"question_id": aq.question_id, "option_id": aq.question.options.filter(is_correct=True).first().pk}  # type: ignore[union-attr]
            for aq in aqs
        ]
        self.client.post(
            f"/api/v1/exams/attempts/{start1.data['id']}/submit/",
            {"answers": answers},
            format="json",
        )
        progress = LevelProgress.objects.get(student=self.profile, level=self.data["level"])
        self.assertEqual(progress.status, LevelProgress.Status.EXAM_PASSED)

        # Now fail a second attempt
        start2 = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        aqs2 = AttemptQuestion.objects.filter(attempt_id=start2.data["id"]).select_related("question")
        wrong_answers = [
            {"question_id": aq.question_id, "option_id": aq.question.options.filter(is_correct=False).first().pk}  # type: ignore[union-attr]
            for aq in aqs2
        ]
        self.client.post(
            f"/api/v1/exams/attempts/{start2.data['id']}/submit/",
            {"answers": wrong_answers},
            format="json",
        )
        progress.refresh_from_db()
        self.assertEqual(progress.status, LevelProgress.Status.EXAM_PASSED)

    def test_submit_exam_fail(self):
        start = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        attempt_id = start.data["id"]

        aqs = AttemptQuestion.objects.filter(attempt_id=attempt_id).select_related("question")
        answers = []
        for aq in aqs:
            wrong = aq.question.options.filter(is_correct=False).first()
            assert wrong is not None
            answers.append({"question_id": aq.question_id, "option_id": wrong.pk})

        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_passed"])

    def test_cannot_submit_twice(self):
        start = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        attempt_id = start.data["id"]

        self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": []},
            format="json",
        )
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attempt_result(self):
        start = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        attempt_id = start.data["id"]
        self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": []},
            format="json",
        )
        response = self.client.get(f"/api/v1/exams/attempts/{attempt_id}/result/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("questions", response.data)

    def test_attempt_result_in_progress_returns_400(self):
        start = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        attempt_id = start.data["id"]
        response = self.client.get(f"/api/v1/exams/attempts/{attempt_id}/result/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attempt_list(self):
        self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        response = self.client.get("/api/v1/exams/attempts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 1)

    def test_start_exam_no_questions_returns_400(self):
        """Starting an exam when no questions exist should return 400."""
        from apps.exams.models import Question

        Question.objects.filter(level=self.data["level"]).delete()
        response = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("No questions", response.data["detail"])

    def test_start_exam_fewer_questions_than_required(self):
        """Exam with num_questions > pool should still create attempt with available questions."""
        from apps.exams.models import Question

        # Delete all but 2 questions (exam requires 5)
        qs = Question.objects.filter(level=self.data["level"])
        keep_ids = list(qs.values_list("id", flat=True)[:2])
        qs.exclude(id__in=keep_ids).delete()
        response = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        attempt_id = response.data["id"]
        aq_count = AttemptQuestion.objects.filter(attempt_id=attempt_id).count()
        self.assertEqual(aq_count, 2)

    def test_submit_with_empty_answers(self):
        """Submitting with no answers should result in score=0 and fail."""
        start = self.client.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        attempt_id = start.data["id"]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data["score"]), 0)
        self.assertFalse(response.data["is_passed"])


class ExamDataIsolationTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user_a, self.profile_a = self.factory.create_student(email="a@test.com")
        self.user_b, self.profile_b = self.factory.create_student(email="b@test.com")
        self.client_a = self.factory.get_auth_client(self.user_a)
        self.client_b = self.factory.get_auth_client(self.user_b)
        self.data = self.factory.setup_full_level(order=1, num_questions=5)
        _make_eligible(self.factory, self.profile_a, self.data)

    def test_student_cannot_see_others_attempts(self):
        """Student B's attempt list should not show Student A's attempts."""
        self.client_a.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        response = self.client_b.get("/api/v1/exams/attempts/")
        self.assertEqual(response.data["count"], 0)

    def test_student_cannot_submit_others_attempt(self):
        """Student B cannot submit Student A's attempt."""
        start = self.client_a.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        attempt_id = start.data["id"]
        response = self.client_b.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": []},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_cannot_view_others_result(self):
        """Student B cannot view Student A's attempt result."""
        start = self.client_a.post(f"/api/v1/exams/{self.data['exam'].pk}/start/")
        attempt_id = start.data["id"]
        self.client_a.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": []},
            format="json",
        )
        response = self.client_b.get(f"/api/v1/exams/attempts/{attempt_id}/result/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ExamEligibilityTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data1 = self.factory.setup_full_level(order=1, num_questions=5)
        self.data2 = self.factory.setup_full_level(order=2, num_questions=5)

    def test_cannot_start_level2_exam_without_passing_level1(self):
        response = self.client.post(f"/api/v1/exams/{self.data2['exam'].pk}/start/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_can_start_level2_after_passing_level1(self):
        self.factory.pass_level(self.profile, self.data1["level"])
        _make_eligible(self.factory, self.profile, self.data2)
        response = self.client.post(f"/api/v1/exams/{self.data2['exam'].pk}/start/")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_reattempt_after_fail_without_purchase(self):
        LevelProgress.objects.create(
            student=self.profile,
            level=self.data1["level"],
            status=LevelProgress.Status.EXAM_FAILED,
        )
        response = self.client.post(f"/api/v1/exams/{self.data1['exam'].pk}/start/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access_exams(self):
        anon = APIClient()
        response = anon.get(f"/api/v1/exams/{self.data1['exam'].pk}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_weekly_exam_start_blocked_until_prior_sessions_completed(self):
        weekly_exam = self.factory.create_exam(
            self.data1["level"],
            week=self.data1["week"],
            course=self.data1["course"],
            exam_type=Exam.ExamType.WEEKLY,
            num_questions=2,
        )
        for _ in range(2):
            self.factory.create_question(weekly_exam)
        self.factory.create_purchase(self.profile, self.data1["level"])

        response = self.client.post(f"/api/v1/exams/{weekly_exam.pk}/start/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("prior sessions", str(response.data["detail"]).lower())

    def test_weekly_exam_start_allowed_after_prior_sessions_completed(self):
        weekly_exam = self.factory.create_exam(
            self.data1["level"],
            week=self.data1["week"],
            course=self.data1["course"],
            exam_type=Exam.ExamType.WEEKLY,
            num_questions=2,
        )
        for _ in range(2):
            self.factory.create_question(weekly_exam)
        self.factory.create_purchase(self.profile, self.data1["level"])
        for session in self.data1["sessions"]:
            self.factory.complete_session(self.profile, session)

        response = self.client.post(f"/api/v1/exams/{weekly_exam.pk}/start/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class AdminExamAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.level = self.factory.create_level(order=1)
        self.exam = self.factory.create_exam(self.level)

    def test_admin_create_question(self):
        response = self.admin_client.post(
            "/api/v1/exams/admin/questions/",
            {
                "exam": self.exam.pk,
                "text": "What is 2+2?",
                "difficulty": "easy",
                "marks": 4,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_create_exam(self):
        response = self.admin_client.post(
            "/api/v1/exams/admin/",
            {
                "level": self.level.pk,
                "exam_type": "level_final",
                "title": "Level 1 Final",
                "duration_minutes": 60,
                "total_marks": 20,
                "passing_percentage": "50.00",
                "num_questions": 5,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_student_cannot_admin_exams(self):
        user, _ = self.factory.create_student()
        student_client = self.factory.get_auth_client(user)
        response = student_client.get("/api/v1/exams/admin/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AutoSubmitTimedOutExamsTaskTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        _, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=5)

    def test_timed_out_attempt_is_auto_submitted(self):
        from apps.exams.tasks import auto_submit_timed_out_exams

        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
        )
        # Backdate started_at to exceed duration
        ExamAttempt.objects.filter(pk=attempt.pk).update(
            started_at=timezone.now() - timedelta(hours=2),
        )
        count = auto_submit_timed_out_exams()
        self.assertEqual(count, 1)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, ExamAttempt.Status.TIMED_OUT)
        self.assertEqual(float(attempt.score or 0), 0)
        self.assertFalse(attempt.is_passed)

    def test_active_attempt_not_timed_out(self):
        from apps.exams.tasks import auto_submit_timed_out_exams

        ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
        )
        count = auto_submit_timed_out_exams()
        self.assertEqual(count, 0)


def _setup_custom_exam_level(factory, user, profile):
    """Create level, course, week, purchase, and mark syllabus complete (no sessions).
    Returns (level, course, week) so tests can create custom questions/exams."""
    level = factory.create_level(order=1)
    course = factory.create_course(level)
    week = factory.create_week(course, order=1)
    factory.create_purchase(profile, level)
    # No sessions means syllabus is automatically "complete"
    return level, course, week


class MultiSelectMCQTests(APITestCase):
    """Tests for multi-select MCQ question type."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.level, self.course, self.week = _setup_custom_exam_level(self.factory, self.user, self.profile)

        # Create a multi-select MCQ question manually
        from apps.exams.models import Option, Question

        self.exam = Exam.objects.create(
            level=self.level,
            exam_type=Exam.ExamType.LEVEL_FINAL,
            title="Multi MCQ Exam",
            duration_minutes=60,
            total_marks=4,
            passing_percentage=50,
            num_questions=1,
        )

        self.question = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="Select all correct",
            difficulty="easy",
            question_type="multi_mcq",
            marks=4,
        )
        self.opt_correct_1 = Option.objects.create(
            question=self.question,
            text="A",
            is_correct=True,
        )
        self.opt_correct_2 = Option.objects.create(
            question=self.question,
            text="B",
            is_correct=True,
        )
        self.opt_wrong = Option.objects.create(
            question=self.question,
            text="C",
            is_correct=False,
        )

    def _start_and_get_attempt_id(self):
        response = self.client.post(f"/api/v1/exams/{self.exam.pk}/start/")
        return response.data["id"]

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_multi_mcq_correct_all_selected(self):
        """Selecting all correct options (and no wrong ones) should award full marks."""
        attempt_id = self._start_and_get_attempt_id()
        answers = [
            {
                "question_id": self.question.pk,
                "option_ids": [self.opt_correct_1.pk, self.opt_correct_2.pk],
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_passed"])
        self.assertEqual(float(response.data["score"]), 4)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_multi_mcq_wrong_answer(self):
        """Selecting wrong options should result in 0 marks (or negative if configured)."""
        attempt_id = self._start_and_get_attempt_id()
        answers = [
            {
                "question_id": self.question.pk,
                "option_ids": [self.opt_wrong.pk],
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_passed"])
        self.assertEqual(float(response.data["score"]), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_multi_mcq_partial_answer(self):
        """Selecting only some correct options (missing one) should be marked wrong."""
        attempt_id = self._start_and_get_attempt_id()
        answers = [
            {
                "question_id": self.question.pk,
                "option_ids": [self.opt_correct_1.pk],  # missing opt_correct_2
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_passed"])
        self.assertEqual(float(response.data["score"]), 0)


class FillInTheBlankTests(APITestCase):
    """Tests for fill-in-the-blank question type."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.level, self.course, self.week = _setup_custom_exam_level(self.factory, self.user, self.profile)

        from apps.exams.models import Question

        self.exam = Exam.objects.create(
            level=self.level,
            exam_type=Exam.ExamType.LEVEL_FINAL,
            title="Fill Blank Exam",
            duration_minutes=60,
            total_marks=4,
            passing_percentage=50,
            num_questions=1,
        )

        self.question = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="What is 6*7?",
            difficulty="easy",
            question_type="fill_blank",
            marks=4,
            correct_text_answer="42",
        )

    def _start_and_get_attempt_id(self):
        response = self.client.post(f"/api/v1/exams/{self.exam.pk}/start/")
        return response.data["id"]

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_fill_blank_correct_answer(self):
        """Exact correct text answer should award full marks."""
        attempt_id = self._start_and_get_attempt_id()
        answers = [
            {
                "question_id": self.question.pk,
                "text_answer": "42",
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_passed"])
        self.assertEqual(float(response.data["score"]), 4)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_fill_blank_case_insensitive(self):
        """Answer comparison should be case-insensitive."""
        # Update question to have a text answer where case matters
        self.question.correct_text_answer = "Paris"
        self.question.text = "Capital of France?"
        self.question.save()

        attempt_id = self._start_and_get_attempt_id()
        answers = [
            {
                "question_id": self.question.pk,
                "text_answer": "paris",
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_passed"])
        self.assertEqual(float(response.data["score"]), 4)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_fill_blank_wrong_answer(self):
        """Wrong text answer should result in 0 marks."""
        attempt_id = self._start_and_get_attempt_id()
        answers = [
            {
                "question_id": self.question.pk,
                "text_answer": "99",
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_passed"])
        self.assertEqual(float(response.data["score"]), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_fill_blank_empty_answer(self):
        """Empty text answer should be treated as unanswered (0 marks, not negative)."""
        attempt_id = self._start_and_get_attempt_id()
        answers = [
            {
                "question_id": self.question.pk,
                "text_answer": "",
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_passed"])
        self.assertEqual(float(response.data["score"]), 0)


class NegativeMarkingTests(APITestCase):
    """Tests for negative marking on wrong answers."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.level, self.course, self.week = _setup_custom_exam_level(self.factory, self.user, self.profile)

        from apps.exams.models import Option, Question

        self.exam = Exam.objects.create(
            level=self.level,
            exam_type=Exam.ExamType.LEVEL_FINAL,
            title="Negative Marking Exam",
            duration_minutes=60,
            total_marks=4,
            passing_percentage=50,
            num_questions=1,
        )

        self.question = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="Negative mark question?",
            difficulty="easy",
            question_type="mcq",
            marks=4,
            negative_marks=1,
        )
        self.correct_option = Option.objects.create(
            question=self.question,
            text="Correct",
            is_correct=True,
        )
        self.wrong_option = Option.objects.create(
            question=self.question,
            text="Wrong",
            is_correct=False,
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_wrong_answer_gives_negative_score(self):
        """A wrong answer with negative_marks=1 should produce score=-1."""
        start = self.client.post(f"/api/v1/exams/{self.exam.pk}/start/")
        attempt_id = start.data["id"]
        answers = [
            {
                "question_id": self.question.pk,
                "option_id": self.wrong_option.pk,
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_passed"])
        self.assertLess(float(response.data["score"]), 0)
        self.assertEqual(float(response.data["score"]), -1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_negative_marks_on_fill_blank(self):
        """Wrong fill-in-the-blank with negative_marks should deduct marks."""
        self.question.question_type = "fill_blank"
        self.question.correct_text_answer = "42"
        self.question.save()

        start = self.client.post(f"/api/v1/exams/{self.exam.pk}/start/")
        attempt_id = start.data["id"]
        answers = [
            {
                "question_id": self.question.pk,
                "text_answer": "wrong",
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data["score"]), -1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_negative_marks_on_multi_mcq(self):
        """Wrong multi-select MCQ with negative_marks should deduct marks."""
        from apps.exams.models import Option

        self.question.question_type = "multi_mcq"
        self.question.save()
        # Add another correct option
        Option.objects.create(
            question=self.question,
            text="Correct 2",
            is_correct=True,
        )

        start = self.client.post(f"/api/v1/exams/{self.exam.pk}/start/")
        attempt_id = start.data["id"]
        answers = [
            {
                "question_id": self.question.pk,
                "option_ids": [self.wrong_option.pk],
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data["score"]), -1)


class QuestionExplanationTests(APITestCase):
    """Tests that explanation is returned in the result after submission."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.level, self.course, self.week = _setup_custom_exam_level(self.factory, self.user, self.profile)

        from apps.exams.models import Option, Question

        self.exam = Exam.objects.create(
            level=self.level,
            exam_type=Exam.ExamType.LEVEL_FINAL,
            title="Explanation Exam",
            duration_minutes=60,
            total_marks=4,
            passing_percentage=50,
            num_questions=1,
        )

        self.question = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="What is 2+2?",
            difficulty="easy",
            question_type="mcq",
            marks=4,
            explanation="2+2 equals 4 because of basic arithmetic.",
        )
        self.correct_option = Option.objects.create(
            question=self.question,
            text="4",
            is_correct=True,
        )
        self.wrong_option = Option.objects.create(
            question=self.question,
            text="5",
            is_correct=False,
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_explanation_in_result(self):
        """After submitting, the result endpoint should include question explanations."""
        start = self.client.post(f"/api/v1/exams/{self.exam.pk}/start/")
        attempt_id = start.data["id"]
        answers = [
            {
                "question_id": self.question.pk,
                "option_id": self.correct_option.pk,
            }
        ]
        self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        response = self.client.get(f"/api/v1/exams/attempts/{attempt_id}/result/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("questions", response.data)
        self.assertGreater(len(response.data["questions"]), 0)
        question_result = response.data["questions"][0]
        self.assertIn("explanation", question_result)
        self.assertEqual(
            question_result["explanation"],
            "2+2 equals 4 because of basic arithmetic.",
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_result_includes_selected_and_correct_option_details(self):
        start = self.client.post(f"/api/v1/exams/{self.exam.pk}/start/")
        attempt_id = start.data["id"]
        answers = [
            {
                "question_id": self.question.pk,
                "option_id": self.wrong_option.pk,
            }
        ]
        self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )

        response = self.client.get(f"/api/v1/exams/attempts/{attempt_id}/result/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        question_result = response.data["questions"][0]
        self.assertEqual(question_result["selected_option"], self.wrong_option.pk)
        self.assertEqual(question_result["selected_option_detail"]["text"], "5")
        self.assertEqual(question_result["correct_option_ids"], [self.correct_option.pk])
        self.assertEqual(question_result["correct_options"][0]["text"], "4")

        options = {item["id"]: item for item in question_result["options"]}
        self.assertTrue(options[self.correct_option.pk]["is_correct"])
        self.assertFalse(options[self.correct_option.pk]["is_selected"])
        self.assertFalse(options[self.wrong_option.pk]["is_correct"])
        self.assertTrue(options[self.wrong_option.pk]["is_selected"])


class ProctoringTests(APITestCase):
    """Tests for the proctoring violation system."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.level, self.course, self.week = _setup_custom_exam_level(self.factory, self.user, self.profile)

        from apps.exams.models import Option, Question

        self.exam = Exam.objects.create(
            level=self.level,
            exam_type=Exam.ExamType.LEVEL_FINAL,
            title="Proctored Exam",
            duration_minutes=60,
            total_marks=4,
            passing_percentage=50,
            num_questions=1,
            is_proctored=True,
            max_warnings=3,
        )

        self.question = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="Proctored question?",
            difficulty="easy",
            question_type="mcq",
            marks=4,
        )
        self.correct_option = Option.objects.create(
            question=self.question,
            text="Correct",
            is_correct=True,
        )
        Option.objects.create(
            question=self.question,
            text="Wrong",
            is_correct=False,
        )

    def _start_attempt(self):
        response = self.client.post(f"/api/v1/exams/{self.exam.pk}/start/")
        return response.data["id"]

    def test_report_violation_success(self):
        """Reporting a violation on a proctored exam should succeed."""
        attempt_id = self._start_attempt()
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/report-violation/",
            {"violation_type": "tab_switch", "details": "Student switched tabs"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["violation_type"], "tab_switch")
        self.assertEqual(response.data["warning_number"], 1)
        self.assertEqual(response.data["total_warnings"], 1)
        self.assertEqual(response.data["max_warnings"], 3)
        self.assertFalse(response.data["is_disqualified"])

    def test_get_violations_list(self):
        """GET violations endpoint should return all violations for an attempt."""
        attempt_id = self._start_attempt()
        # Report two violations
        self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/report-violation/",
            {"violation_type": "tab_switch"},
            format="json",
        )
        self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/report-violation/",
            {"violation_type": "full_screen_exit"},
            format="json",
        )
        response = self.client.get(
            f"/api/v1/exams/attempts/{attempt_id}/violations/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_warnings"], 2)
        self.assertEqual(len(response.data["violations"]), 2)
        self.assertFalse(response.data["is_disqualified"])

    def test_auto_disqualification_on_max_warnings(self):
        """Reaching max_warnings should auto-disqualify the attempt."""
        attempt_id = self._start_attempt()
        # Report 3 violations (max_warnings=3)
        for v_type in ["tab_switch", "full_screen_exit", "voice_detected"]:
            response = self.client.post(
                f"/api/v1/exams/attempts/{attempt_id}/report-violation/",
                {"violation_type": v_type},
                format="json",
            )
        # The third violation should trigger disqualification
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_disqualified"])
        self.assertEqual(response.data["total_warnings"], 3)

        # Verify the attempt is now disqualified in the database
        attempt = ExamAttempt.objects.get(pk=attempt_id)
        self.assertTrue(attempt.is_disqualified)
        self.assertEqual(attempt.status, ExamAttempt.Status.SUBMITTED)
        self.assertEqual(float(attempt.score or 0), 0)
        self.assertFalse(attempt.is_passed)

    def test_non_proctored_exam_rejects_violation(self):
        """Reporting a violation on a non-proctored exam should return 400."""
        self.exam.is_proctored = False
        self.exam.save()

        attempt_id = self._start_attempt()
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/report-violation/",
            {"violation_type": "tab_switch"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not proctored", response.data["detail"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_disqualified_attempt_cannot_be_submitted(self):
        """A disqualified attempt should reject submission with 400."""
        attempt_id = self._start_attempt()
        # Trigger disqualification by hitting max_warnings
        for v_type in ["tab_switch", "full_screen_exit", "voice_detected"]:
            self.client.post(
                f"/api/v1/exams/attempts/{attempt_id}/report-violation/",
                {"violation_type": v_type},
                format="json",
            )
        # Now try to submit answers
        answers = [
            {
                "question_id": self.question.pk,
                "option_id": self.correct_option.pk,
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("disqualified", response.data["detail"])


class ExamDeadlineEnforcementTests(APITestCase):
    """Tests for the hard deadline enforcement on exam submissions."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.level, self.course, self.week = _setup_custom_exam_level(self.factory, self.user, self.profile)

        from apps.exams.models import Option, Question

        self.exam = Exam.objects.create(
            level=self.level,
            exam_type=Exam.ExamType.LEVEL_FINAL,
            title="Deadline Exam",
            duration_minutes=30,
            total_marks=4,
            passing_percentage=50,
            num_questions=1,
        )

        self.question = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="Deadline test question?",
            difficulty="easy",
            question_type="mcq",
            marks=4,
        )
        self.correct_option = Option.objects.create(
            question=self.question,
            text="Correct",
            is_correct=True,
        )
        Option.objects.create(
            question=self.question,
            text="Wrong",
            is_correct=False,
        )

    def _start_attempt(self):
        response = self.client.post(f"/api/v1/exams/{self.exam.pk}/start/")
        return response.data["id"]

    def _build_correct_answers(self):
        return [{"question_id": self.question.pk, "option_id": self.correct_option.pk}]

    def test_submission_after_deadline_returns_400(self):
        """Submitting after started_at + duration + 30s grace should be rejected."""
        attempt_id = self._start_attempt()

        # Backdate started_at to 31+ minutes ago (duration=30 min, so deadline is 30 min + 30s)
        past_time = timezone.now() - timedelta(minutes=31, seconds=1)
        ExamAttempt.objects.filter(pk=attempt_id).update(started_at=past_time)

        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": self._build_correct_answers()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("deadline", response.data["detail"].lower())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_submission_within_deadline_succeeds(self):
        """Submitting well before the deadline should succeed."""
        attempt_id = self._start_attempt()

        # started_at is now (default), duration is 30 min — plenty of time
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": self._build_correct_answers()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_passed"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_submission_within_grace_period_succeeds(self):
        """Submitting within the 30-second grace window after deadline should succeed."""
        attempt_id = self._start_attempt()

        # Backdate so that we are 15 seconds past the deadline (within 30s grace)
        past_time = timezone.now() - timedelta(minutes=30, seconds=15)
        ExamAttempt.objects.filter(pk=attempt_id).update(started_at=past_time)

        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": self._build_correct_answers()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_timed_out_attempt_status_is_set_correctly(self):
        """After deadline rejection, the attempt should be TIMED_OUT with score 0."""
        attempt_id = self._start_attempt()

        past_time = timezone.now() - timedelta(minutes=31, seconds=1)
        ExamAttempt.objects.filter(pk=attempt_id).update(started_at=past_time)

        self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": self._build_correct_answers()},
            format="json",
        )

        attempt = ExamAttempt.objects.get(pk=attempt_id)
        self.assertEqual(attempt.status, ExamAttempt.Status.TIMED_OUT)
        self.assertEqual(float(attempt.score or 0), 0)
        self.assertFalse(attempt.is_passed)
        self.assertIsNotNone(attempt.submitted_at)


class ExamAnswerValidationTests(APITestCase):
    """Tests for edge cases in answer validation during exam submission."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.level, self.course, self.week = _setup_custom_exam_level(self.factory, self.user, self.profile)

        from apps.exams.models import Option, Question

        self.exam = Exam.objects.create(
            level=self.level,
            exam_type=Exam.ExamType.LEVEL_FINAL,
            title="Validation Exam",
            duration_minutes=60,
            total_marks=4,
            passing_percentage=50,
            num_questions=1,
        )

        # Create two questions — only one will be in the exam
        self.question1 = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="Question 1?",
            difficulty="easy",
            question_type="mcq",
            marks=4,
        )
        self.q1_correct = Option.objects.create(
            question=self.question1,
            text="Correct 1",
            is_correct=True,
        )
        self.q1_wrong = Option.objects.create(
            question=self.question1,
            text="Wrong 1",
            is_correct=False,
        )

        self.question2 = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="Question 2?",
            difficulty="easy",
            question_type="mcq",
            marks=4,
        )
        self.q2_correct = Option.objects.create(
            question=self.question2,
            text="Correct 2",
            is_correct=True,
        )
        Option.objects.create(
            question=self.question2,
            text="Wrong 2",
            is_correct=False,
        )

    def _start_attempt(self):
        response = self.client.post(f"/api/v1/exams/{self.exam.pk}/start/")
        return response.data["id"]

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_option_from_different_question_evaluated_as_wrong(self):
        """Submitting an option_id that belongs to a different question should be marked wrong."""
        attempt_id = self._start_attempt()

        # Find the actual question assigned to this attempt
        aq = AttemptQuestion.objects.filter(attempt_id=attempt_id).first()
        assert aq is not None
        actual_question_id = aq.question_id

        # Pick an option from the OTHER question
        if actual_question_id == self.question1.pk:
            wrong_option_id = self.q2_correct.pk
        else:
            wrong_option_id = self.q1_correct.pk

        answers = [{"question_id": actual_question_id, "option_id": wrong_option_id}]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The option does not belong to the attempt question, so it should be wrong
        aq.refresh_from_db()
        self.assertFalse(aq.is_correct)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_nonexistent_option_id_handled_gracefully(self):
        """Submitting an option_id that does not exist should not crash — treated as wrong."""
        attempt_id = self._start_attempt()
        aq = AttemptQuestion.objects.filter(attempt_id=attempt_id).first()
        assert aq is not None

        answers = [{"question_id": aq.question_id, "option_id": 999999}]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        aq.refresh_from_db()
        self.assertFalse(aq.is_correct)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_answers_for_questions_not_in_attempt_are_ignored(self):
        """Answers referencing questions not assigned to this attempt should be ignored."""
        attempt_id = self._start_attempt()
        aq = AttemptQuestion.objects.filter(attempt_id=attempt_id).first()
        assert aq is not None
        actual_question_id = aq.question_id

        # Determine which question is NOT in the attempt
        if actual_question_id == self.question1.pk:
            extra_question_id = self.question2.pk
            extra_option_id = self.q2_correct.pk
        else:
            extra_question_id = self.question1.pk
            extra_option_id = self.q1_correct.pk

        answers = [
            # A real answer for the actual attempt question (wrong on purpose)
            {"question_id": actual_question_id, "option_id": None},
            # An extra answer for a question NOT in the attempt
            {"question_id": extra_question_id, "option_id": extra_option_id},
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only the attempt's own questions should be evaluated; the extra answer is ignored
        self.assertEqual(AttemptQuestion.objects.filter(attempt_id=attempt_id).count(), 1)


class ExamSerializerLimitTests(APITestCase):
    """Tests for serializer field-level validation limits."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.level, self.course, self.week = _setup_custom_exam_level(self.factory, self.user, self.profile)

        from apps.exams.models import Option, Question

        self.exam = Exam.objects.create(
            level=self.level,
            exam_type=Exam.ExamType.LEVEL_FINAL,
            title="Limit Exam",
            duration_minutes=60,
            total_marks=4,
            passing_percentage=50,
            num_questions=1,
        )

        self.question = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="Serializer limit test?",
            difficulty="easy",
            question_type="mcq",
            marks=4,
        )
        Option.objects.create(
            question=self.question,
            text="Correct",
            is_correct=True,
        )
        Option.objects.create(
            question=self.question,
            text="Wrong",
            is_correct=False,
        )

    def _start_attempt(self):
        response = self.client.post(f"/api/v1/exams/{self.exam.pk}/start/")
        return response.data["id"]

    def test_text_answer_longer_than_1000_chars_rejected(self):
        """text_answer exceeding max_length=1000 should be rejected by the serializer."""
        attempt_id = self._start_attempt()
        answers = [
            {
                "question_id": self.question.pk,
                "text_answer": "x" * 1001,
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_more_than_200_answers_rejected(self):
        """Submitting more than 200 answer items should be rejected by max_length on answers."""
        attempt_id = self._start_attempt()
        answers = [{"question_id": i, "option_id": 1} for i in range(201)]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_more_than_20_option_ids_rejected(self):
        """Submitting more than 20 option_ids in a single answer should be rejected."""
        attempt_id = self._start_attempt()
        answers = [
            {
                "question_id": self.question.pk,
                "option_ids": list(range(1, 22)),  # 21 option_ids
            }
        ]
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/submit/",
            {"answers": answers},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
