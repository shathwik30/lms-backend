from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.exams.models import AttemptQuestion, ExamAttempt, Option
from apps.exams.services import ExamService
from apps.exams.tasks import auto_submit_timed_out_exams
from core.test_utils import TestFactory


def _create_aq(attempt, question, order=1, **kwargs):
    """Helper to create AttemptQuestion with required order field."""
    return AttemptQuestion.objects.create(
        attempt=attempt,
        question=question,
        order=order,
        **kwargs,
    )


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class AutoSubmitTimedOutExamsTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1)
        self.exam = self.data["exam"]

    def _create_in_progress_attempt(self, started_minutes_ago=120):
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            status=ExamAttempt.Status.IN_PROGRESS,
            total_marks=self.exam.total_marks,
        )
        # auto_now_add ignores passed values, so update directly
        started_at = timezone.now() - timedelta(minutes=started_minutes_ago)
        ExamAttempt.objects.filter(pk=attempt.pk).update(started_at=started_at)
        attempt.refresh_from_db()
        return attempt

    def test_auto_submits_timed_out_attempt(self):
        attempt = self._create_in_progress_attempt(started_minutes_ago=120)
        count = auto_submit_timed_out_exams()
        attempt.refresh_from_db()
        self.assertEqual(count, 1)
        self.assertEqual(attempt.status, ExamAttempt.Status.TIMED_OUT)
        self.assertIsNotNone(attempt.submitted_at)

    def test_does_not_submit_active_attempt(self):
        self._create_in_progress_attempt(started_minutes_ago=5)
        count = auto_submit_timed_out_exams()
        self.assertEqual(count, 0)

    def test_does_not_resubmit_already_submitted(self):
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            status=ExamAttempt.Status.SUBMITTED,
            submitted_at=timezone.now() - timedelta(minutes=60),
            total_marks=self.exam.total_marks,
        )
        ExamAttempt.objects.filter(pk=attempt.pk).update(
            started_at=timezone.now() - timedelta(minutes=120),
        )
        count = auto_submit_timed_out_exams()
        self.assertEqual(count, 0)

    def test_scores_saved_answers_on_timeout(self):
        attempt = self._create_in_progress_attempt(started_minutes_ago=120)
        question, correct_option = self.data["questions"][0]
        aq = _create_aq(attempt, question, order=1, selected_option=correct_option)
        auto_submit_timed_out_exams()
        aq.refresh_from_db()
        attempt.refresh_from_db()
        self.assertTrue(aq.is_correct)
        self.assertEqual(aq.marks_awarded, question.marks)
        self.assertEqual(attempt.score, question.marks)

    def test_wrong_answer_gets_negative_marks(self):
        attempt = self._create_in_progress_attempt(started_minutes_ago=120)
        question, _ = self.data["questions"][0]
        wrong_option = Option.objects.filter(question=question, is_correct=False).first()
        aq = _create_aq(attempt, question, order=1, selected_option=wrong_option)
        auto_submit_timed_out_exams()
        aq.refresh_from_db()
        self.assertFalse(aq.is_correct)
        self.assertEqual(aq.marks_awarded, -question.negative_marks)

    def test_unanswered_question_gets_zero(self):
        attempt = self._create_in_progress_attempt(started_minutes_ago=120)
        question, _ = self.data["questions"][0]
        aq = _create_aq(attempt, question, order=1)
        auto_submit_timed_out_exams()
        aq.refresh_from_db()
        self.assertIsNone(aq.is_correct)
        self.assertEqual(aq.marks_awarded, 0)

    def test_multiple_timed_out_attempts(self):
        _, profile2 = self.factory.create_student(email="s2@test.com")
        self._create_in_progress_attempt(started_minutes_ago=120)
        attempt2 = ExamAttempt.objects.create(
            student=profile2,
            exam=self.exam,
            status=ExamAttempt.Status.IN_PROGRESS,
            total_marks=self.exam.total_marks,
        )
        ExamAttempt.objects.filter(pk=attempt2.pk).update(
            started_at=timezone.now() - timedelta(minutes=120),
        )
        count = auto_submit_timed_out_exams()
        self.assertEqual(count, 2)

    def test_pass_threshold_calculated_correctly(self):
        attempt = self._create_in_progress_attempt(started_minutes_ago=120)
        for i, (question, correct_option) in enumerate(self.data["questions"]):
            _create_aq(attempt, question, order=i + 1, selected_option=correct_option)
        auto_submit_timed_out_exams()
        attempt.refresh_from_db()
        self.assertTrue(attempt.is_passed)

    def test_submitted_at_uses_deadline_not_current_time(self):
        started_at = timezone.now() - timedelta(minutes=120)
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            status=ExamAttempt.Status.IN_PROGRESS,
            total_marks=self.exam.total_marks,
        )
        ExamAttempt.objects.filter(pk=attempt.pk).update(started_at=started_at)
        auto_submit_timed_out_exams()
        attempt.refresh_from_db()
        expected_deadline = started_at + timedelta(minutes=self.exam.duration_minutes)
        self.assertEqual(attempt.submitted_at, expected_deadline)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class ScoreAttemptTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1)
        self.exam = self.data["exam"]
        self.attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.exam,
            status=ExamAttempt.Status.IN_PROGRESS,
            started_at=timezone.now(),
            total_marks=self.exam.total_marks,
        )

    def test_score_with_no_answers(self):
        score = ExamService._score_timed_out_attempt(self.attempt)
        self.assertEqual(score, 0)

    def test_score_correct_mcq(self):
        question, correct_option = self.data["questions"][0]
        _create_aq(self.attempt, question, order=1, selected_option=correct_option)
        score = ExamService._score_timed_out_attempt(self.attempt)
        self.assertEqual(score, question.marks)

    def test_score_wrong_mcq(self):
        question, _ = self.data["questions"][0]
        wrong = Option.objects.filter(question=question, is_correct=False).first()
        _create_aq(self.attempt, question, order=1, selected_option=wrong)
        score = ExamService._score_timed_out_attempt(self.attempt)
        self.assertEqual(score, -question.negative_marks)

    def test_score_fill_blank_correct(self):
        question, _ = self.data["questions"][0]
        question.question_type = "fill_blank"
        question.correct_text_answer = "42"
        question.save()
        _create_aq(self.attempt, question, order=1, text_answer="42")
        score = ExamService._score_timed_out_attempt(self.attempt)
        self.assertEqual(score, question.marks)

    def test_score_fill_blank_case_insensitive(self):
        question, _ = self.data["questions"][0]
        question.question_type = "fill_blank"
        question.correct_text_answer = "Newton"
        question.save()
        _create_aq(self.attempt, question, order=1, text_answer="newton")
        score = ExamService._score_timed_out_attempt(self.attempt)
        self.assertEqual(score, question.marks)

    def test_score_fill_blank_wrong(self):
        question, _ = self.data["questions"][0]
        question.question_type = "fill_blank"
        question.correct_text_answer = "42"
        question.save()
        _create_aq(self.attempt, question, order=1, text_answer="wrong")
        score = ExamService._score_timed_out_attempt(self.attempt)
        self.assertEqual(score, -question.negative_marks)

    def test_score_unanswered_gets_zero(self):
        question, _ = self.data["questions"][0]
        _create_aq(self.attempt, question, order=1)
        score = ExamService._score_timed_out_attempt(self.attempt)
        self.assertEqual(score, 0)

    def test_score_mixed_answers(self):
        q1, correct1 = self.data["questions"][0]
        q2, _ = self.data["questions"][1]
        wrong2 = Option.objects.filter(question=q2, is_correct=False).first()
        _create_aq(self.attempt, q1, order=1, selected_option=correct1)
        _create_aq(self.attempt, q2, order=2, selected_option=wrong2)
        score = ExamService._score_timed_out_attempt(self.attempt)
        expected = q1.marks - q2.negative_marks
        self.assertEqual(score, expected)
