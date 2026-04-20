from rest_framework import status
from rest_framework.test import APITestCase

from core.test_utils import TestFactory


class LevelPublicAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.level = self.factory.create_level(order=1, name="Foundation")
        self.course = self.factory.create_course(self.level)
        self.week = self.factory.create_week(self.course, order=1)

    def test_list_levels_unauthenticated(self):
        response = self.client.get("/api/v1/levels/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_levels_returns_active_only(self):
        inactive = self.factory.create_level(order=2, name="Hidden")
        inactive.is_active = False
        inactive.save()
        response = self.client.get("/api/v1/levels/")
        names = [item["name"] for item in response.data]
        self.assertIn("Foundation", names)
        self.assertNotIn("Hidden", names)

    def test_level_detail(self):
        response = self.client.get(f"/api/v1/levels/{self.level.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Foundation")

    def test_level_detail_includes_courses(self):
        response = self.client.get(f"/api/v1/levels/{self.level.pk}/")
        self.assertIn("courses", response.data)
        self.assertEqual(len(response.data["courses"]), 1)

    def test_level_detail_inactive_returns_404(self):
        self.level.is_active = False
        self.level.save()
        response = self.client.get(f"/api/v1/levels/{self.level.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_level_detail_nonexistent_returns_404(self):
        response = self.client.get("/api/v1/levels/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminLevelAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.level = self.factory.create_level(order=1)
        self.course = self.factory.create_course(self.level)

    def test_admin_create_level(self):
        response = self.admin_client.post(
            "/api/v1/levels/admin/",
            {
                "name": "Advanced",
                "order": 2,
                "passing_percentage": "70.00",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_update_level(self):
        response = self.admin_client.patch(
            f"/api/v1/levels/admin/{self.level.pk}/",
            {"name": "Updated"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.level.refresh_from_db()
        self.assertEqual(self.level.name, "Updated")

    def test_admin_delete_level(self):
        response = self.admin_client.delete(f"/api/v1/levels/admin/{self.level.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_create_week(self):
        response = self.admin_client.post(
            f"/api/v1/courses/admin/{self.course.pk}/weeks/",
            {"name": "Week 1", "order": 1, "course": self.course.pk},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_list_includes_inactive_levels(self):
        self.level.is_active = False
        self.level.save()
        response = self.admin_client.get("/api/v1/levels/admin/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data]
        self.assertIn(self.level.name, names)

    def test_student_cannot_access_admin_levels(self):
        user, _ = self.factory.create_student()
        student_client = self.factory.get_auth_client(user)
        response = student_client.get("/api/v1/levels/admin/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access_admin_levels(self):
        response = self.client.get("/api/v1/levels/admin/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
