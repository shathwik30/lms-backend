from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.exams.models import (
    AttemptQuestion,
    Exam,
    ExamAttempt,
    Option,
    ProctoringViolation,
    Question,
)
from apps.exams.services import ExamService
from apps.notifications.models import Notification
from apps.progress.models import LevelProgress
from core.constants import ErrorMessage, ExamConstants
from core.exceptions import (
    FinalExamAttemptsExhausted,
    LevelLocked,
    OnboardingAlreadyAttempted,
)
from core.test_utils import TestFactory


def _make_eligible(factory, profile, data):
    """Create purchase and complete all sessions so student can attempt the level final exam."""
    factory.create_purchase(profile, data["level"])
    for s in data["sessions"]:
        factory.complete_session(profile, s)


class StartExamOnboardingAlreadyAttemptedTests(TestCase):
    """Coverage: start_exam lines 38-39 — OnboardingAlreadyAttempted raised."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.exam = self.factory.create_exam(
            self.level,
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=1,
        )
        # Pre-create a question in the exam pool
        self.factory.create_question(self.exam)

    def test_onboarding_already_attempted_raises(self):
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save(update_fields=["is_onboarding_exam_attempted"])

        with self.assertRaises(OnboardingAlreadyAttempted):
            ExamService.start_exam(self.profile, self.exam)

    def test_onboarding_not_attempted_does_not_raise(self):
        """Sanity check: first attempt should succeed (not raise)."""
        attempt, is_new = ExamService.start_exam(self.profile, self.exam)
        self.assertIsNotNone(attempt)
        self.assertTrue(is_new)


class StartExamFinalExamAttemptsExhaustedTests(TestCase):
    """Coverage: start_exam line 46 — FinalExamAttemptsExhausted raised."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=5)
        self.level = self.data["level"]
        self.exam = self.data["exam"]
        # Make student eligible first (purchase + complete syllabus)
        _make_eligible(self.factory, self.profile, self.data)

    def test_final_exam_attempts_exhausted_raises(self):
        # Exhaust all attempts
        self.level.max_final_exam_attempts = 2
        self.level.save(update_fields=["max_final_exam_attempts"])
        LevelProgress.objects.update_or_create(
            student=self.profile,
            level=self.level,
            defaults={"final_exam_attempts_used": 2},
        )

        with self.assertRaises(FinalExamAttemptsExhausted):
            ExamService.start_exam(self.profile, self.exam)

    def test_final_exam_with_attempts_remaining_does_not_raise(self):
        self.level.max_final_exam_attempts = 3
        self.level.save(update_fields=["max_final_exam_attempts"])
        LevelProgress.objects.update_or_create(
            student=self.profile,
            level=self.level,
            defaults={"final_exam_attempts_used": 1},
        )
        attempt, is_new = ExamService.start_exam(self.profile, self.exam)
        self.assertIsNotNone(attempt)
        self.assertTrue(is_new)


class StartExamLevelLockedTests(TestCase):
    """Coverage: start_exam line 47 — LevelLocked raised when ineligible (not exhausted)."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.exam = self.factory.create_exam(self.level, exam_type=Exam.ExamType.LEVEL_FINAL)

    def test_no_purchase_raises_level_locked(self):
        # No purchase means not eligible; no progress means not exhausted -> LevelLocked
        with self.assertRaises(LevelLocked):
            ExamService.start_exam(self.profile, self.exam)


class StartExamOnboardingQuestionPoolTests(TestCase):
    """Coverage: start_exam — onboarding pulls from its own exam pool."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level1 = self.factory.create_level(order=1)
        self.level2 = self.factory.create_level(order=2)
        self.level3 = self.factory.create_level(order=3)

        self.exam = self.factory.create_exam(
            self.level1,
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=3,
        )

        # Create questions across different levels, all in the same onboarding exam
        self.q1, _ = self.factory.create_question(self.exam, level=self.level1, marks=4)
        self.q2, _ = self.factory.create_question(self.exam, level=self.level2, marks=4)
        self.q3, _ = self.factory.create_question(self.exam, level=self.level3, marks=4)

    def test_onboarding_pulls_questions_from_all_levels(self):
        attempt, is_new = ExamService.start_exam(self.profile, self.exam)
        self.assertTrue(is_new)
        self.assertIsNotNone(attempt)

        question_ids = set(AttemptQuestion.objects.filter(attempt=attempt).values_list("question_id", flat=True))
        # All three questions from different levels should be included
        self.assertEqual(question_ids, {self.q1.pk, self.q2.pk, self.q3.pk})


