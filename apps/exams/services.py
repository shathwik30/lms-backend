from __future__ import annotations

import random
from datetime import timedelta

from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.progress.models import LevelProgress
from apps.users.models import StudentProfile
from apps.users.models import User as UserModel
from core.constants import ErrorMessage, ExamConstants
from core.exceptions import LevelLocked
from core.services.eligibility import EligibilityService

from .models import AttemptQuestion, Exam, ExamAttempt, ProctoringViolation, Question


class ExamService:
    @staticmethod
    def get_exam_with_eligibility(student_profile: StudentProfile, exam_pk: int) -> tuple[Exam | None, bool]:
        try:
            exam = Exam.objects.select_related("level", "week").get(pk=exam_pk, is_active=True)
        except Exam.DoesNotExist:
            return None, False
        eligible = EligibilityService.can_attempt_exam(student_profile, exam)
        return exam, eligible

    @staticmethod
    def start_exam(student_profile: StudentProfile, exam: Exam) -> tuple[ExamAttempt | None, bool | None]:
        if not EligibilityService.can_attempt_exam(student_profile, exam):
            raise LevelLocked()

        active_attempt = ExamAttempt.objects.filter(
            student=student_profile,
            exam=exam,
            status=ExamAttempt.Status.IN_PROGRESS,
        ).first()
        if active_attempt:
            return active_attempt, False

        pool = Question.objects.filter(level=exam.level, is_active=True)
        if exam.week:
            pool = pool.filter(week=exam.week)

        pool_list = list(pool)
        if not pool_list:
            return None, None

        count = min(exam.num_questions, len(pool_list))
        selected = random.sample(pool_list, count)

        attempt = ExamAttempt.objects.create(
            student=student_profile,
            exam=exam,
            total_marks=sum(q.marks for q in selected),
        )

        random.shuffle(selected)
        attempt_questions = [AttemptQuestion(attempt=attempt, question=q, order=i + 1) for i, q in enumerate(selected)]
        AttemptQuestion.objects.bulk_create(attempt_questions)

        return attempt, True

    @classmethod
    def submit_exam(
        cls, user: UserModel, attempt: ExamAttempt, answers_data: list[dict]
    ) -> tuple[ExamAttempt | None, str | None]:
        if attempt.is_disqualified:
            return None, ErrorMessage.ATTEMPT_DISQUALIFIED

        if attempt.status != ExamAttempt.Status.IN_PROGRESS:
            return None, ErrorMessage.ATTEMPT_ALREADY_SUBMITTED

        deadline = attempt.started_at + timedelta(minutes=attempt.exam.duration_minutes)
        if timezone.now() > deadline + timedelta(seconds=ExamConstants.SUBMISSION_GRACE_SECONDS):
            attempt.status = ExamAttempt.Status.TIMED_OUT
            attempt.submitted_at = deadline
            attempt.score = 0
            attempt.is_passed = False
            attempt.save()
            return None, ErrorMessage.SUBMISSION_DEADLINE_PASSED

        answers_map = {a["question_id"]: a for a in answers_data}

        total_score = 0
        attempt_questions = list(
            attempt.attempt_questions.select_related("question").prefetch_related("question__options")
        )
        multi_mcq_updates = []

        for aq in attempt_questions:
            answer = answers_map.get(aq.question_id)

            if not answer:
                aq.is_correct = None
                aq.marks_awarded = 0
                continue

            q_type = aq.question.question_type
            if q_type == Question.QuestionType.MCQ:
                cls._evaluate_mcq(aq, answer)
            elif q_type == Question.QuestionType.MULTI_MCQ:
                cls._evaluate_multi_mcq(aq, answer, multi_mcq_updates)
            elif q_type == Question.QuestionType.FILL_BLANK:
                cls._evaluate_fill_blank(aq, answer)

            total_score += aq.marks_awarded

        AttemptQuestion.objects.bulk_update(
            attempt_questions,
            ["selected_option_id", "text_answer", "is_correct", "marks_awarded"],
        )

        for aq, option_ids in multi_mcq_updates:
            aq.selected_options.set(option_ids)

        attempt.score = total_score
        attempt.submitted_at = timezone.now()
        attempt.status = ExamAttempt.Status.SUBMITTED

        pass_score = (attempt.exam.passing_percentage / ExamConstants.PERCENTAGE_DIVISOR) * attempt.total_marks
        attempt.is_passed = total_score >= pass_score
        attempt.save()

        if attempt.exam.exam_type == Exam.ExamType.LEVEL_FINAL:
            cls._update_level_progress(user, attempt)

        from core.tasks import send_exam_result_task

        send_exam_result_task.delay(
            email=user.email,
            full_name=user.full_name,
            exam_title=attempt.exam.title,
            score=str(attempt.score),
            total_marks=attempt.total_marks,
            is_passed=attempt.is_passed,
        )

        return attempt, None

    @staticmethod
    def report_violation(
        attempt: ExamAttempt, violation_type: str, details: str = ""
    ) -> tuple[dict | None, str | None]:
        if not attempt.exam.is_proctored:
            return None, ErrorMessage.EXAM_NOT_PROCTORED

        if attempt.is_disqualified:
            return None, ErrorMessage.ATTEMPT_ALREADY_DISQUALIFIED

        warning_count = attempt.violations.count() + 1

        violation = ProctoringViolation.objects.create(
            attempt=attempt,
            violation_type=violation_type,
            warning_number=warning_count,
            details=details,
        )

        if warning_count >= attempt.exam.max_warnings:
            attempt.is_disqualified = True
            attempt.status = ExamAttempt.Status.SUBMITTED
            attempt.submitted_at = timezone.now()
            attempt.score = 0
            attempt.is_passed = False
            attempt.save()

            NotificationService.create(
                user=attempt.student.user,
                title="Exam Disqualified",
                message=f"You were disqualified from {attempt.exam.title} due to repeated proctoring violations.",
                notification_type=Notification.NotificationType.EXAM_RESULT,
                data={"attempt_id": attempt.id},
            )

        return {
            "violation": violation,
            "total_warnings": warning_count,
            "max_warnings": attempt.exam.max_warnings,
            "is_disqualified": attempt.is_disqualified,
        }, None

    @staticmethod
    def _evaluate_mcq(aq: AttemptQuestion, answer: dict) -> None:
        selected_option_id = answer.get("option_id")
        if selected_option_id:
            option = next((o for o in aq.question.options.all() if o.pk == selected_option_id), None)
            if option:
                aq.selected_option_id = selected_option_id
                aq.is_correct = option.is_correct
                if option.is_correct:
                    aq.marks_awarded = aq.question.marks
                else:
                    aq.marks_awarded = -aq.question.negative_marks
            else:
                aq.is_correct = False
                aq.marks_awarded = -aq.question.negative_marks
        else:
            aq.is_correct = None
            aq.marks_awarded = 0

    @staticmethod
    def _evaluate_multi_mcq(aq: AttemptQuestion, answer: dict, multi_mcq_updates: list) -> None:
        option_ids = answer.get("option_ids", [])
        if option_ids:
            all_options = list(aq.question.options.all())
            correct_ids = {o.id for o in all_options if o.is_correct}
            selected_ids = set(option_ids)
            valid_ids = {o.id for o in all_options if o.id in selected_ids}
            aq.is_correct = valid_ids == correct_ids
            if aq.is_correct:
                aq.marks_awarded = aq.question.marks
            else:
                aq.marks_awarded = -aq.question.negative_marks
            multi_mcq_updates.append((aq, list(valid_ids)))
        else:
            aq.is_correct = None
            aq.marks_awarded = 0

    @staticmethod
    def _evaluate_fill_blank(aq: AttemptQuestion, answer: dict) -> None:
        text_answer = answer.get("text_answer", "").strip()
        aq.text_answer = text_answer
        if text_answer:
            correct = aq.question.correct_text_answer.strip()
            aq.is_correct = text_answer.lower() == correct.lower()
            if aq.is_correct:
                aq.marks_awarded = aq.question.marks
            else:
                aq.marks_awarded = -aq.question.negative_marks
        else:
            aq.is_correct = None
            aq.marks_awarded = 0

    @staticmethod
    def _update_level_progress(user: UserModel, attempt: ExamAttempt) -> None:
        profile = user.student_profile
        level = attempt.exam.level

        progress, _ = LevelProgress.objects.get_or_create(
            student=profile,
            level=level,
        )

        if attempt.is_passed:
            progress.status = LevelProgress.Status.EXAM_PASSED
            progress.completed_at = timezone.now()
            progress.save()

            profile.highest_cleared_level = level
            profile.save()

            from apps.certificates.models import Certificate

            Certificate.objects.get_or_create(
                student=profile,
                level=level,
                defaults={
                    "score": attempt.score,
                    "total_marks": attempt.total_marks,
                },
            )

            NotificationService.create(
                user=user,
                title=f"Level {level.name} Cleared!",
                message=f"Congratulations! You passed {attempt.exam.title} with {attempt.score}/{attempt.total_marks}.",
                notification_type=Notification.NotificationType.EXAM_RESULT,
                data={"level_id": level.id, "attempt_id": attempt.id},
            )
        else:
            if progress.status != LevelProgress.Status.EXAM_PASSED:
                progress.status = LevelProgress.Status.EXAM_FAILED
                progress.save()

            NotificationService.create(
                user=user,
                title=f"Exam Result: {attempt.exam.title}",
                message=f"You scored {attempt.score}/{attempt.total_marks}. Review the material and try again.",
                notification_type=Notification.NotificationType.EXAM_RESULT,
                data={"level_id": level.id, "attempt_id": attempt.id},
            )
