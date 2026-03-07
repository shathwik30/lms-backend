from unittest.mock import patch

from django.test import TestCase

from apps.courses.services import CourseAccessService
from apps.progress.models import SessionProgress
from core.test_utils import TestFactory


class HasCourseAccessTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)

    def test_returns_false_when_course_does_not_exist(self):
        result = CourseAccessService.has_course_access(self.profile, 99999)
        self.assertFalse(result)

    def test_returns_false_when_course_inactive(self):
        self.course.is_active = False
        self.course.save()
        result = CourseAccessService.has_course_access(self.profile, self.course.pk)
        self.assertFalse(result)

    def test_returns_false_without_purchase(self):
        result = CourseAccessService.has_course_access(self.profile, self.course.pk)
        self.assertFalse(result)

    def test_returns_true_with_active_purchase(self):
        self.factory.create_purchase(self.profile, self.level)
        result = CourseAccessService.has_course_access(self.profile, self.course.pk)
        self.assertTrue(result)

    def test_returns_false_with_expired_purchase(self):
        self.factory.create_expired_purchase(self.profile, self.level)
        result = CourseAccessService.has_course_access(self.profile, self.course.pk)
        self.assertFalse(result)


class HasLevelAccessTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)

    def test_returns_false_without_purchase(self):
        result = CourseAccessService.has_level_access(self.profile, self.level)
        self.assertFalse(result)

    def test_returns_true_with_active_purchase(self):
        self.factory.create_purchase(self.profile, self.level)
        result = CourseAccessService.has_level_access(self.profile, self.level)
        self.assertTrue(result)

    def test_returns_false_with_expired_purchase(self):
        self.factory.create_expired_purchase(self.profile, self.level)
        result = CourseAccessService.has_level_access(self.profile, self.level)
        self.assertFalse(result)


class IsSessionAccessibleTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)
        self.week = self.factory.create_week(self.course, order=1)

    @patch("apps.courses.services.EligibilityService.is_session_accessible")
    def test_delegates_to_eligibility_service(self, mock_eligible):
        mock_eligible.return_value = True
        session = self.factory.create_session(self.week, order=1)
        result = CourseAccessService.is_session_accessible(self.profile, session)
        self.assertTrue(result)
        mock_eligible.assert_called_once_with(self.profile, session)

    @patch("apps.courses.services.EligibilityService.is_session_accessible")
    def test_returns_false_when_not_accessible(self, mock_eligible):
        mock_eligible.return_value = False
        session = self.factory.create_session(self.week, order=1)
        result = CourseAccessService.is_session_accessible(self.profile, session)
        self.assertFalse(result)


class GetNextSessionTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)

    def test_no_active_sessions_returns_none(self):
        """Course with no weeks/sessions returns None."""
        result = CourseAccessService.get_next_session(self.profile, self.course)
        self.assertIsNone(result)

    def test_no_active_sessions_inactive_week_returns_none(self):
        """Sessions exist but week is inactive -> returns None."""
        week = self.factory.create_week(self.course, order=1)
        self.factory.create_session(week, order=1)
        week.is_active = False
        week.save()
        result = CourseAccessService.get_next_session(self.profile, self.course)
        self.assertIsNone(result)

    def test_no_active_sessions_inactive_session_returns_none(self):
        """Week is active but all sessions are inactive -> returns None."""
        week = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week, order=1)
        s1.is_active = False
        s1.save()
        result = CourseAccessService.get_next_session(self.profile, self.course)
        self.assertIsNone(result)

    def test_all_sessions_completed_returns_none(self):
        """When all sessions are completed, returns None."""
        week = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week, order=1)
        s2 = self.factory.create_session(week, order=2)
        self.factory.complete_session(self.profile, s1)
        self.factory.complete_session(self.profile, s2)
        result = CourseAccessService.get_next_session(self.profile, self.course)
        self.assertIsNone(result)

    def test_single_incomplete_session_returns_it(self):
        """Single incomplete session is returned."""
        week = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week, order=1)
        result = CourseAccessService.get_next_session(self.profile, self.course)
        self.assertEqual(result.pk, s1.pk)

    def test_mix_of_completed_and_incomplete_returns_first_incomplete(self):
        """With some completed, returns the first incomplete session."""
        week = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week, order=1)
        s2 = self.factory.create_session(week, order=2)
        self.factory.create_session(week, order=3)
        # Complete s1 only
        self.factory.complete_session(self.profile, s1)
        result = CourseAccessService.get_next_session(self.profile, self.course)
        self.assertEqual(result.pk, s2.pk)

    def test_multiple_weeks_respects_week_order_then_session_order(self):
        """Sessions are ordered by week order first, then session order."""
        week1 = self.factory.create_week(self.course, order=1)
        week2 = self.factory.create_week(self.course, order=2)
        s1_w1 = self.factory.create_session(week1, order=1)
        s2_w1 = self.factory.create_session(week1, order=2)
        s1_w2 = self.factory.create_session(week2, order=1)
        # Complete all of week 1
        self.factory.complete_session(self.profile, s1_w1)
        self.factory.complete_session(self.profile, s2_w1)
        # Next should be first session in week 2
        result = CourseAccessService.get_next_session(self.profile, self.course)
        self.assertEqual(result.pk, s1_w2.pk)

    def test_first_session_of_first_week_when_nothing_completed(self):
        """When nothing is completed, returns the very first session."""
        week1 = self.factory.create_week(self.course, order=1)
        week2 = self.factory.create_week(self.course, order=2)
        s1_w1 = self.factory.create_session(week1, order=1)
        self.factory.create_session(week1, order=2)
        self.factory.create_session(week2, order=1)
        result = CourseAccessService.get_next_session(self.profile, self.course)
        self.assertEqual(result.pk, s1_w1.pk)

    def test_skips_completed_middle_session(self):
        """If session 2 of 3 is completed but session 1 is not, returns session 1."""
        week = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week, order=1)
        s2 = self.factory.create_session(week, order=2)
        self.factory.create_session(week, order=3)
        # Only complete s2 (middle)
        self.factory.complete_session(self.profile, s2)
        result = CourseAccessService.get_next_session(self.profile, self.course)
        self.assertEqual(result.pk, s1.pk)

    def test_different_student_progress_isolated(self):
        """Student B's completions do not affect Student A's next session."""
        _, profile_b = self.factory.create_student(email="b@test.com")
        week = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week, order=1)
        self.factory.create_session(week, order=2)
        # Student B completes s1
        self.factory.complete_session(profile_b, s1)
        # Student A's next session should still be s1
        result = CourseAccessService.get_next_session(self.profile, self.course)
        self.assertEqual(result.pk, s1.pk)

    def test_progress_exists_but_not_completed(self):
        """SessionProgress with is_completed=False should not count."""
        week = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week, order=1)
        self.factory.create_session(week, order=2)
        # Create progress for s1 but not completed
        SessionProgress.objects.create(
            student=self.profile,
            session=s1,
            watched_seconds=100,
            is_completed=False,
        )
        result = CourseAccessService.get_next_session(self.profile, self.course)
        self.assertEqual(result.pk, s1.pk)
