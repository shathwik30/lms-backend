"""
Additional tests for core/services/eligibility.py coverage gaps.

Covers:
  - is_course_complete with zero sessions -> True
  - is_week_complete with zero sessions -> True
  - can_attempt_exam with unknown exam type -> False
  - is_session_accessible: prior weeks incomplete -> False
  - is_session_accessible: prior sessions in same week incomplete -> False
  - is_session_accessible: first session in first week -> True (no priors)
  - is_session_accessible: all priors complete -> True
  - get_next_action: no levels after cleared -> ALL_COMPLETE
  - get_next_action: onboarding not attempted + no highest_cleared -> NO_LEVELS when empty
"""

from django.test import TestCase

from apps.courses.models import Session
from apps.exams.models import Exam
from core.constants import NextAction
from core.services.eligibility import EligibilityService
from core.test_utils import TestFactory


class IsCompleteZeroSessionsTests(TestCase):
    """Test is_course_complete and is_week_complete with zero active sessions."""

    def setUp(self):
        self.factory = TestFactory()
        _, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)
        self.week = self.factory.create_week(self.course, order=1)

    def test_is_course_complete_zero_sessions(self):
        """A course with zero active sessions is considered complete."""
        self.assertTrue(EligibilityService.is_course_complete(self.profile, self.course))

    def test_is_week_complete_zero_sessions(self):
        """A week with zero active sessions is considered complete."""
        self.assertTrue(EligibilityService.is_week_complete(self.profile, self.week))

    def test_is_course_complete_with_inactive_sessions_only(self):
        """Inactive sessions should not count -- course is still 'complete'."""
        Session.objects.create(
            week=self.week,
            title="Inactive Session",
            video_url="https://example.com/vid.mp4",
            duration_seconds=100,
            order=1,
            session_type=Session.SessionType.VIDEO,
            is_active=False,
        )
        self.assertTrue(EligibilityService.is_course_complete(self.profile, self.course))

    def test_is_week_complete_with_inactive_sessions_only(self):
        """Inactive sessions should not count -- week is still 'complete'."""
        Session.objects.create(
            week=self.week,
            title="Inactive Session",
            video_url="https://example.com/vid.mp4",
            duration_seconds=100,
            order=1,
            session_type=Session.SessionType.VIDEO,
            is_active=False,
        )
        self.assertTrue(EligibilityService.is_week_complete(self.profile, self.week))


class CanAttemptExamUnknownTypeTests(TestCase):
    """Test can_attempt_exam returns False for an unknown exam type."""

    def setUp(self):
        self.factory = TestFactory()
        _, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)

    def test_unknown_exam_type_returns_false(self):
        """If exam_type is not ONBOARDING, LEVEL_FINAL, or WEEKLY, return False."""
        exam = Exam.objects.create(
            level=self.level,
            exam_type="unknown_type",
            title="Mystery Exam",
            duration_minutes=30,
            total_marks=20,
            passing_percentage=50,
            num_questions=5,
        )
        self.assertFalse(EligibilityService.can_attempt_exam(self.profile, exam))


