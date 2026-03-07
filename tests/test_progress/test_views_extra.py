from django.test import TestCase

from apps.progress.models import CourseProgress
from core.constants import ErrorMessage
from core.test_utils import TestFactory


class CourseProgressViewTests(TestCase):
    """Tests for CourseProgressView covering the NOT_FOUND path."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)

    def test_course_progress_not_found(self):
        """Requesting progress for a course the student has no record for returns 404."""
        response = self.client.get("/api/v1/progress/courses/99999/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)

    def test_course_progress_found(self):
        """Requesting progress for a course with an existing record returns 200."""
        level = self.factory.create_level(order=1)
        course = self.factory.create_course(level)
        CourseProgress.objects.create(
            student=self.profile,
            course=course,
            status=CourseProgress.Status.IN_PROGRESS,
        )

        response = self.client.get(f"/api/v1/progress/courses/{course.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["course"], course.pk)


class LevelCourseProgressViewTests(TestCase):
    """Tests for LevelCourseProgressView."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)

    def test_level_course_progress_returns_courses(self):
        """Returns course progress records for a given level."""
        level = self.factory.create_level(order=1)
        course1 = self.factory.create_course(level, title="Course A")
        course2 = self.factory.create_course(level, title="Course B")

        CourseProgress.objects.create(
            student=self.profile,
            course=course1,
            status=CourseProgress.Status.NOT_STARTED,
        )
        CourseProgress.objects.create(
            student=self.profile,
            course=course2,
            status=CourseProgress.Status.COMPLETED,
        )

        response = self.client.get(f"/api/v1/progress/levels/{level.pk}/courses/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_level_course_progress_empty(self):
        """Returns empty list when no course progress exists for the level."""
        level = self.factory.create_level(order=1)

        response = self.client.get(f"/api/v1/progress/levels/{level.pk}/courses/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])


class LeaderboardViewTests(TestCase):
    """Tests for LeaderboardView covering the invalid limit parameter path."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)

    def test_leaderboard_invalid_limit_defaults(self):
        """Non-integer limit parameter defaults to DEFAULT_LEADERBOARD_LIMIT."""
        response = self.client.get("/api/v1/progress/leaderboard/?limit=abc")
        self.assertEqual(response.status_code, 200)
        self.assertIn("leaderboard", response.data)
        self.assertIn("my_rank", response.data)

    def test_leaderboard_valid_limit(self):
        """Valid limit parameter returns successfully."""
        response = self.client.get("/api/v1/progress/leaderboard/?limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertIn("leaderboard", response.data)

    def test_leaderboard_with_level_filter(self):
        """Level filter parameter works correctly."""
        level = self.factory.create_level(order=1)
        response = self.client.get(f"/api/v1/progress/leaderboard/?level={level.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("leaderboard", response.data)

    def test_leaderboard_no_params(self):
        """Default request with no params returns successfully."""
        response = self.client.get("/api/v1/progress/leaderboard/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("leaderboard", response.data)
        self.assertIn("my_rank", response.data)

    def test_leaderboard_limit_capped_at_max(self):
        """Limit exceeding MAX_LEADERBOARD_LIMIT is capped."""
        response = self.client.get("/api/v1/progress/leaderboard/?limit=1000")
        self.assertEqual(response.status_code, 200)
        self.assertIn("leaderboard", response.data)