class StartExamPerExamPoolTests(TestCase):
    """Coverage: start_exam — each exam pulls only from its own question pool."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=3)
        self.level = self.data["level"]
        self.exam1 = self.data["exam"]

        # Create a second exam with its own questions
        self.exam2 = self.factory.create_exam(
            self.level,
            exam_type=Exam.ExamType.WEEKLY,
            num_questions=3,
        )
        for _ in range(3):
            self.factory.create_question(self.exam2)

        _make_eligible(self.factory, self.profile, self.data)

    def test_exam_only_pulls_its_own_questions(self):
        attempt, is_new = ExamService.start_exam(self.profile, self.exam1)
        self.assertTrue(is_new)

        question_ids = set(AttemptQuestion.objects.filter(attempt=attempt).values_list("question_id", flat=True))
        # All selected questions must belong to exam1
        exam1_question_ids = set(Question.objects.filter(exam=self.exam1).values_list("id", flat=True))
        self.assertTrue(question_ids.issubset(exam1_question_ids))
        # None from exam2
        exam2_question_ids = set(Question.objects.filter(exam=self.exam2).values_list("id", flat=True))
        self.assertFalse(question_ids & exam2_question_ids)


class ProcessOnboardingResultTests(TestCase):
    """Coverage: _process_onboarding_result lines 184-245."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level1 = self.factory.create_level(order=1, passing_percentage=50)
        self.level2 = self.factory.create_level(order=2, passing_percentage=50)
        self.level3 = self.factory.create_level(order=3, passing_percentage=50)

        self.exam = self.factory.create_exam(
            self.level1,
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=6,
        )

    def _create_attempt_with_scores(self, level_scores):
        """
        Create an attempt with attempt_questions scored per level.

        level_scores: list of (level, marks_per_question, num_correct, num_total)
        """
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=sum(m * t for _, m, _, t in level_scores),
        )

        order = 1
        for level, marks, num_correct, num_total in level_scores:
            for i in range(num_total):
                q = Question.objects.create(
                    exam=self.exam,
                    level=level,
                    text=f"Q for {level.name} #{i}",
                    difficulty="medium",
                    marks=marks,
                )
                Option.objects.create(question=q, text="Correct", is_correct=True)
                Option.objects.create(question=q, text="Wrong", is_correct=False)

                AttemptQuestion.objects.create(
                    attempt=attempt,
                    question=q,
                    order=order,
                    marks_awarded=marks if i < num_correct else 0,
                    is_correct=i < num_correct,
                )
                order += 1

        return attempt

    def test_pass_some_levels_fail_at_level_n(self):
        """Pass levels 1 and 2, fail at level 3 -> highest_cleared=level2, current_level=level3."""
        attempt = self._create_attempt_with_scores(
            [
                (self.level1, 4, 2, 2),  # 100% >= 50% -> pass
                (self.level2, 4, 2, 2),  # 100% >= 50% -> pass
                (self.level3, 4, 0, 2),  # 0% < 50% -> fail
            ]
        )

        ExamService._process_onboarding_result(self.user, attempt)

        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_onboarding_exam_attempted)
        self.assertEqual(self.profile.highest_cleared_level, self.level2)
        self.assertEqual(self.profile.current_level, self.level3)

        # Level 1 and 2 should have EXAM_PASSED progress
        self.assertTrue(
            LevelProgress.objects.filter(
                student=self.profile, level=self.level1, status=LevelProgress.Status.EXAM_PASSED
            ).exists()
        )
        self.assertTrue(
            LevelProgress.objects.filter(
                student=self.profile, level=self.level2, status=LevelProgress.Status.EXAM_PASSED
            ).exists()
        )
        # Level 3 should NOT have EXAM_PASSED progress
        self.assertFalse(
            LevelProgress.objects.filter(
                student=self.profile, level=self.level3, status=LevelProgress.Status.EXAM_PASSED
            ).exists()
        )

    def test_pass_all_levels(self):
        """Pass all levels -> highest_cleared=level3, current_level=level3 (no next level)."""
        attempt = self._create_attempt_with_scores(
            [
                (self.level1, 4, 2, 2),  # pass
                (self.level2, 4, 2, 2),  # pass
                (self.level3, 4, 2, 2),  # pass
            ]
        )

        ExamService._process_onboarding_result(self.user, attempt)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.highest_cleared_level, self.level3)
        # No level with order=4, so current_level falls back to highest_cleared
        self.assertEqual(self.profile.current_level, self.level3)

    def test_fail_level_1(self):
        """Fail level 1 -> no highest_cleared, current_level=level1."""
        attempt = self._create_attempt_with_scores(
            [
                (self.level1, 4, 0, 2),  # 0% < 50% -> fail
                (self.level2, 4, 2, 2),  # would pass but processing stops at level 1
                (self.level3, 4, 2, 2),
            ]
        )

        ExamService._process_onboarding_result(self.user, attempt)

        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.highest_cleared_level)
        self.assertEqual(self.profile.current_level, self.level1)

    def test_no_questions_for_level_skips_it(self):
        """Level with total=0 questions is skipped, not treated as pass or fail."""
        # Only create questions for level1 and level3, skip level2
        attempt = self._create_attempt_with_scores(
            [
                (self.level1, 4, 2, 2),  # pass
                (self.level3, 4, 2, 2),  # pass
            ]
        )
        # level2 has no questions in the attempt -> total=0 -> skipped
        # Processing: level1 passes, level2 skipped (continue), level3 passes

        ExamService._process_onboarding_result(self.user, attempt)

        self.profile.refresh_from_db()
        # level2 is skipped, so highest_cleared is level3
        self.assertEqual(self.profile.highest_cleared_level, self.level3)

    def test_notification_created_on_onboarding(self):
        attempt = self._create_attempt_with_scores(
            [
                (self.level1, 4, 2, 2),
            ]
        )

        ExamService._process_onboarding_result(self.user, attempt)

        notification = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.NotificationType.EXAM_RESULT,
            title="Placement Test Complete",
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn(str(attempt.score), notification.message)


