from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Bookmark
from core.test_utils import TestFactory


class BookmarkAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)
        self.data = self.factory.setup_full_level(order=1)
        self.session = self.data["sessions"][0]

    def test_create_bookmark(self):
        response = self.client.post(
            "/api/v1/courses/bookmarks/",
            {
                "session": self.session.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["session"], self.session.pk)
        self.assertEqual(response.data["session_title"], self.session.title)

    def test_list_bookmarks(self):
        Bookmark.objects.create(student=self.profile, session=self.session)
        response = self.client.get("/api/v1/courses/bookmarks/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_list_only_own_bookmarks(self):
        other_user, other_profile = self.factory.create_student(email="other@test.com")
        Bookmark.objects.create(student=other_profile, session=self.session)
        Bookmark.objects.create(student=self.profile, session=self.session)
        response = self.client.get("/api/v1/courses/bookmarks/")
        self.assertEqual(response.data["count"], 1)

    def test_delete_bookmark(self):
        bm = Bookmark.objects.create(student=self.profile, session=self.session)
        response = self.client.delete(f"/api/v1/courses/bookmarks/{bm.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Bookmark.objects.filter(pk=bm.pk).exists())

    def test_delete_bookmark_not_found(self):
        response = self.client.delete("/api/v1/courses/bookmarks/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_other_users_bookmark_404(self):
        other_user, other_profile = self.factory.create_student(email="other2@test.com")
        bm = Bookmark.objects.create(student=other_profile, session=self.session)
        response = self.client.delete(f"/api/v1/courses/bookmarks/{bm.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_duplicate_bookmark_rejected(self):
        self.client.post("/api/v1/courses/bookmarks/", {"session": self.session.pk})
        response = self.client.post(
            "/api/v1/courses/bookmarks/",
            {
                "session": self.session.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_denied(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        response = anon.get("/api/v1/courses/bookmarks/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_cannot_bookmark(self):
        admin = self.factory.create_admin()
        admin_client = self.factory.get_auth_client(admin)
        response = admin_client.post(
            "/api/v1/courses/bookmarks/",
            {
                "session": self.session.pk,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
