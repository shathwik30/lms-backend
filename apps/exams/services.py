from __future__ import annotations

import logging
import random
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.progress.models import LevelProgress
from apps.users.models import StudentProfile
from apps.users.models import User as UserModel
from core.constants import ErrorMessage, ExamConstants
from core.exceptions import FinalExamAttemptsExhausted, LevelLocked, OnboardingAlreadyAttempted
from core.services.eligibility import EligibilityService

from .models import AttemptQuestion, Exam, ExamAttempt, ProctoringViolation, Question

logger = logging.getLogger(__name__)


class ExamService:
    @staticmethod
    def get_exam_with_eligibility(student_profile: StudentProfile, exam_pk: int) -> tuple[Exam | None, bool]:
        try:
            exam = Exam.objects.select_related("level", "week", "course").get(pk=exam_pk, is_active=True)
        except Exam.DoesNotExist:
            return None, False
        eligible = EligibilityService.can_attempt_exam(student_profile, exam)
        return exam, eligible

    @staticmethod
    def start_exam(student_profile: StudentProfile, exam: Exam) -> tuple[ExamAttempt | None, bool | None]:
        if exam.exam_type == Exam.ExamType.ONBOARDING:
            if student_profile.onboarding_exam_attempted:
                raise OnboardingAlreadyAttempted()
        elif not EligibilityService.can_attempt_exam(student_profile, exam):
            if exam.exam_type == Exam.ExamType.LEVEL_FINAL:
                progress = LevelProgress.objects.filter(student=student_profile, level=exam.level).first()
                if progress and progress.final_exam_attempts_used >= exam.level.max_final_exam_attempts:
                    raise FinalExamAttemptsExhausted()
            raise LevelLocked()

        with transaction.atomic():
            active_attempt = (
                ExamAttempt.objects.select_for_update()
                .filter(
                    student=student_profile,
                    exam=exam,
                    status=ExamAttempt.Status.IN_PROGRESS,
                )
                .first()
            )
            if active_attempt:
                return active_attempt, False

            if exam.exam_type == Exam.ExamType.ONBOARDING:
                # Pull questions from ALL levels
                pool = Question.objects.filter(is_active=True)
            else:
                pool = Question.objects.filter(level=exam.level, is_active=True)
                if exam.week:
                    pool = pool.filter(week=exam.week)
                if exam.course:
                    pool = pool.filter(course=exam.course)

            pool_ids_marks = list(pool.values_list("id", "marks"))
            if not pool_ids_marks:
                return None, None

            count = min(exam.num_questions, len(pool_ids_marks))
            if count < exam.num_questions:
                logger.warning(
                    "Exam %d: only %d questions available, required %d",
                    exam.pk,
                    count,
                    exam.num_questions,
                )
            selected_pairs = random.sample(pool_ids_marks, count)

            attempt = ExamAttempt.objects.create(
                student=student_profile,
                exam=exam,
                total_marks=sum(marks for _, marks in selected_pairs),
            )

            random.shuffle(selected_pairs)
            attempt_questions = [
                AttemptQuestion(attempt=attempt, question_id=qid, order=i + 1)
                for i, (qid, _) in enumerate(selected_pairs)
            ]
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
            timed_score = cls._score_timed_out_attempt(attempt)
            pass_score = (attempt.exam.passing_percentage / ExamConstants.PERCENTAGE_DIVISOR) * attempt.total_marks
            attempt.status = ExamAttempt.Status.TIMED_OUT
            attempt.submitted_at = deadline
            attempt.score = timed_score
            attempt.is_passed = timed_score >= pass_score
            attempt.save(update_fields=["status", "submitted_at", "score", "is_passed"])
            return None, ErrorMessage.SUBMISSION_DEADLINE_PASSED

        answers_map = {a["question_id"]: a for a in answers_data}

        total_score: Decimal = Decimal(0)
        attempt_questions = list(
            attempt.attempt_questions.select_related("question").prefetch_related("question__options")
        )
        multi_mcq_updates: list[tuple[AttemptQuestion, list[int]]] = []

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
        attempt.save(update_fields=["score", "submitted_at", "status", "is_passed"])

        if attempt.exam.exam_type == Exam.ExamType.ONBOARDING:
            cls._process_onboarding_result(user, attempt)
        elif attempt.exam.exam_type == Exam.ExamType.LEVEL_FINAL:
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
    def _process_onboarding_result(user: UserModel, attempt: ExamAttempt) -> None:
        from apps.levels.models import Level

        profile = user.student_profile
        profile.onboarding_exam_attempted = True

        # Group questions by level, score per-level
        attempt_questions = list(attempt.attempt_questions.select_related("question__level"))

        level_scores: dict[int, dict] = {}
        for aq in attempt_questions:
            level_id = aq.question.level_id
            if level_id not in level_scores:
                level_scores[level_id] = {"scored": Decimal(0), "total": Decimal(0)}
            level_scores[level_id]["total"] += aq.question.marks
            if aq.marks_awarded > 0:
                level_scores[level_id]["scored"] += aq.marks_awarded

        levels = Level.objects.filter(id__in=level_scores.keys(), is_active=True).order_by("order")

        highest_cleared = None
        for level in levels:
            data = level_scores.get(level.id)
            if not data or data["total"] == 0:
                continue
            percentage = (data["scored"] / data["total"]) * 100
            if percentage >= level.passing_percentage:
                LevelProgress.objects.update_or_create(
                    student=profile,
                    level=level,
                    defaults={
                        "status": LevelProgress.Status.EXAM_PASSED,
                        "completed_at": timezone.now(),
                    },
                )
                highest_cleared = level
            else:
                # Failed this level — stop clearing subsequent levels
                break

        if highest_cleared:
            profile.highest_cleared_level = highest_cleared
            # Set current level to the next one after highest cleared
            next_level = Level.objects.filter(order=highest_cleared.order + 1, is_active=True).first()
            if next_level:
                profile.current_level = next_level
            else:
                profile.current_level = highest_cleared
        else:
            # Failed level 1 — start at level 1
            first_level = Level.objects.filter(is_active=True).order_by("order").first()
            if first_level:
                profile.current_level = first_level

        profile.save(update_fields=["onboarding_exam_attempted", "highest_cleared_level", "current_level"])

        NotificationService.create(
            user=user,
            title="Placement Test Complete",
            message=f"Your placement test is complete. Score: {attempt.score}/{attempt.total_marks}.",
            notification_type=Notification.NotificationType.EXAM_RESULT,
            data={"attempt_id": attempt.id},
        )

    @staticmethod
    def _reset_level_progress(student: StudentProfile, level) -> None:
        from apps.progress.services import ProgressService

        ProgressService.reset_level_progress(student, level)

    @staticmethod
    def _score_timed_out_attempt(attempt: ExamAttempt) -> Decimal:
        """Score previously-saved answers for a timed-out attempt."""
        total_score = Decimal(0)
        attempt_questions = list(
            attempt.attempt_questions.select_related("question").prefetch_related(
                "question__options", "selected_options"
            )
        )

        for aq in attempt_questions:
            if aq.selected_option_id:
                option = next((o for o in aq.question.options.all() if o.pk == aq.selected_option_id), None)
                if option:
                    aq.is_correct = option.is_correct
                    aq.marks_awarded = aq.question.marks if option.is_correct else -aq.question.negative_marks
                else:
                    aq.is_correct = False
                    aq.marks_awarded = -aq.question.negative_marks
            elif any(True for _ in aq.selected_options.all()):
                correct_ids = {o.id for o in aq.question.options.all() if o.is_correct}
                selected_ids = {o.id for o in aq.selected_options.all()}
                aq.is_correct = selected_ids == correct_ids
                aq.marks_awarded = aq.question.marks if aq.is_correct else -aq.question.negative_marks
            elif aq.text_answer:
                correct = (aq.question.correct_text_answer or "").strip()
                aq.is_correct = aq.text_answer.strip().lower() == correct.lower()
                aq.marks_awarded = aq.question.marks if aq.is_correct else -aq.question.negative_marks
            else:
                aq.is_correct = None
                aq.marks_awarded = 0

            total_score += aq.marks_awarded

        AttemptQuestion.objects.bulk_update(attempt_questions, ["is_correct", "marks_awarded"])
        return total_score

    @staticmethod
    def report_violation(
        attempt: ExamAttempt, violation_type: str, details: str = ""
    ) -> tuple[dict | None, str | None]:
        if not attempt.exam.is_proctored:
            return None, ErrorMessage.EXAM_NOT_PROCTORED

        if attempt.is_disqualified:
            return None, ErrorMessage.ATTEMPT_ALREADY_DISQUALIFIED

        with transaction.atomic():
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
                attempt.save(update_fields=["is_disqualified", "status", "submitted_at", "score", "is_passed"])

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
            progress.save(update_fields=["status", "completed_at"])

            profile.highest_cleared_level = level
            profile.save(update_fields=["highest_cleared_level"])

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
            from django.db.models import F

            # Atomically increment attempts_used to avoid race conditions
            LevelProgress.objects.filter(pk=progress.pk).update(
                final_exam_attempts_used=F("final_exam_attempts_used") + 1,
            )
            progress.refresh_from_db()

            if progress.final_exam_attempts_used >= level.max_final_exam_attempts:
                # Reset level progress (zeroes attempts_used, sets status=IN_PROGRESS)
                ExamService._reset_level_progress(profile, level)
                # Re-read after reset to avoid stale in-memory state
                LevelProgress.objects.filter(pk=progress.pk).update(
                    status=LevelProgress.Status.EXAM_FAILED,
                )

                NotificationService.create(
                    user=user,
                    title=f"Level {level.name} — Attempts Exhausted",
                    message=f"All {level.max_final_exam_attempts} attempts used. Level progress has been reset.",
                    notification_type=Notification.NotificationType.EXAM_RESULT,
                    data={"level_id": level.id, "attempt_id": attempt.id},
                )
            else:
                LevelProgress.objects.filter(pk=progress.pk).exclude(
                    status=LevelProgress.Status.EXAM_PASSED,
                ).update(status=LevelProgress.Status.EXAM_FAILED)

                remaining = level.max_final_exam_attempts - progress.final_exam_attempts_used
                NotificationService.create(
                    user=user,
                    title=f"Exam Result: {attempt.exam.title}",
                    message=f"You scored {attempt.score}/{attempt.total_marks}. {remaining} attempt(s) remaining.",
                    notification_type=Notification.NotificationType.EXAM_RESULT,
                    data={"level_id": level.id, "attempt_id": attempt.id},
                )