class ResetLevelProgressTests(TestCase):
    """Coverage: _reset_level_progress lines 255-257 — delegates to ProgressService."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)

    @patch("apps.progress.services.ProgressService.reset_level_progress")
    def test_delegates_to_progress_service(self, mock_reset):
        ExamService._reset_level_progress(self.profile, self.level)
        mock_reset.assert_called_once_with(self.profile, self.level)


class ScoreTimedOutAttemptMultiMcqTests(TestCase):
    """Coverage: _score_timed_out_attempt lines 278-282 — multi-MCQ scoring."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.exam = self.factory.create_exam(
            self.level,
            exam_type=Exam.ExamType.WEEKLY,
            num_questions=1,
        )

    def test_timed_out_multi_mcq_correct(self):
        """Multi-MCQ with all correct options selected scores full marks."""
        q = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="Multi select Q",
            difficulty="medium",
            question_type=Question.QuestionType.MULTI_MCQ,
            marks=4,
            negative_marks=1,
        )
        opt_a = Option.objects.create(question=q, text="A", is_correct=True)
        opt_b = Option.objects.create(question=q, text="B", is_correct=True)
        Option.objects.create(question=q, text="C", is_correct=False)

        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=4,
        )
        aq = AttemptQuestion.objects.create(
            attempt=attempt,
            question=q,
            order=1,
        )
        # Simulate previously saved multi-MCQ selections (correct)
        aq.selected_options.set([opt_a.pk, opt_b.pk])

        score = ExamService._score_timed_out_attempt(attempt)
        aq.refresh_from_db()

        self.assertEqual(score, Decimal(4))
        self.assertTrue(aq.is_correct)
        self.assertEqual(aq.marks_awarded, Decimal(4))

    def test_timed_out_multi_mcq_incorrect(self):
        """Multi-MCQ with wrong options selected gets negative marks."""
        q = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="Multi select Q",
            difficulty="medium",
            question_type=Question.QuestionType.MULTI_MCQ,
            marks=4,
            negative_marks=1,
        )
        opt_a = Option.objects.create(question=q, text="A", is_correct=True)
        Option.objects.create(question=q, text="B", is_correct=True)
        opt_c = Option.objects.create(question=q, text="C", is_correct=False)

        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=4,
        )
        aq = AttemptQuestion.objects.create(
            attempt=attempt,
            question=q,
            order=1,
        )
        # Select only one correct + one wrong -> incorrect
        aq.selected_options.set([opt_a.pk, opt_c.pk])

        score = ExamService._score_timed_out_attempt(attempt)
        aq.refresh_from_db()

        self.assertEqual(score, Decimal(-1))
        self.assertFalse(aq.is_correct)
        self.assertEqual(aq.marks_awarded, Decimal(-1))


