from django.test import TestCase, override_settings

from apps.exams.models import Exam
from apps.levels.models import Level
from apps.progress.models import LevelProgress
from core.constants import NextAction
from core.services.eligibility import EligibilityService
from core.test_utils import TestFactory


class EligibilityServiceTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        _, self.profile = self.factory.create_student()
        self.data1 = self.factory.setup_full_level(order=1, num_sessions=2, num_questions=5)
        self.data2 = self.factory.setup_full_level(order=2, num_sessions=2, num_questions=5)

    # ── is_syllabus_complete ──

    def test_syllabus_incomplete(self):
        self.assertFalse(EligibilityService.is_syllabus_complete(self.profile, self.data1["level"]))

    def test_syllabus_complete(self):
        for s in self.data1["sessions"]:
            self.factory.complete_session(self.profile, s)
        self.assertTrue(EligibilityService.is_syllabus_complete(self.profile, self.data1["level"]))

    def test_syllabus_complete_partial_sessions(self):
        self.factory.complete_session(self.profile, self.data1["sessions"][0])
        self.assertFalse(EligibilityService.is_syllabus_complete(self.profile, self.data1["level"]))

    def test_syllabus_complete_with_zero_sessions(self):
        """Level with no active sessions is considered complete."""
        empty_level = self.factory.create_level(order=99)
        self.assertTrue(EligibilityService.is_syllabus_complete(self.profile, empty_level))

    def test_syllabus_incomplete_videos_done_no_feedback(self):
        """All videos watched but no feedback submitted — not completed via service."""
        from django.utils import timezone

        from apps.progress.models import SessionProgress

        for s in self.data1["sessions"]:
            SessionProgress.objects.create(
                student=self.profile,
                session=s,
                watched_seconds=s.duration_seconds,
                is_completed=False,
                completed_at=timezone.now(),
            )
        self.assertFalse(EligibilityService.is_syllabus_complete(self.profile, self.data1["level"]))

    # ── has_active_purchase ──

    def test_has_active_purchase_true(self):
        self.factory.create_purchase(self.profile, self.data1["level"])
        self.assertTrue(EligibilityService.has_active_purchase(self.profile, self.data1["level"]))

    def test_has_active_purchase_false_no_purchase(self):
        self.assertFalse(EligibilityService.has_active_purchase(self.profile, self.data1["level"]))

    def test_has_active_purchase_false_expired(self):
        """Expired purchase with status=ACTIVE should NOT count."""
        self.factory.create_expired_purchase(self.profile, self.data1["level"])
        self.assertFalse(EligibilityService.has_active_purchase(self.profile, self.data1["level"]))

    # ── has_cleared_level ──

    def test_not_cleared(self):
        self.assertFalse(EligibilityService.has_cleared_level(self.profile, self.data1["level"]))

    def test_cleared(self):
        self.factory.pass_level(self.profile, self.data1["level"])
        self.assertTrue(EligibilityService.has_cleared_level(self.profile, self.data1["level"]))

    # ── has_cleared_previous_level ──

    def test_level1_has_no_prerequisite(self):
        self.assertTrue(EligibilityService.has_cleared_previous_level(self.profile, self.data1["level"]))

    def test_level2_needs_level1(self):
        self.assertFalse(EligibilityService.has_cleared_previous_level(self.profile, self.data2["level"]))

    def test_level2_after_clearing_level1(self):
        self.factory.pass_level(self.profile, self.data1["level"])
        self.assertTrue(EligibilityService.has_cleared_previous_level(self.profile, self.data2["level"]))

    # ── can_attempt_exam ──

    def test_can_attempt_level1_final_with_purchase_and_syllabus(self):
        self.factory.create_purchase(self.profile, self.data1["level"])
        for s in self.data1["sessions"]:
            self.factory.complete_session(self.profile, s)
        self.assertTrue(EligibilityService.can_attempt_exam(self.profile, self.data1["exam"]))

    def test_cannot_attempt_level1_final_without_purchase(self):
        self.assertFalse(EligibilityService.can_attempt_exam(self.profile, self.data1["exam"]))

    def test_cannot_attempt_level2_exam_without_clearing(self):
        self.factory.create_purchase(self.profile, self.data2["level"])
        self.assertFalse(EligibilityService.can_attempt_exam(self.profile, self.data2["exam"]))

    def test_can_attempt_level2_after_clearing_level1(self):
        self.factory.pass_level(self.profile, self.data1["level"])
        self.factory.create_purchase(self.profile, self.data2["level"])
        for s in self.data2["sessions"]:
            self.factory.complete_session(self.profile, s)
        self.assertTrue(EligibilityService.can_attempt_exam(self.profile, self.data2["exam"]))

    def test_cannot_attempt_final_with_exhausted_attempts(self):
        self.factory.create_purchase(self.profile, self.data1["level"])
        for s in self.data1["sessions"]:
            self.factory.complete_session(self.profile, s)
        LevelProgress.objects.create(
            student=self.profile,
            level=self.data1["level"],
            status=LevelProgress.Status.EXAM_FAILED,
            final_exam_attempts_used=self.data1["level"].max_final_exam_attempts,
        )
        self.assertFalse(EligibilityService.can_attempt_exam(self.profile, self.data1["exam"]))

    # ── can_attempt_exam: weekly exams ──

    def test_weekly_exam_without_purchase_blocked(self):
        weekly_exam = self.factory.create_exam(
            self.data1["level"],
            week=self.data1["week"],
            exam_type=Exam.ExamType.WEEKLY,
            num_questions=3,
        )
        self.assertFalse(EligibilityService.can_attempt_exam(self.profile, weekly_exam))

    def test_weekly_exam_with_purchase_allowed(self):
        weekly_exam = self.factory.create_exam(
            self.data1["level"],
            week=self.data1["week"],
            exam_type=Exam.ExamType.WEEKLY,
            num_questions=3,
        )
        self.factory.create_purchase(self.profile, self.data1["level"])
        self.assertTrue(EligibilityService.can_attempt_exam(self.profile, weekly_exam))

    # ── can_attempt_exam: onboarding ──

    def test_onboarding_exam_allowed_first_time(self):
        onboarding_exam = self.factory.create_exam(
            self.data1["level"],
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=5,
        )
        self.assertTrue(EligibilityService.can_attempt_exam(self.profile, onboarding_exam))

    def test_onboarding_exam_only_allowed_for_current_onboarding_level(self):
        self.profile.current_level = self.data2["level"]
        self.profile.save(update_fields=["current_level"])
        onboarding_exam_level1 = self.factory.create_exam(
            self.data1["level"],
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=5,
        )
        onboarding_exam_level2 = self.factory.create_exam(
            self.data2["level"],
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=5,
        )
        self.assertFalse(EligibilityService.can_attempt_exam(self.profile, onboarding_exam_level1))
        self.assertTrue(EligibilityService.can_attempt_exam(self.profile, onboarding_exam_level2))

    def test_onboarding_exam_blocked_after_attempt(self):
        onboarding_exam = self.factory.create_exam(
            self.data1["level"],
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=5,
        )
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save()
        self.assertFalse(EligibilityService.can_attempt_exam(self.profile, onboarding_exam))

    # ── can_purchase_level ──

    def test_can_purchase_level1(self):
        self.assertTrue(EligibilityService.can_purchase_level(self.profile, self.data1["level"]))

    def test_cannot_purchase_level2_without_clearing(self):
        self.assertFalse(EligibilityService.can_purchase_level(self.profile, self.data2["level"]))

    def test_can_purchase_level2_after_clearing(self):
        self.factory.pass_level(self.profile, self.data1["level"])
        self.assertTrue(EligibilityService.can_purchase_level(self.profile, self.data2["level"]))

    # ── get_next_action ──

    def test_next_action_new_student_onboarding(self):
        onboarding_exam = self.factory.create_exam(
            self.data1["level"],
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=5,
        )
        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.TAKE_ONBOARDING_EXAM)
        self.assertEqual(result["level"]["order"], 1)
        self.assertEqual(result["exam_id"], onboarding_exam.id)

    def test_next_action_onboarding_advances_to_current_level_exam(self):
        self.factory.create_exam(
            self.data1["level"],
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=5,
        )
        onboarding_exam_level2 = self.factory.create_exam(
            self.data2["level"],
            exam_type=Exam.ExamType.ONBOARDING,
            num_questions=5,
        )
        self.profile.current_level = self.data2["level"]
        self.profile.highest_cleared_level = self.data1["level"]
        self.profile.save(update_fields=["current_level", "highest_cleared_level"])

        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.TAKE_ONBOARDING_EXAM)
        self.assertEqual(result["level"]["order"], 2)
        self.assertEqual(result["exam_id"], onboarding_exam_level2.id)

    def test_next_action_after_onboarding_no_purchase(self):
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save()
        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.PURCHASE_LEVEL)
        self.assertEqual(result["level"]["order"], 1)

    def test_next_action_after_pass_level1(self):
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save()
        self.factory.pass_level(self.profile, self.data1["level"])
        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.PURCHASE_LEVEL)
        self.assertEqual(result["level"]["order"], 2)

    def test_next_action_in_progress(self):
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save()
        self.factory.create_purchase(self.profile, self.data1["level"])
        LevelProgress.objects.create(
            student=self.profile,
            level=self.data1["level"],
            status=LevelProgress.Status.IN_PROGRESS,
        )
        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.COMPLETE_COURSES)

    def test_next_action_syllabus_complete(self):
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save()
        self.factory.create_purchase(self.profile, self.data1["level"])
        for s in self.data1["sessions"]:
            self.factory.complete_session(self.profile, s)
        LevelProgress.objects.create(
            student=self.profile,
            level=self.data1["level"],
            status=LevelProgress.Status.SYLLABUS_COMPLETE,
        )
        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.TAKE_FINAL_EXAM)

    def test_next_action_all_cleared(self):
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save()
        self.factory.pass_level(self.profile, self.data1["level"])
        self.factory.pass_level(self.profile, self.data2["level"])
        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.ALL_COMPLETE)

    def test_next_action_no_levels(self):
        """When no active levels exist."""
        Level.objects.all().delete()
        _, fresh_profile = self.factory.create_student(email="fresh@test.com")
        result = EligibilityService.get_next_action(fresh_profile)
        self.assertEqual(result["action"], NextAction.NO_LEVELS)

    def test_next_action_redo_level_after_exhausted_attempts(self):
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save()
        self.factory.create_purchase(self.profile, self.data1["level"])
        LevelProgress.objects.create(
            student=self.profile,
            level=self.data1["level"],
            status=LevelProgress.Status.EXAM_FAILED,
            final_exam_attempts_used=self.data1["level"].max_final_exam_attempts,
        )
        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.REDO_LEVEL)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailFunctionTests(TestCase):
    def test_send_welcome_email(self):
        from django.core import mail

        from core.emails import EmailService

        EmailService.send_welcome("user@test.com", "Test User")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Welcome", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["user@test.com"])

    def test_send_purchase_confirmation(self):
        from django.core import mail
        from django.utils import timezone

        from core.emails import EmailService

        EmailService.send_purchase_confirmation(
            "user@test.com",
            "Test User",
            "Foundation",
            "999.00",
            timezone.now(),
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Purchase Confirmed", mail.outbox[0].subject)
        self.assertIn("Foundation", mail.outbox[0].body)

    def test_send_exam_result_passed(self):
        from django.core import mail

        from core.emails import EmailService

        EmailService.send_exam_result(
            "user@test.com",
            "Test User",
            "Final Exam",
            "35",
            40,
            True,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("PASSED", mail.outbox[0].subject)
        self.assertIn("Congratulations", mail.outbox[0].body)

    def test_send_exam_result_failed(self):
        from django.core import mail

        from core.emails import EmailService

        EmailService.send_exam_result(
            "user@test.com",
            "Test User",
            "Final Exam",
            "10",
            40,
            False,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("NOT PASSED", mail.outbox[0].subject)
        self.assertIn("try again", mail.outbox[0].body)

    def test_send_doubt_reply_notification(self):
        from django.core import mail

        from core.emails import EmailService

        EmailService.send_doubt_reply(
            "user@test.com",
            "Test User",
            "How to solve Q5?",
            "Prof. Smith",
            "The key is to apply Newton's second law...",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("New Reply", mail.outbox[0].subject)
        self.assertIn("Newton", mail.outbox[0].body)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailTaskTests(TestCase):
    def test_welcome_email_task(self):
        from django.core import mail

        from core.tasks import send_welcome_email_task

        send_welcome_email_task("user@test.com", "Test User")
        self.assertEqual(len(mail.outbox), 1)

    def test_purchase_confirmation_task(self):
        from django.core import mail
        from django.utils import timezone

        from core.tasks import send_purchase_confirmation_task

        send_purchase_confirmation_task(
            "user@test.com",
            "Test User",
            "Foundation",
            "999.00",
            timezone.now().isoformat(),
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_exam_result_task(self):
        from django.core import mail

        from core.tasks import send_exam_result_task

        send_exam_result_task(
            "user@test.com",
            "Test User",
            "Final Exam",
            "35",
            40,
            True,
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_doubt_reply_task(self):
        from django.core import mail

        from core.tasks import send_doubt_reply_task

        send_doubt_reply_task(
            "user@test.com",
            "Test User",
            "My Doubt",
            "Admin",
            "Here is the answer...",
        )
        self.assertEqual(len(mail.outbox), 1)
