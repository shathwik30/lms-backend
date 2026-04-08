from django.test import TestCase
from django.utils import timezone

from apps.courses.models import Session
from apps.exams.models import ExamAttempt
from apps.progress.models import CourseProgress, LevelProgress, SessionProgress
from apps.progress.services import ProgressService
from core.constants import ErrorMessage
from core.test_utils import TestFactory


class UpdateSessionProgressTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)
        self.week = self.factory.create_week(self.course, order=1)

    def test_non_video_session_returns_error(self):
        """update_session_progress on a RESOURCE session returns an error."""
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.RESOURCE)
        progress, error = ProgressService.update_session_progress(self.profile, session.pk, watched_seconds=100)
        self.assertIsNone(progress)
        self.assertEqual(error, ErrorMessage.SESSION_NOT_FOUND)

    def test_practice_exam_session_returns_error(self):
        """update_session_progress on a PRACTICE_EXAM session returns an error."""
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.PRACTICE_EXAM)
        progress, error = ProgressService.update_session_progress(self.profile, session.pk, watched_seconds=100)
        self.assertIsNone(progress)
        self.assertEqual(error, ErrorMessage.SESSION_NOT_FOUND)

    def test_nonexistent_session_returns_error(self):
        progress, error = ProgressService.update_session_progress(self.profile, 99999, watched_seconds=100)
        self.assertIsNone(progress)
        self.assertEqual(error, ErrorMessage.SESSION_NOT_FOUND)

    def test_video_session_succeeds(self):
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.VIDEO)
        progress, error = ProgressService.update_session_progress(self.profile, session.pk, watched_seconds=100)
        self.assertIsNotNone(progress)
        self.assertIsNone(error)
        self.assertEqual(progress.watched_seconds, 100)

    def test_video_session_auto_completes_at_threshold_without_feedback(self):
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.VIDEO)
        watched_seconds = int(session.duration_seconds * 0.95)
        progress, error = ProgressService.update_session_progress(self.profile, session.pk, watched_seconds)
        self.assertIsNotNone(progress)
        self.assertIsNone(error)
        self.assertTrue(progress.is_completed)
        self.assertIsNotNone(progress.completed_at)

    def test_video_session_below_threshold_does_not_complete(self):
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.VIDEO)
        watched_seconds = int(session.duration_seconds * 0.89)
        progress, error = ProgressService.update_session_progress(self.profile, session.pk, watched_seconds)
        self.assertIsNotNone(progress)
        self.assertIsNone(error)
        self.assertFalse(progress.is_completed)
        self.assertIsNone(progress.completed_at)


class CompleteResourceSessionTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)
        self.week = self.factory.create_week(self.course, order=1)

    def test_complete_resource_session_marks_completed(self):
        """Completing a RESOURCE session marks it as completed with timestamp."""
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.RESOURCE)
        progress, error = ProgressService.complete_resource_session(self.profile, session.pk)
        self.assertIsNotNone(progress)
        self.assertIsNone(error)
        self.assertTrue(progress.is_completed)
        self.assertIsNotNone(progress.completed_at)

    def test_non_resource_session_returns_error(self):
        """Calling complete_resource_session on a VIDEO session returns error."""
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.VIDEO)
        progress, error = ProgressService.complete_resource_session(self.profile, session.pk)
        self.assertIsNone(progress)
        self.assertEqual(error, ErrorMessage.SESSION_NOT_FOUND)

    def test_practice_exam_session_returns_error(self):
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.PRACTICE_EXAM)
        progress, error = ProgressService.complete_resource_session(self.profile, session.pk)
        self.assertIsNone(progress)
        self.assertEqual(error, ErrorMessage.SESSION_NOT_FOUND)

    def test_nonexistent_session_returns_error(self):
        progress, error = ProgressService.complete_resource_session(self.profile, 99999)
        self.assertIsNone(progress)
        self.assertEqual(error, ErrorMessage.SESSION_NOT_FOUND)

    def test_already_completed_no_duplicate(self):
        """Completing a resource session twice does not create a duplicate or error."""
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.RESOURCE)
        progress1, _ = ProgressService.complete_resource_session(self.profile, session.pk)
        first_completed_at = progress1.completed_at

        progress2, error2 = ProgressService.complete_resource_session(self.profile, session.pk)
        self.assertIsNotNone(progress2)
        self.assertIsNone(error2)
        self.assertTrue(progress2.is_completed)
        # completed_at should not change on second call
        self.assertEqual(progress2.completed_at, first_completed_at)
        # Only one SessionProgress record exists
        self.assertEqual(
            SessionProgress.objects.filter(student=self.profile, session=session).count(),
            1,
        )

    def test_triggers_cascading_completion(self):
        """Completing the only resource session in a course triggers cascading."""
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.RESOURCE)
        LevelProgress.objects.create(
            student=self.profile,
            level=self.level,
            status=LevelProgress.Status.IN_PROGRESS,
        )
        ProgressService.complete_resource_session(self.profile, session.pk)
        # Course should be marked complete since it's the only session
        cp = CourseProgress.objects.filter(student=self.profile, course=self.course).first()
        self.assertIsNotNone(cp)
        self.assertEqual(cp.status, CourseProgress.Status.COMPLETED)


class CompleteExamSessionTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)
        self.week = self.factory.create_week(self.course, order=1)

    def test_pass_exam_marks_completed(self):
        """Passing an exam session marks it completed with timestamp."""
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.PRACTICE_EXAM)
        progress, error = ProgressService.complete_exam_session(self.profile, session, is_passed=True)
        self.assertIsNotNone(progress)
        self.assertIsNone(error)
        self.assertTrue(progress.is_completed)
        self.assertTrue(progress.is_exam_passed)
        self.assertIsNotNone(progress.completed_at)

    def test_pass_exam_triggers_cascading_completion(self):
        """Passing the only exam session triggers cascading course completion."""
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.PRACTICE_EXAM)
        LevelProgress.objects.create(
            student=self.profile,
            level=self.level,
            status=LevelProgress.Status.IN_PROGRESS,
        )
        ProgressService.complete_exam_session(self.profile, session, is_passed=True)
        cp = CourseProgress.objects.filter(student=self.profile, course=self.course).first()
        self.assertIsNotNone(cp)
        self.assertEqual(cp.status, CourseProgress.Status.COMPLETED)

    def test_fail_non_proctored_exam_no_week_reset(self):
        """Failing a non-proctored exam does not reset week progress."""
        s1 = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.VIDEO)
        s2 = self.factory.create_session(self.week, order=2, session_type=Session.SessionType.PRACTICE_EXAM)
        # Complete s1 first
        self.factory.complete_session(self.profile, s1)
        # Fail s2 (practice exam, not proctored)
        ProgressService.complete_exam_session(self.profile, s2, is_passed=False)
        # s1 progress should still exist
        self.assertTrue(SessionProgress.objects.filter(student=self.profile, session=s1, is_completed=True).exists())

    def test_fail_proctored_exam_resets_week_progress(self):
        """Failing a PROCTORED_EXAM resets all week progress."""
        s1 = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.VIDEO)
        s2 = self.factory.create_session(self.week, order=2, session_type=Session.SessionType.PROCTORED_EXAM)
        # Complete s1
        self.factory.complete_session(self.profile, s1)
        self.assertTrue(SessionProgress.objects.filter(student=self.profile, session=s1).exists())
        # Fail s2 (proctored exam)
        ProgressService.complete_exam_session(self.profile, s2, is_passed=False)
        # s1 progress should be deleted (week reset)
        self.assertFalse(SessionProgress.objects.filter(student=self.profile, session=s1).exists())
        # s2 progress should also be deleted
        self.assertFalse(SessionProgress.objects.filter(student=self.profile, session=s2).exists())

    def test_fail_exam_sets_is_exam_passed_false(self):
        """Failing an exam sets is_exam_is_passed=False but not is_completed."""
        session = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.PRACTICE_EXAM)
        progress, error = ProgressService.complete_exam_session(self.profile, session, is_passed=False)
        self.assertIsNotNone(progress)
        self.assertIsNone(error)
        self.assertFalse(progress.is_exam_passed)
        self.assertFalse(progress.is_completed)
        self.assertIsNone(progress.completed_at)


class CheckCascadingCompletionTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)
        self.week = self.factory.create_week(self.course, order=1)

    def test_week_not_complete_early_return(self):
        """When week is not complete, cascading does nothing."""
        s1 = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.RESOURCE)
        self.factory.create_session(self.week, order=2, session_type=Session.SessionType.RESOURCE)
        # Complete only s1; week has 2 sessions so it's not complete
        ProgressService.complete_resource_session(self.profile, s1.pk)
        # No CourseProgress should be created
        self.assertFalse(CourseProgress.objects.filter(student=self.profile, course=self.course).exists())

    def test_week_complete_but_course_not_complete(self):
        """Week 1 complete but week 2 still has sessions -> no course completion."""
        week2 = self.factory.create_week(self.course, order=2)
        s1_w1 = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.RESOURCE)
        self.factory.create_session(week2, order=1, session_type=Session.SessionType.RESOURCE)
        # Complete only week 1
        ProgressService.complete_resource_session(self.profile, s1_w1.pk)
        # No CourseProgress completion
        cp = CourseProgress.objects.filter(student=self.profile, course=self.course).first()
        self.assertIsNone(cp)

    def test_full_cascading_to_syllabus_complete(self):
        """All sessions complete -> course complete -> syllabus complete."""
        s1 = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.RESOURCE)
        LevelProgress.objects.create(
            student=self.profile,
            level=self.level,
            status=LevelProgress.Status.IN_PROGRESS,
        )
        ProgressService.complete_resource_session(self.profile, s1.pk)
        # Course should be completed
        cp = CourseProgress.objects.get(student=self.profile, course=self.course)
        self.assertEqual(cp.status, CourseProgress.Status.COMPLETED)
        # Level should be syllabus complete
        lp = LevelProgress.objects.get(student=self.profile, level=self.level)
        self.assertEqual(lp.status, LevelProgress.Status.SYLLABUS_COMPLETE)

    def test_cascading_updates_exam_failed_to_syllabus_complete(self):
        """LevelProgress with EXAM_FAILED status also gets promoted."""
        s1 = self.factory.create_session(self.week, order=1, session_type=Session.SessionType.RESOURCE)
        LevelProgress.objects.create(
            student=self.profile,
            level=self.level,
            status=LevelProgress.Status.EXAM_FAILED,
        )
        ProgressService.complete_resource_session(self.profile, s1.pk)
        lp = LevelProgress.objects.get(student=self.profile, level=self.level)
        self.assertEqual(lp.status, LevelProgress.Status.SYLLABUS_COMPLETE)


class ResetWeekProgressTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)
        self.week = self.factory.create_week(self.course, order=1)

    def test_deletes_all_session_progress_for_week(self):
        s1 = self.factory.create_session(self.week, order=1)
        s2 = self.factory.create_session(self.week, order=2)
        self.factory.complete_session(self.profile, s1)
        self.factory.complete_session(self.profile, s2)
        self.assertEqual(SessionProgress.objects.filter(student=self.profile).count(), 2)
        ProgressService.reset_week_progress(self.profile, self.week)
        self.assertEqual(SessionProgress.objects.filter(student=self.profile).count(), 0)

    def test_does_not_affect_other_weeks(self):
        week2 = self.factory.create_week(self.course, order=2)
        s1_w1 = self.factory.create_session(self.week, order=1)
        s1_w2 = self.factory.create_session(week2, order=1)
        self.factory.complete_session(self.profile, s1_w1)
        self.factory.complete_session(self.profile, s1_w2)
        ProgressService.reset_week_progress(self.profile, self.week)
        # Week 2 progress should remain
        self.assertTrue(SessionProgress.objects.filter(student=self.profile, session=s1_w2).exists())
        # Week 1 progress should be gone
        self.assertFalse(SessionProgress.objects.filter(student=self.profile, session=s1_w1).exists())

    def test_does_not_affect_other_students(self):
        _, profile_b = self.factory.create_student(email="b@test.com")
        s1 = self.factory.create_session(self.week, order=1)
        self.factory.complete_session(self.profile, s1)
        self.factory.complete_session(profile_b, s1)
        ProgressService.reset_week_progress(self.profile, self.week)
        # Profile B's progress should remain
        self.assertTrue(SessionProgress.objects.filter(student=profile_b, session=s1).exists())

    def test_skips_inactive_sessions(self):
        """Only deletes progress for active sessions."""
        s1 = self.factory.create_session(self.week, order=1)
        s2 = self.factory.create_session(self.week, order=2)
        self.factory.complete_session(self.profile, s1)
        self.factory.complete_session(self.profile, s2)
        # Make s2 inactive
        s2.is_active = False
        s2.save()
        ProgressService.reset_week_progress(self.profile, self.week)
        # s1 progress deleted (active session), s2 progress remains (inactive session)
        self.assertFalse(SessionProgress.objects.filter(student=self.profile, session=s1).exists())
        self.assertTrue(SessionProgress.objects.filter(student=self.profile, session=s2).exists())


class ResetLevelProgressTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)
        self.week = self.factory.create_week(self.course, order=1)

    def test_deletes_all_session_progress(self):
        s1 = self.factory.create_session(self.week, order=1)
        s2 = self.factory.create_session(self.week, order=2)
        self.factory.complete_session(self.profile, s1)
        self.factory.complete_session(self.profile, s2)
        ProgressService.reset_level_progress(self.profile, self.level)
        self.assertEqual(SessionProgress.objects.filter(student=self.profile).count(), 0)

    def test_deletes_course_progress(self):
        CourseProgress.objects.create(
            student=self.profile,
            course=self.course,
            status=CourseProgress.Status.COMPLETED,
        )
        ProgressService.reset_level_progress(self.profile, self.level)
        self.assertFalse(CourseProgress.objects.filter(student=self.profile, course=self.course).exists())

    def test_resets_level_progress_status_and_attempts(self):
        LevelProgress.objects.create(
            student=self.profile,
            level=self.level,
            status=LevelProgress.Status.EXAM_FAILED,
            completed_at=timezone.now(),
            final_exam_attempts_used=3,
        )
        ProgressService.reset_level_progress(self.profile, self.level)
        lp = LevelProgress.objects.get(student=self.profile, level=self.level)
        self.assertEqual(lp.status, LevelProgress.Status.IN_PROGRESS)
        self.assertIsNone(lp.completed_at)
        self.assertEqual(lp.final_exam_attempts_used, 0)

    def test_does_not_affect_other_levels(self):
        level2 = self.factory.create_level(order=2)
        course2 = self.factory.create_course(level2)
        week2 = self.factory.create_week(course2, order=1)
        s_other = self.factory.create_session(week2, order=1)
        self.factory.complete_session(self.profile, s_other)
        CourseProgress.objects.create(
            student=self.profile,
            course=course2,
            status=CourseProgress.Status.COMPLETED,
        )
        ProgressService.reset_level_progress(self.profile, self.level)
        # Other level's data should remain
        self.assertTrue(SessionProgress.objects.filter(student=self.profile, session=s_other).exists())
        self.assertTrue(CourseProgress.objects.filter(student=self.profile, course=course2).exists())


class GetCourseProgressTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)

    def test_course_with_no_sessions(self):
        """Course with no weeks/sessions returns empty weeks list."""
        result = ProgressService.get_course_progress(self.profile, self.course)
        self.assertEqual(result["course_id"], self.course.id)
        self.assertEqual(result["course_title"], self.course.title)
        self.assertEqual(result["status"], CourseProgress.Status.NOT_STARTED)
        self.assertEqual(result["weeks"], [])

    def test_multiple_weeks_with_mixed_completion(self):
        """Aggregates per-week stats correctly."""
        week1 = self.factory.create_week(self.course, order=1, name="Week 1")
        week2 = self.factory.create_week(self.course, order=2, name="Week 2")
        s1_w1 = self.factory.create_session(week1, order=1)
        s2_w1 = self.factory.create_session(week1, order=2)
        s1_w2 = self.factory.create_session(week2, order=1)
        self.factory.create_session(week2, order=2)
        # Complete all of week 1
        self.factory.complete_session(self.profile, s1_w1)
        self.factory.complete_session(self.profile, s2_w1)
        # Complete only one session in week 2
        self.factory.complete_session(self.profile, s1_w2)

        result = ProgressService.get_course_progress(self.profile, self.course)
        weeks = result["weeks"]
        self.assertEqual(len(weeks), 2)

        # Week 1 should be complete
        self.assertEqual(weeks[0]["week_name"], "Week 1")
        self.assertEqual(weeks[0]["total_sessions"], 2)
        self.assertEqual(weeks[0]["completed_sessions"], 2)
        self.assertTrue(weeks[0]["is_complete"])

        # Week 2 should be incomplete
        self.assertEqual(weeks[1]["week_name"], "Week 2")
        self.assertEqual(weeks[1]["total_sessions"], 2)
        self.assertEqual(weeks[1]["completed_sessions"], 1)
        self.assertFalse(weeks[1]["is_complete"])

    def test_with_course_progress_record(self):
        """When CourseProgress exists, its status is returned."""
        CourseProgress.objects.create(
            student=self.profile,
            course=self.course,
            status=CourseProgress.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        result = ProgressService.get_course_progress(self.profile, self.course)
        self.assertEqual(result["status"], CourseProgress.Status.COMPLETED)

    def test_without_course_progress_record(self):
        """When no CourseProgress exists, status is NOT_STARTED."""
        result = ProgressService.get_course_progress(self.profile, self.course)
        self.assertEqual(result["status"], CourseProgress.Status.NOT_STARTED)

    def test_inactive_weeks_excluded(self):
        """Inactive weeks are not included in the progress."""
        week1 = self.factory.create_week(self.course, order=1)
        week2 = self.factory.create_week(self.course, order=2)
        self.factory.create_session(week1, order=1)
        self.factory.create_session(week2, order=1)
        week2.is_active = False
        week2.save()
        result = ProgressService.get_course_progress(self.profile, self.course)
        self.assertEqual(len(result["weeks"]), 1)

    def test_inactive_sessions_excluded_from_count(self):
        """Inactive sessions are not counted in total or completed."""
        week = self.factory.create_week(self.course, order=1)
        s1 = self.factory.create_session(week, order=1)
        s2 = self.factory.create_session(week, order=2)
        self.factory.complete_session(self.profile, s1)
        s2.is_active = False
        s2.save()
        result = ProgressService.get_course_progress(self.profile, self.course)
        week_data = result["weeks"][0]
        self.assertEqual(week_data["total_sessions"], 1)
        self.assertEqual(week_data["completed_sessions"], 1)
        self.assertTrue(week_data["is_complete"])

    def test_week_with_zero_sessions_not_complete(self):
        """A week with 0 total active sessions should have is_complete=False."""
        self.factory.create_week(self.course, order=1)
        # No sessions created for this week
        result = ProgressService.get_course_progress(self.profile, self.course)
        self.assertEqual(len(result["weeks"]), 1)
        self.assertEqual(result["weeks"][0]["total_sessions"], 0)
        self.assertFalse(result["weeks"][0]["is_complete"])

    def test_weeks_ordered_by_order_field(self):
        """Weeks are returned sorted by their order field."""
        week3 = self.factory.create_week(self.course, order=3, name="Week 3")
        week1 = self.factory.create_week(self.course, order=1, name="Week 1")
        week2 = self.factory.create_week(self.course, order=2, name="Week 2")
        self.factory.create_session(week1, order=1)
        self.factory.create_session(week2, order=1)
        self.factory.create_session(week3, order=1)
        result = ProgressService.get_course_progress(self.profile, self.course)
        week_orders = [w["week_order"] for w in result["weeks"]]
        self.assertEqual(week_orders, [1, 2, 3])


class GetCalendarDataTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.data = self.factory.setup_full_level(order=1)

    def test_exam_dates_in_calendar(self):
        """ExamAttempt dates appear in calendar data."""
        exam = self.data["exam"]
        now = timezone.now()
        ExamAttempt.objects.create(
            student=self.profile,
            exam=exam,
            status=ExamAttempt.Status.SUBMITTED,
            score=15,
            total_marks=20,
            is_passed=True,
            submitted_at=now,
        )
        result = ProgressService.get_calendar_data(self.profile, now.year, now.month)
        self.assertGreater(len(result), 0)
        found_exam = any(entry["exams_taken"] > 0 for entry in result)
        self.assertTrue(found_exam)

    def test_empty_month_returns_empty(self):
        result = ProgressService.get_calendar_data(self.profile, 2020, 1)
        self.assertEqual(result, [])

    def test_session_and_exam_on_same_day(self):
        """Both sessions_watched and exams_taken appear for the same date."""
        now = timezone.now()
        session = self.data["sessions"][0]
        SessionProgress.objects.create(
            student=self.profile,
            session=session,
            watched_seconds=100,
        )
        exam = self.data["exam"]
        ExamAttempt.objects.create(
            student=self.profile,
            exam=exam,
            status=ExamAttempt.Status.SUBMITTED,
            score=15,
            total_marks=20,
            is_passed=True,
            submitted_at=now,
        )
        result = ProgressService.get_calendar_data(self.profile, now.year, now.month)
        # Find any entry that has both sessions_watched and exams_taken > 0
        # (they should share the same date since both were created "now")
        combined = [e for e in result if e["sessions_watched"] > 0 and e["exams_taken"] > 0]
        self.assertGreater(len(combined), 0, f"Expected an entry with both activity types, got: {result}")

    def test_results_sorted_by_date(self):
        """Calendar data entries are sorted by date."""
        now = timezone.now()
        session = self.data["sessions"][0]
        SessionProgress.objects.create(
            student=self.profile,
            session=session,
            watched_seconds=100,
        )
        result = ProgressService.get_calendar_data(self.profile, now.year, now.month)
        dates = [entry["date"] for entry in result]
        self.assertEqual(dates, sorted(dates))


class GetLeaderboardTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.data = self.factory.setup_full_level(order=1, num_questions=2)
        # Create students
        self.user_a, self.profile_a = self.factory.create_student(email="a@test.com")
        self.user_b, self.profile_b = self.factory.create_student(email="b@test.com")
        self.user_c, self.profile_c = self.factory.create_student(email="c@test.com")

    def _create_passed_attempt(self, profile, exam, score=8):
        return ExamAttempt.objects.create(
            student=profile,
            exam=exam,
            status=ExamAttempt.Status.SUBMITTED,
            score=score,
            total_marks=exam.total_marks,
            is_passed=True,
            submitted_at=timezone.now(),
        )

    def test_user_not_in_top_n(self):
        """User outside top N gets their rank from the full ranked list."""
        # A and B pass exams; C does not
        self._create_passed_attempt(self.profile_a, self.data["exam"], score=10)
        self.factory.pass_level(self.profile_a, self.data["level"])
        self._create_passed_attempt(self.profile_b, self.data["exam"], score=8)
        self.factory.pass_level(self.profile_b, self.data["level"])

        # C passes exam with lowest score
        self._create_passed_attempt(self.profile_c, self.data["exam"], score=5)

        # Request with limit=2 so C is not in top 2
        result = ProgressService.get_leaderboard(self.user_c, limit=2)
        self.assertEqual(len(result["leaderboard"]), 2)
        # C should still get a rank (outside top N)
        self.assertIsNotNone(result["my_rank"])
        self.assertEqual(result["my_rank"], 3)

    def test_user_in_top_n(self):
        """User inside top N gets their rank from the leaderboard list."""
        self._create_passed_attempt(self.profile_a, self.data["exam"], score=10)
        self.factory.pass_level(self.profile_a, self.data["level"])
        result = ProgressService.get_leaderboard(self.user_a, limit=10)
        self.assertEqual(result["my_rank"], 1)

    def test_non_student_user_gets_none_rank(self):
        """Admin/non-student user gets my_rank=None."""
        admin = self.factory.create_admin()
        self._create_passed_attempt(self.profile_a, self.data["exam"], score=10)
        self.factory.pass_level(self.profile_a, self.data["level"])
        result = ProgressService.get_leaderboard(admin, limit=10)
        self.assertIsNone(result["my_rank"])
        self.assertGreater(len(result["leaderboard"]), 0)


class BuildRankedLeaderboardTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.data = self.factory.setup_full_level(order=1, num_questions=2)

    def test_missing_profile_skipped(self):
        """If a student profile is deleted, that entry is skipped."""
        user, profile = self.factory.create_student(email="ghost@test.com")
        exam = self.data["exam"]
        ExamAttempt.objects.create(
            student=profile,
            exam=exam,
            status=ExamAttempt.Status.SUBMITTED,
            score=10,
            total_marks=exam.total_marks,
            is_passed=True,
            submitted_at=timezone.now(),
        )
        profile_id = profile.id
        # Delete the profile to simulate missing profile
        profile.delete()

        leaderboard, ranked = ProgressService._build_ranked_leaderboard(level_id=None, limit=10)
        student_ids = [entry["student_id"] for entry in leaderboard]
        self.assertNotIn(profile_id, student_ids)

    def test_leaderboard_sorted_by_levels_cleared_then_score(self):
        """Leaderboard sorts by levels_cleared descending, then total_score."""
        user_a, profile_a = self.factory.create_student(email="a@test.com")
        user_b, profile_b = self.factory.create_student(email="b@test.com")
        exam = self.data["exam"]
        level = self.data["level"]

        # A: higher score but no levels cleared
        ExamAttempt.objects.create(
            student=profile_a,
            exam=exam,
            status=ExamAttempt.Status.SUBMITTED,
            score=20,
            total_marks=exam.total_marks,
            is_passed=True,
            submitted_at=timezone.now(),
        )

        # B: lower score but level cleared
        ExamAttempt.objects.create(
            student=profile_b,
            exam=exam,
            status=ExamAttempt.Status.SUBMITTED,
            score=5,
            total_marks=exam.total_marks,
            is_passed=True,
            submitted_at=timezone.now(),
        )
        self.factory.pass_level(profile_b, level)

        leaderboard, _ = ProgressService._build_ranked_leaderboard(level_id=None, limit=10)
        # B should be rank 1 (1 level cleared vs 0)
        self.assertEqual(leaderboard[0]["student_id"], profile_b.id)
        self.assertEqual(leaderboard[1]["student_id"], profile_a.id)

    def test_scoped_by_level(self):
        """When level_id is provided, only that level's data is included."""
        data2 = self.factory.setup_full_level(order=2, num_questions=2)
        user, profile = self.factory.create_student(email="scoped@test.com")

        # Pass exam on level 2 only
        ExamAttempt.objects.create(
            student=profile,
            exam=data2["exam"],
            status=ExamAttempt.Status.SUBMITTED,
            score=10,
            total_marks=data2["exam"].total_marks,
            is_passed=True,
            submitted_at=timezone.now(),
        )

        # Scoped to level 1 -- this student should not appear
        leaderboard, _ = ProgressService._build_ranked_leaderboard(level_id=self.data["level"].pk, limit=10)
        student_ids = [entry["student_id"] for entry in leaderboard]
        self.assertNotIn(profile.id, student_ids)

    def test_disqualified_attempts_excluded(self):
        """Disqualified attempts do not count."""
        user, profile = self.factory.create_student(email="disq@test.com")
        exam = self.data["exam"]
        ExamAttempt.objects.create(
            student=profile,
            exam=exam,
            status=ExamAttempt.Status.SUBMITTED,
            score=20,
            total_marks=exam.total_marks,
            is_passed=True,
            is_disqualified=True,
            submitted_at=timezone.now(),
        )
        leaderboard, _ = ProgressService._build_ranked_leaderboard(level_id=None, limit=10)
        student_ids = [entry["student_id"] for entry in leaderboard]
        self.assertNotIn(profile.id, student_ids)

    def test_levels_cleared_without_exam_attempt(self):
        """Student with level cleared but no non-disqualified exam still appears."""
        user, profile = self.factory.create_student(email="levels_only@test.com")
        self.factory.pass_level(profile, self.data["level"])
        leaderboard, _ = ProgressService._build_ranked_leaderboard(level_id=None, limit=10)
        student_ids = [entry["student_id"] for entry in leaderboard]
        self.assertIn(profile.id, student_ids)
        entry = next(e for e in leaderboard if e["student_id"] == profile.id)
        self.assertEqual(entry["levels_cleared"], 1)
        self.assertEqual(entry["exams_passed"], 0)
        self.assertEqual(entry["total_score"], 0.0)