class ReportViolationNonProctoredTests(TestCase):
    """Coverage: report_violation line 300-301 — EXAM_NOT_PROCTORED."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.exam = self.factory.create_exam(self.level)
        self.exam.is_proctored = False
        self.exam.save(update_fields=["is_proctored"])

        self.attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=20,
        )

    def test_non_proctored_exam_returns_error(self):
        result, error = ExamService.report_violation(
            self.attempt,
            ProctoringViolation.ViolationType.TAB_SWITCH,
        )
        self.assertIsNone(result)
        self.assertEqual(error, ErrorMessage.EXAM_NOT_PROCTORED)


class ReportViolationAlreadyDisqualifiedTests(TestCase):
    """Coverage: report_violation line 303-304 — ATTEMPT_ALREADY_DISQUALIFIED."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.exam = self.factory.create_exam(self.level)
        self.exam.is_proctored = True
        self.exam.save(update_fields=["is_proctored"])

        self.attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=20,
            is_disqualified=True,
        )

    def test_already_disqualified_returns_error(self):
        result, error = ExamService.report_violation(
            self.attempt,
            ProctoringViolation.ViolationType.TAB_SWITCH,
        )
        self.assertIsNone(result)
        self.assertEqual(error, ErrorMessage.ATTEMPT_ALREADY_DISQUALIFIED)


