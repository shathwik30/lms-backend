from rest_framework import status
from rest_framework.test import APITestCase

from core.test_utils import TestFactory


class SearchAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data = self.factory.setup_full_level(order=1)

    def test_search_by_course_title(self):
        response = self.client.get("/api/v1/search/?q=Level 1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["courses"]), 0)

    def test_search_by_session_title(self):
        response = self.client.get("/api/v1/search/?q=Session")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["sessions"]), 0)

    def test_search_by_level_name(self):
        response = self.client.get("/api/v1/search/?q=Level")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data["levels"]), 0)

    def test_search_no_results(self):
        response = self.client.get("/api/v1/search/?q=nonexistent_xyz")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["courses"]), 0)
        self.assertEqual(len(response.data["sessions"]), 0)
        self.assertEqual(len(response.data["levels"]), 0)

    def test_search_too_short_query(self):
        response = self.client.get("/api/v1/search/?q=a")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_empty_query(self):
        response = self.client.get("/api/v1/search/?q=")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_missing_query(self):
        response = self.client.get("/api/v1/search/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_excludes_inactive(self):
        self.data["sessions"][0].is_active = False
        self.data["sessions"][0].save()
        response = self.client.get("/api/v1/search/?q=Session 1")
        for s in response.data["sessions"]:
            self.assertNotEqual(s["id"], self.data["sessions"][0].pk)

    def test_unauthenticated_denied(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.get("/api/v1/search/?q=test")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ScopedSearchTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, _ = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data1 = self.factory.setup_full_level(order=1, num_sessions=2, num_questions=3)
        self.data2 = self.factory.setup_full_level(order=2, num_sessions=2, num_questions=2)

        # Create weekly exams with week FK for week-scoped question search tests
        self.weekly_exam1 = self.factory.create_exam(
            self.data1["level"],
            week=self.data1["week"],
            course=self.data1["course"],
            exam_type="weekly",
            num_questions=3,
        )
        for _ in range(3):
            self.factory.create_question(self.weekly_exam1)

        self.weekly_exam2 = self.factory.create_exam(
            self.data2["level"],
            week=self.data2["week"],
            course=self.data2["course"],
            exam_type="weekly",
            num_questions=2,
        )
        for _ in range(2):
            self.factory.create_question(self.weekly_exam2)

    def test_search_scoped_by_level(self):
        level1 = self.data1["level"]
        response = self.client.get(f"/api/v1/search/?q=Session&level={level1.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for session in response.data["sessions"]:
            # week is returned as an FK integer, not a nested object
            from apps.levels.models import Week

            week = Week.objects.select_related("course").get(pk=session["week"])
            self.assertEqual(week.course.level_id, level1.pk)

    def test_search_level_scope_excludes_other_levels(self):
        level1 = self.data1["level"]
        response = self.client.get(f"/api/v1/search/?q=Session&level={level1.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        session_ids = {s["id"] for s in response.data["sessions"]}
        for session in self.data2["sessions"]:
            self.assertNotIn(session.pk, session_ids)

    def test_search_level_scope_hides_levels_list(self):
        level1 = self.data1["level"]
        response = self.client.get(f"/api/v1/search/?q=Level&level={level1.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["levels"]), 0)

    def test_search_scoped_by_week(self):
        week1 = self.data1["week"]
        response = self.client.get(f"/api/v1/search/?q=Session&week={week1.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for session in response.data["sessions"]:
            self.assertEqual(session["week"], week1.pk)

    def test_search_week_scope_excludes_other_weeks(self):
        week1 = self.data1["week"]
        response = self.client.get(f"/api/v1/search/?q=Session&week={week1.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        session_ids = {s["id"] for s in response.data["sessions"]}
        for session in self.data2["sessions"]:
            self.assertNotIn(session.pk, session_ids)

    def test_questions_count_in_response(self):
        response = self.client.get("/api/v1/search/?q=question")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("questions_count", response.data)
        self.assertIsInstance(response.data["questions_count"], int)

    def test_questions_count_scoped_by_level(self):
        level1 = self.data1["level"]
        response = self.client.get(f"/api/v1/search/?q=question&level={level1.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 3 from level_final exam + 3 from weekly exam = 6
        self.assertEqual(response.data["questions_count"], 6)

    def test_questions_count_scoped_by_week(self):
        week1 = self.data1["week"]
        response = self.client.get(f"/api/v1/search/?q=question&week={week1.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only weekly exam questions have a week FK
        self.assertEqual(response.data["questions_count"], 3)
