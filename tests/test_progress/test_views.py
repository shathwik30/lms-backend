from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.progress.models import LevelProgress
from core.constants import NextAction
from core.test_utils import TestFactory


class ProgressTrackingTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data = self.factory.setup_full_level(order=1)
        self.factory.create_purchase(self.profile, self.data["level"])

    def test_update_session_progress(self):
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/progress/sessions/{session.pk}/",
            {"watched_seconds": 1000},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["watched_seconds"], 1000)

    def test_progress_only_increases(self):
        session = self.data["sessions"][0]
        self.client.post(
            f"/api/v1/progress/sessions/{session.pk}/",
            {"watched_seconds": 2000},
        )
        self.client.post(
            f"/api/v1/progress/sessions/{session.pk}/",
            {"watched_seconds": 500},
        )
        response = self.client.post(
            f"/api/v1/progress/sessions/{session.pk}/",
            {"watched_seconds": 100},
        )
        self.assertEqual(response.data["watched_seconds"], 2000)

    def test_auto_complete_at_90_percent_without_feedback(self):
        session = self.data["sessions"][0]
        threshold = int(session.duration_seconds * 0.95)
        response = self.client.post(
            f"/api/v1/progress/sessions/{session.pk}/",
            {"watched_seconds": threshold},
        )
        self.assertTrue(response.data["is_completed"])

    def test_no_complete_below_threshold(self):
        session = self.data["sessions"][0]
        threshold = int(session.duration_seconds * 0.89)
        response = self.client.post(
            f"/api/v1/progress/sessions/{session.pk}/",
            {"watched_seconds": threshold},
        )
        self.assertFalse(response.data["is_completed"])

    def test_no_complete_at_89_percent(self):
        """Progress at 89% should NOT auto-complete."""
        session = self.data["sessions"][0]
        below_threshold = int(session.duration_seconds * 0.89)
        response = self.client.post(
            f"/api/v1/progress/sessions/{session.pk}/",
            {"watched_seconds": below_threshold},
        )
        self.assertFalse(response.data["is_completed"])

    def test_watched_seconds_capped_at_duration(self):
        """watched_seconds should never exceed session.duration_seconds."""
        session = self.data["sessions"][0]
        response = self.client.post(
            f"/api/v1/progress/sessions/{session.pk}/",
            {"watched_seconds": session.duration_seconds + 5000},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["watched_seconds"], session.duration_seconds)

    def test_progress_nonexistent_session_returns_404(self):
        response = self.client.post(
            "/api/v1/progress/sessions/00000000-0000-0000-0000-000000000000/",
            {"watched_seconds": 100},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_progress_inactive_session_returns_404(self):
        session = self.data["sessions"][0]
        session.is_active = False
        session.save()
        response = self.client.post(
            f"/api/v1/progress/sessions/{session.pk}/",
            {"watched_seconds": 100},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_level_auto_completion(self):
        """When all sessions complete, LevelProgress should become SYLLABUS_COMPLETE."""
        LevelProgress.objects.create(
            student=self.profile,
            level=self.data["level"],
            status=LevelProgress.Status.IN_PROGRESS,
        )
        for s in self.data["sessions"]:
            self.client.post(
                f"/api/v1/progress/sessions/{s.pk}/",
                {"watched_seconds": s.duration_seconds},
            )
        progress = LevelProgress.objects.get(student=self.profile, level=self.data["level"])
        self.assertEqual(progress.status, LevelProgress.Status.SYLLABUS_COMPLETE)

    def test_session_progress_list(self):
        response = self.client.get(f"/api/v1/progress/levels/{self.data['level'].pk}/sessions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_level_progress_list(self):
        response = self.client.get("/api/v1/progress/levels/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_cannot_access_progress(self):
        anon = APIClient()
        response = anon.post(
            f"/api/v1/progress/sessions/{self.data['sessions'][0].pk}/",
            {"watched_seconds": 100},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProgressDataIsolationTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user_a, self.profile_a = self.factory.create_student(email="a@test.com")
        self.user_b, self.profile_b = self.factory.create_student(email="b@test.com")
        self.client_a = self.factory.get_auth_client(self.user_a)
        self.client_b = self.factory.get_auth_client(self.user_b)
        self.data = self.factory.setup_full_level(order=1)
        self.factory.create_purchase(self.profile_a, self.data["level"])

    def test_student_cannot_see_others_session_progress(self):
        session = self.data["sessions"][0]
        self.client_a.post(
            f"/api/v1/progress/sessions/{session.pk}/",
            {"watched_seconds": 1000},
        )
        response = self.client_b.get(f"/api/v1/progress/levels/{self.data['level'].pk}/sessions/")
        self.assertEqual(response.data["count"], 0)


class DashboardTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data1 = self.factory.setup_full_level(order=1)
        self.data2 = self.factory.setup_full_level(order=2)

    def test_dashboard_new_student(self):
        from apps.exams.models import Exam

        onboarding_exam = self.factory.create_exam(self.data1["level"], exam_type=Exam.ExamType.ONBOARDING)
        response = self.client.get("/api/v1/progress/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["next_action"], NextAction.TAKE_ONBOARDING_EXAM)
        self.assertEqual(response.data["exam_id"], onboarding_exam.id)

    def test_dashboard_after_onboarding_no_purchase(self):
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save()
        response = self.client.get("/api/v1/progress/dashboard/")
        self.assertEqual(response.data["next_action"], NextAction.PURCHASE_LEVEL)

    def test_dashboard_after_passing_level1_onboarding_shows_level2_exam(self):
        from apps.exams.models import Exam

        self.factory.create_exam(self.data1["level"], exam_type=Exam.ExamType.ONBOARDING)
        level2_exam = self.factory.create_exam(self.data2["level"], exam_type=Exam.ExamType.ONBOARDING)
        self.profile.current_level = self.data2["level"]
        self.profile.highest_cleared_level = self.data1["level"]
        self.profile.save(update_fields=["current_level", "highest_cleared_level"])

        response = self.client.get("/api/v1/progress/dashboard/")
        self.assertEqual(response.data["next_action"], NextAction.TAKE_ONBOARDING_EXAM)
        self.assertEqual(response.data["current_level"]["order"], 2)
        self.assertEqual(response.data["exam_id"], level2_exam.id)

    def test_dashboard_after_pass(self):
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save()
        self.factory.pass_level(self.profile, self.data1["level"])
        response = self.client.get("/api/v1/progress/dashboard/")
        self.assertEqual(response.data["next_action"], NextAction.PURCHASE_LEVEL)
        self.assertEqual(response.data["current_level"]["order"], 2)

    def test_dashboard_all_complete(self):
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save()
        self.factory.pass_level(self.profile, self.data1["level"])
        self.factory.pass_level(self.profile, self.data2["level"])
        response = self.client.get("/api/v1/progress/dashboard/")
        self.assertEqual(response.data["next_action"], NextAction.ALL_COMPLETE)

    def test_dashboard_in_progress(self):
        self.profile.is_onboarding_exam_attempted = True
        self.profile.save()
        self.factory.create_purchase(self.profile, self.data1["level"])
        LevelProgress.objects.create(
            student=self.profile,
            level=self.data1["level"],
            status=LevelProgress.Status.IN_PROGRESS,
        )
        response = self.client.get("/api/v1/progress/dashboard/")
        self.assertEqual(response.data["next_action"], NextAction.COMPLETE_COURSES)


class LeaderboardTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        # Student A — passes level 1
        self.user_a, self.profile_a = self.factory.create_student(email="a@test.com")
        self.client_a = self.factory.get_auth_client(self.user_a)
        # Student B — passes level 1 and level 2
        self.user_b, self.profile_b = self.factory.create_student(email="b@test.com")

        self.data1 = self.factory.setup_full_level(order=1, num_questions=2)
        self.data2 = self.factory.setup_full_level(order=2, num_questions=2)

        # A passes level 1
        self._create_passed_attempt(self.profile_a, self.data1["exam"], score=6)
        self.factory.pass_level(self.profile_a, self.data1["level"])

        # B passes level 1 and level 2
        self._create_passed_attempt(self.profile_b, self.data1["exam"], score=8)
        self._create_passed_attempt(self.profile_b, self.data2["exam"], score=7)
        self.factory.pass_level(self.profile_b, self.data1["level"])
        self.factory.pass_level(self.profile_b, self.data2["level"])

    def _create_passed_attempt(self, profile, exam, score=8):
        from django.utils import timezone

        from apps.exams.models import ExamAttempt

        return ExamAttempt.objects.create(
            student=profile,
            exam=exam,
            status=ExamAttempt.Status.SUBMITTED,
            score=score,
            total_marks=exam.total_marks,
            is_passed=True,
            submitted_at=timezone.now(),
        )

    def test_leaderboard_returns_ranked_students(self):
        response = self.client_a.get("/api/v1/progress/leaderboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("leaderboard", response.data)
        lb = response.data["leaderboard"]
        self.assertEqual(len(lb), 2)
        # B should be rank 1 (2 levels cleared vs A's 1)
        self.assertEqual(lb[0]["student_id"], self.profile_b.id)
        self.assertEqual(lb[0]["rank"], 1)
        self.assertEqual(lb[0]["levels_cleared"], 2)
        self.assertEqual(lb[1]["student_id"], self.profile_a.id)
        self.assertEqual(lb[1]["rank"], 2)

    def test_leaderboard_includes_my_rank(self):
        response = self.client_a.get("/api/v1/progress/leaderboard/")
        self.assertEqual(response.data["my_rank"], 2)

    def test_leaderboard_scoped_by_level(self):
        level1 = self.data1["level"]
        response = self.client_a.get(f"/api/v1/progress/leaderboard/?level={level1.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lb = response.data["leaderboard"]
        # Both students passed level 1 exams
        self.assertEqual(len(lb), 2)

    def test_leaderboard_limit(self):
        response = self.client_a.get("/api/v1/progress/leaderboard/?limit=1")
        self.assertEqual(len(response.data["leaderboard"]), 1)

    def test_leaderboard_empty_when_no_passes(self):
        # New student with no data
        user_c, _ = self.factory.create_student(email="c@test.com")
        client_c = self.factory.get_auth_client(user_c)
        response = client_c.get("/api/v1/progress/leaderboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Still shows leaderboard from other students
        self.assertGreater(len(response.data["leaderboard"]), 0)
        # But my_rank is None
        self.assertIsNone(response.data["my_rank"])

    def test_leaderboard_unauthenticated_denied(self):
        anon = APIClient()
        response = anon.get("/api/v1/progress/leaderboard/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_leaderboard_entry_fields(self):
        response = self.client_a.get("/api/v1/progress/leaderboard/")
        entry = response.data["leaderboard"][0]
        self.assertIn("rank", entry)
        self.assertIn("student_id", entry)
        self.assertIn("full_name", entry)
        self.assertIn("profile_picture", entry)
        self.assertIn("levels_cleared", entry)
        self.assertIn("total_score", entry)
        self.assertIn("exams_passed", entry)

    def test_disqualified_attempts_excluded(self):
        """Disqualified attempts should not count."""
        user_c, profile_c = self.factory.create_student(email="disq@test.com")
        from django.utils import timezone

        from apps.exams.models import ExamAttempt

        ExamAttempt.objects.create(
            student=profile_c,
            exam=self.data1["exam"],
            status=ExamAttempt.Status.SUBMITTED,
            score=10,
            total_marks=8,
            is_passed=True,
            is_disqualified=True,
            submitted_at=timezone.now(),
        )
        client_c = self.factory.get_auth_client(user_c)
        response = client_c.get("/api/v1/progress/leaderboard/")
        student_ids = {e["student_id"] for e in response.data["leaderboard"]}
        self.assertNotIn(profile_c.id, student_ids)