class ReportViolationMaxWarningsDisqualificationTests(TestCase):
    """Coverage: report_violation lines 316-330 — disqualification on max warnings."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.exam = self.factory.create_exam(self.level)
        self.exam.is_proctored = True
        self.exam.max_warnings = 2
        self.exam.save(update_fields=["is_proctored", "max_warnings"])

        self.attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=20,
        )

    def test_reaching_max_warnings_disqualifies(self):
        # First violation — below threshold
        result1, error1 = ExamService.report_violation(
            self.attempt,
            ProctoringViolation.ViolationType.TAB_SWITCH,
            "First warning",
        )
        self.assertIsNone(error1)
        self.assertFalse(result1["is_disqualified"])
        self.assertEqual(result1["total_warnings"], 1)

        # Second violation — reaches max_warnings=2 -> disqualify
        result2, error2 = ExamService.report_violation(
            self.attempt,
            ProctoringViolation.ViolationType.FULL_SCREEN_EXIT,
            "Second warning",
        )
        self.assertIsNone(error2)
        self.assertTrue(result2["is_disqualified"])
        self.assertEqual(result2["total_warnings"], 2)

        # Verify attempt state
        self.attempt.refresh_from_db()
        self.assertTrue(self.attempt.is_disqualified)
        self.assertEqual(self.attempt.status, ExamAttempt.Status.SUBMITTED)
        self.assertEqual(self.attempt.score, 0)
        self.assertFalse(self.attempt.is_passed)
        self.assertIsNotNone(self.attempt.submitted_at)

        # Verify disqualification notification was created
        notification = Notification.objects.filter(
            user=self.user,
            title="Exam Disqualified",
            notification_type=Notification.NotificationType.EXAM_RESULT,
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn("disqualified", notification.message)

    def test_violation_below_threshold_does_not_disqualify(self):
        self.exam.max_warnings = 5
        self.exam.save(update_fields=["max_warnings"])

        result, error = ExamService.report_violation(
            self.attempt,
            ProctoringViolation.ViolationType.VOICE_DETECTED,
        )
        self.assertIsNone(error)
        self.assertFalse(result["is_disqualified"])
        self.assertEqual(result["total_warnings"], 1)
        self.assertEqual(result["max_warnings"], 5)

        self.attempt.refresh_from_db()
        self.assertFalse(self.attempt.is_disqualified)


class EvaluateMultiMcqNoOptionsTests(TestCase):
    """Coverage: _evaluate_multi_mcq lines 372-374 — empty option_ids."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)

    def test_empty_option_ids_marks_none_zero(self):
        exam = self.factory.create_exam(self.level, num_questions=1)
        q = Question.objects.create(
            exam=exam,
            level=self.level,
            text="Multi MCQ Q",
            difficulty="medium",
            question_type=Question.QuestionType.MULTI_MCQ,
            marks=4,
            negative_marks=1,
        )
        Option.objects.create(question=q, text="A", is_correct=True)
        Option.objects.create(question=q, text="B", is_correct=False)
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=exam,
            total_marks=4,
        )
        aq = AttemptQuestion.objects.create(
            attempt=attempt,
            question=q,
            order=1,
        )
        # Prefetch options so _evaluate_multi_mcq can access them
        aq.question = Question.objects.prefetch_related("options").get(pk=q.pk)

        multi_mcq_updates = []
        answer = {"question_id": q.pk, "option_ids": []}

        ExamService._evaluate_multi_mcq(aq, answer, multi_mcq_updates)

        self.assertIsNone(aq.is_correct)
        self.assertEqual(aq.marks_awarded, 0)
        self.assertEqual(len(multi_mcq_updates), 0)

    def test_missing_option_ids_key_marks_none_zero(self):
        exam = self.factory.create_exam(self.level, num_questions=1)
        q = Question.objects.create(
            exam=exam,
            level=self.level,
            text="Multi MCQ Q",
            difficulty="medium",
            question_type=Question.QuestionType.MULTI_MCQ,
            marks=4,
        )
        Option.objects.create(question=q, text="A", is_correct=True)
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=exam,
            total_marks=4,
        )
        aq = AttemptQuestion.objects.create(
            attempt=attempt,
            question=q,
            order=1,
        )
        aq.question = Question.objects.prefetch_related("options").get(pk=q.pk)

        multi_mcq_updates = []
        answer = {"question_id": q.pk}  # no option_ids key at all

        ExamService._evaluate_multi_mcq(aq, answer, multi_mcq_updates)

        self.assertIsNone(aq.is_correct)
        self.assertEqual(aq.marks_awarded, 0)