class IsSessionAccessibleTests(TestCase):
    """
    Test is_session_accessible for various scenarios:
      - First session in first week (no priors) -> True
      - All priors complete -> True
      - Prior weeks incomplete -> False
      - Prior sessions in same week incomplete -> False
    """

    def setUp(self):
        self.factory = TestFactory()
        _, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)

    def test_first_session_first_week_accessible(self):
        """First session in the first week has no priors -- always accessible."""
        week1 = self.factory.create_week(self.course, order=1)
        session1 = self.factory.create_session(week1, order=1)
        self.assertTrue(EligibilityService.is_session_accessible(self.profile, session1))

    def test_all_priors_complete_accessible(self):
        """When all prior weeks and sessions are complete, session is accessible."""
        week1 = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week1, order=1)
        s2 = self.factory.create_session(week1, order=2)

        week2 = self.factory.create_week(self.course, order=2)
        s3 = self.factory.create_session(week2, order=1)

        # Complete all prior sessions
        self.factory.complete_session(self.profile, s1)
        self.factory.complete_session(self.profile, s2)

        self.assertTrue(EligibilityService.is_session_accessible(self.profile, s3))

    def test_prior_weeks_incomplete_blocks_access(self):
        """If prior weeks have incomplete sessions, access is blocked."""
        week1 = self.factory.create_week(self.course, order=1)
        self.factory.create_session(week1, order=1)
        self.factory.create_session(week1, order=2)

        week2 = self.factory.create_week(self.course, order=2)
        s3 = self.factory.create_session(week2, order=1)

        # week1 sessions not completed
        self.assertFalse(EligibilityService.is_session_accessible(self.profile, s3))

    def test_prior_weeks_partially_complete_blocks_access(self):
        """If only some sessions in a prior week are complete, access is blocked."""
        week1 = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week1, order=1)
        self.factory.create_session(week1, order=2)  # s2 not completed

        week2 = self.factory.create_week(self.course, order=2)
        s3 = self.factory.create_session(week2, order=1)

        self.factory.complete_session(self.profile, s1)
        # s2 not completed
        self.assertFalse(EligibilityService.is_session_accessible(self.profile, s3))

    def test_prior_sessions_same_week_incomplete_blocks_access(self):
        """If prior sessions in the same week are incomplete, access is blocked."""
        week1 = self.factory.create_week(self.course, order=1)
        self.factory.create_session(week1, order=1)  # s1 not completed
        s2 = self.factory.create_session(week1, order=2)

        self.assertFalse(EligibilityService.is_session_accessible(self.profile, s2))

    def test_prior_session_same_week_complete_accessible(self):
        """Second session accessible when first session in same week is complete."""
        week1 = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week1, order=1)
        s2 = self.factory.create_session(week1, order=2)

        self.factory.complete_session(self.profile, s1)
        self.assertTrue(EligibilityService.is_session_accessible(self.profile, s2))

    def test_prior_week_with_zero_sessions_does_not_block(self):
        """A prior week with no active sessions should not block access."""
        # week1 has no sessions (empty week)
        self.factory.create_week(self.course, order=1)

        week2 = self.factory.create_week(self.course, order=2)
        s1 = self.factory.create_session(week2, order=1)

        self.assertTrue(EligibilityService.is_session_accessible(self.profile, s1))

    def test_multiple_prior_weeks_all_complete(self):
        """Access granted when sessions in all prior weeks are complete."""
        week1 = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week1, order=1)

        week2 = self.factory.create_week(self.course, order=2)
        s2 = self.factory.create_session(week2, order=1)

        week3 = self.factory.create_week(self.course, order=3)
        s3 = self.factory.create_session(week3, order=1)

        self.factory.complete_session(self.profile, s1)
        self.factory.complete_session(self.profile, s2)

        self.assertTrue(EligibilityService.is_session_accessible(self.profile, s3))

    def test_multiple_prior_weeks_one_incomplete_blocks(self):
        """If any prior week has incomplete sessions, access is blocked."""
        week1 = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week1, order=1)

        week2 = self.factory.create_week(self.course, order=2)
        self.factory.create_session(week2, order=1)  # not completed

        week3 = self.factory.create_week(self.course, order=3)
        s3 = self.factory.create_session(week3, order=1)

        self.factory.complete_session(self.profile, s1)
        # week2 session not completed

        self.assertFalse(EligibilityService.is_session_accessible(self.profile, s3))


class GetNextActionGapTests(TestCase):
    """
    Test get_next_action edge cases not covered by existing tests:
      - No levels exist after all cleared -> ALL_COMPLETE
      - Onboarding done, no highest_cleared_level, no levels -> NO_LEVELS
    """

    def setUp(self):
        self.factory = TestFactory()
        _, self.profile = self.factory.create_student()

    def test_all_complete_no_next_level_after_cleared(self):
        """
        After clearing the only level, no more levels exist.
        Should return ALL_COMPLETE.
        """
        level1 = self.factory.create_level(order=1)
        self.profile.onboarding_exam_attempted = True
        self.profile.save()
        self.factory.pass_level(self.profile, level1)

        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.ALL_COMPLETE)
        self.assertIsNone(result["level"])

    def test_no_levels_after_onboarding_no_cleared(self):
        """
        After onboarding, no highest_cleared_level and no active levels exist.
        Should return NO_LEVELS.
        """
        self.profile.onboarding_exam_attempted = True
        self.profile.save()
        # No levels created at all
        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.NO_LEVELS)
        self.assertIsNone(result["level"])

    def test_no_levels_before_onboarding(self):
        """
        New student, no onboarding done, but no levels exist.
        Should return NO_LEVELS.
        """
        # No levels created
        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.NO_LEVELS)
        self.assertIsNone(result["level"])

    def test_all_complete_with_multiple_levels(self):
        """
        After clearing all 3 levels, returns ALL_COMPLETE.
        """
        level1 = self.factory.create_level(order=1)
        level2 = self.factory.create_level(order=2)
        level3 = self.factory.create_level(order=3)
        self.profile.onboarding_exam_attempted = True
        self.profile.save()
        self.factory.pass_level(self.profile, level1)
        self.factory.pass_level(self.profile, level2)
        self.factory.pass_level(self.profile, level3)

        result = EligibilityService.get_next_action(self.profile)
        self.assertEqual(result["action"], NextAction.ALL_COMPLETE)
        self.assertIsNone(result["level"])
        self.assertEqual(result["message"], "Congratulations! You have cleared all levels.")