class UpdateLevelProgressFailWithAttemptsRemainingTests(TestCase):
    """Coverage: _update_level_progress lines 451-463 — fail with retries left."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=5)
        self.level = self.data["level"]
        self.level.max_final_exam_attempts = 3
        self.level.save(update_fields=["max_final_exam_attempts"])
        self.exam = self.data["exam"]

    def test_fail_increments_counter_and_notifies(self):
        LevelProgress.objects.create(
            student=self.profile,
            level=self.level,
            status=LevelProgress.Status.SYLLABUS_COMPLETE,
            final_exam_attempts_used=0,
        )

        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=20,
            score=Decimal("5"),
            is_passed=False,
            status=ExamAttempt.Status.SUBMITTED,
        )

        ExamService._update_level_progress(self.user, attempt)

        progress = LevelProgress.objects.get(student=self.profile, level=self.level)
        self.assertEqual(progress.final_exam_attempts_used, 1)
        self.assertEqual(progress.status, LevelProgress.Status.EXAM_FAILED)

        # Notification should mention remaining attempts
        notification = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.NotificationType.EXAM_RESULT,
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn("2 attempt(s) remaining", notification.message)

    def test_fail_second_attempt_increments_correctly(self):
        LevelProgress.objects.create(
            student=self.profile,
            level=self.level,
            status=LevelProgress.Status.EXAM_FAILED,
            final_exam_attempts_used=1,
        )

        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=20,
            score=Decimal("5"),
            is_passed=False,
            status=ExamAttempt.Status.SUBMITTED,
        )

        ExamService._update_level_progress(self.user, attempt)

        progress = LevelProgress.objects.get(student=self.profile, level=self.level)
        self.assertEqual(progress.final_exam_attempts_used, 2)

        notification = Notification.objects.filter(
            user=self.user,
            notification_type=Notification.NotificationType.EXAM_RESULT,
        ).first()
        self.assertIn("1 attempt(s) remaining", notification.message)


class UpdateLevelProgressFailAttemptsExhaustedTests(TestCase):
    """Coverage: _update_level_progress lines 436-450 — fail with all attempts used."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=5)
        self.level = self.data["level"]
        self.level.max_final_exam_attempts = 2
        self.level.save(update_fields=["max_final_exam_attempts"])
        self.exam = self.data["exam"]

    @patch("apps.exams.services.ExamService._reset_level_progress")
    def test_exhausted_attempts_resets_and_notifies(self, mock_reset):
        LevelProgress.objects.create(
            student=self.profile,
            level=self.level,
            status=LevelProgress.Status.EXAM_FAILED,
            final_exam_attempts_used=1,
        )

        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=20,
            score=Decimal("5"),
            is_passed=False,
            status=ExamAttempt.Status.SUBMITTED,
        )

        ExamService._update_level_progress(self.user, attempt)

        # Verify _reset_level_progress was called
        mock_reset.assert_called_once_with(self.profile, self.level)

        # After reset, status should be EXAM_FAILED
        progress = LevelProgress.objects.get(student=self.profile, level=self.level)
        self.assertEqual(progress.status, LevelProgress.Status.EXAM_FAILED)

        # Notification about exhausted attempts
        notification = Notification.objects.filter(
            user=self.user,
            title__contains="Attempts Exhausted",
            notification_type=Notification.NotificationType.EXAM_RESULT,
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn("All 2 attempts used", notification.message)
        self.assertIn("reset", notification.message)


class UpdateLevelProgressPassTests(TestCase):
    """Coverage: _update_level_progress — pass updates progress and profile."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=5)
        self.level = self.data["level"]
        self.exam = self.data["exam"]

    def test_pass_updates_progress_and_profile(self):
        LevelProgress.objects.create(
            student=self.profile,
            level=self.level,
            status=LevelProgress.Status.SYLLABUS_COMPLETE,
        )

        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=20,
            score=Decimal("15"),
            is_passed=True,
            status=ExamAttempt.Status.SUBMITTED,
        )

        ExamService._update_level_progress(self.user, attempt)

        # Progress updated
        progress = LevelProgress.objects.get(student=self.profile, level=self.level)
        self.assertEqual(progress.status, LevelProgress.Status.EXAM_PASSED)
        self.assertIsNotNone(progress.completed_at)

        # Profile updated
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.highest_cleared_level, self.level)

        # Notification created
        notification = Notification.objects.filter(
            user=self.user,
            title__contains="Cleared",
            notification_type=Notification.NotificationType.EXAM_RESULT,
        ).first()
        self.assertIsNotNone(notification)
        self.assertIn("Congratulations", notification.message)


class SubmitExamOnboardingTests(TestCase):
    """Coverage: submit_exam line 164-165 — onboarding exam calls _process_onboarding_result."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1, passing_percentage=50)

        self.exam = self.factory.create_exam(
            self.level,
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=1,
            passing_percentage=50,
        )

        self.q = Question.objects.create(
            exam=self.exam,
            level=self.level,
            text="Onboarding Q",
            difficulty="easy",
            marks=4,
        )
        self.correct_opt = Option.objects.create(
            question=self.q,
            text="Correct",
            is_correct=True,
        )
        Option.objects.create(question=self.q, text="Wrong", is_correct=False)

    @patch("apps.exams.services.ExamService._process_onboarding_result")
    @patch("core.tasks.send_exam_result_task.delay")
    def test_submit_onboarding_calls_process(self, mock_email_task, mock_process):
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=4,
            status=ExamAttempt.Status.IN_PROGRESS,
        )
        AttemptQuestion.objects.create(
            attempt=attempt,
            question=self.q,
            order=1,
        )

        answers = [{"question_id": self.q.pk, "option_id": self.correct_opt.pk}]
        result_attempt, error = ExamService.submit_exam(self.user, attempt, answers)

        self.assertIsNone(error)
        self.assertIsNotNone(result_attempt)
        mock_process.assert_called_once_with(self.user, attempt)
        mock_email_task.assert_called_once()


class SubmitExamTimedOutBeyondGraceTests(TestCase):
    """Coverage: submit_exam lines 112-120 — timed out beyond grace period."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=2)
        self.level = self.data["level"]
        self.exam = self.data["exam"]
        self.exam.duration_minutes = 30
        self.exam.passing_percentage = Decimal("50")
        self.exam.save(update_fields=["duration_minutes", "passing_percentage"])

    def test_submit_after_grace_period_returns_timed_out(self):
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=8,
            status=ExamAttempt.Status.IN_PROGRESS,
        )

        # Create attempt questions with correct answers saved
        for i, (q, correct_opt) in enumerate(self.data["questions"][:2]):
            AttemptQuestion.objects.create(
                attempt=attempt,
                question=q,
                order=i + 1,
                selected_option=correct_opt,
            )

        # Backdate started_at beyond deadline + grace
        past_time = timezone.now() - timedelta(
            minutes=self.exam.duration_minutes,
            seconds=ExamConstants.SUBMISSION_GRACE_SECONDS + 10,
        )
        ExamAttempt.objects.filter(pk=attempt.pk).update(started_at=past_time)
        attempt.refresh_from_db()

        answers = [
            {"question_id": self.data["questions"][0][0].pk, "option_id": self.data["questions"][0][1].pk},
            {"question_id": self.data["questions"][1][0].pk, "option_id": self.data["questions"][1][1].pk},
        ]

        result_attempt, error = ExamService.submit_exam(self.user, attempt, answers)

        self.assertIsNone(result_attempt)
        self.assertEqual(error, ErrorMessage.SUBMISSION_DEADLINE_PASSED)

        attempt.refresh_from_db()
        self.assertEqual(attempt.status, ExamAttempt.Status.TIMED_OUT)
        self.assertIsNotNone(attempt.score)
        self.assertIsNotNone(attempt.is_passed)

    def test_submit_within_grace_period_succeeds(self):
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=8,
            status=ExamAttempt.Status.IN_PROGRESS,
        )
        for i, (q, _correct_opt) in enumerate(self.data["questions"][:2]):
            AttemptQuestion.objects.create(
                attempt=attempt,
                question=q,
                order=i + 1,
            )

        # Set started_at to be just past duration but within grace
        past_time = timezone.now() - timedelta(
            minutes=self.exam.duration_minutes,
            seconds=ExamConstants.SUBMISSION_GRACE_SECONDS - 10,
        )
        ExamAttempt.objects.filter(pk=attempt.pk).update(started_at=past_time)
        attempt.refresh_from_db()

        answers = [
            {"question_id": self.data["questions"][0][0].pk, "option_id": self.data["questions"][0][1].pk},
        ]

        with patch("core.tasks.send_exam_result_task.delay"):
            result_attempt, error = ExamService.submit_exam(self.user, attempt, answers)

        self.assertIsNone(error)
        self.assertIsNotNone(result_attempt)
        self.assertEqual(result_attempt.status, ExamAttempt.Status.SUBMITTED)


class SubmitExamDisqualifiedTests(TestCase):
    """Coverage: submit_exam lines 105-106 — disqualified attempt returns error."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.exam = self.factory.create_exam(self.level)

    def test_disqualified_attempt_returns_error(self):
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=20,
            is_disqualified=True,
        )
        result, error = ExamService.submit_exam(self.user, attempt, [])
        self.assertIsNone(result)
        self.assertEqual(error, ErrorMessage.ATTEMPT_DISQUALIFIED)


class SubmitExamAlreadySubmittedTests(TestCase):
    """Coverage: submit_exam lines 108-109 — already submitted attempt."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.exam = self.factory.create_exam(self.level)

    def test_already_submitted_attempt_returns_error(self):
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=20,
            status=ExamAttempt.Status.SUBMITTED,
        )
        result, error = ExamService.submit_exam(self.user, attempt, [])
        self.assertIsNone(result)
        self.assertEqual(error, ErrorMessage.ATTEMPT_ALREADY_SUBMITTED)


class StartExamNoQuestionsTests(TestCase):
    """Coverage: start_exam lines 73-74 — no questions available returns None."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)

    def test_onboarding_no_questions_returns_none(self):
        exam = self.factory.create_exam(
            self.level,
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=5,
        )
        # No questions exist at all
        attempt, is_new = ExamService.start_exam(self.profile, exam)
        self.assertIsNone(attempt)
        self.assertIsNone(is_new)


class StartExamReturnsExistingAttemptTests(TestCase):
    """Coverage: start_exam lines 59-60 — returns existing in-progress attempt."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.exam = self.factory.create_exam(
            self.level,
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=1,
        )
        self.q, _ = self.factory.create_question(self.exam)

    def test_returns_existing_in_progress_attempt(self):
        attempt1, is_new1 = ExamService.start_exam(self.profile, self.exam)
        self.assertTrue(is_new1)

        # Second call should return the same attempt
        attempt2, is_new2 = ExamService.start_exam(self.profile, self.exam)
        self.assertFalse(is_new2)
        self.assertEqual(attempt1.pk, attempt2.pk)


class SubmitExamLevelFinalTests(TestCase):
    """Coverage: submit_exam line 166-167 — level_final calls _update_level_progress."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1, num_questions=2)
        self.level = self.data["level"]
        self.exam = self.data["exam"]
        self.exam.num_questions = 2
        self.exam.passing_percentage = Decimal("50")
        self.exam.save(update_fields=["num_questions", "passing_percentage"])

    @patch("apps.exams.services.ExamService._update_level_progress")
    @patch("core.tasks.send_exam_result_task.delay")
    def test_submit_level_final_calls_update_progress(self, mock_email, mock_update):
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            total_marks=8,
            status=ExamAttempt.Status.IN_PROGRESS,
        )
        q, correct = self.data["questions"][0]
        AttemptQuestion.objects.create(
            attempt=attempt,
            question=q,
            order=1,
        )

        answers = [{"question_id": q.pk, "option_id": correct.pk}]
        result_attempt, error = ExamService.submit_exam(self.user, attempt, answers)

        self.assertIsNone(error)
        mock_update.assert_called_once_with(self.user, attempt)
