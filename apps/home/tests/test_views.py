from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.home.models import Banner
from core.test_utils import TestFactory


class BannerAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_public_banner_list(self):
        Banner.objects.create(
            title="Welcome",
            image_url="https://example.com/banner.jpg",
            order=1,
        )
        Banner.objects.create(
            title="Inactive",
            image_url="https://example.com/hidden.jpg",
            is_active=False,
        )
        anon = APIClient()
        response = anon.get("/api/v1/home/banners/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "Welcome")

    def test_banner_list_ordered(self):
        Banner.objects.create(
            title="Second",
            image_url="https://example.com/2.jpg",
            order=2,
        )
        Banner.objects.create(
            title="First",
            image_url="https://example.com/1.jpg",
            order=1,
        )
        anon = APIClient()
        response = anon.get("/api/v1/home/banners/")
        self.assertEqual(response.data[0]["title"], "First")
        self.assertEqual(response.data[1]["title"], "Second")

    def test_featured_courses(self):
        level = self.factory.create_level(order=1)
        self.factory.create_course(level)
        anon = APIClient()
        response = anon.get("/api/v1/home/featured/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_featured_excludes_inactive(self):
        level = self.factory.create_level(order=1)
        course = self.factory.create_course(level)
        course.is_active = False
        course.save()
        anon = APIClient()
        response = anon.get("/api/v1/home/featured/")
        self.assertEqual(len(response.data), 0)


class AdminBannerAPITests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)

    def test_admin_create_banner(self):
        response = self.admin_client.post(
            "/api/v1/home/admin/banners/",
            {
                "title": "Promo",
                "image_url": "https://example.com/promo.jpg",
                "link_type": "none",
                "order": 1,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_update_banner(self):
        banner = Banner.objects.create(
            title="Old",
            image_url="https://example.com/old.jpg",
        )
        response = self.admin_client.patch(
            f"/api/v1/home/admin/banners/{banner.pk}/",
            {"title": "Updated"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        banner.refresh_from_db()
        self.assertEqual(banner.title, "Updated")

    def test_admin_delete_banner(self):
        banner = Banner.objects.create(
            title="Delete",
            image_url="https://example.com/del.jpg",
        )
        response = self.admin_client.delete(f"/api/v1/home/admin/banners/{banner.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_student_cannot_admin(self):
        user, _ = self.factory.create_student()
        client = self.factory.get_auth_client(user)
        response = client.post(
            "/api/v1/home/admin/banners/",
            {
                "title": "Nope",
                "image_url": "https://example.com/nope.jpg",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class BannerURLValidationTests(APITestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)

    def test_javascript_url_rejected(self):
        response = self.admin_client.post(
            "/api/v1/home/admin/banners/",
            {
                "title": "XSS Banner",
                "image_url": "https://example.com/banner.jpg",
                "link_type": "url",
                "link_url": "javascript:alert(1)",
                "order": 1,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_data_url_rejected(self):
        response = self.admin_client.post(
            "/api/v1/home/admin/banners/",
            {
                "title": "Data Banner",
                "image_url": "https://example.com/banner.jpg",
                "link_type": "url",
                "link_url": "data:text/html,<script>alert(1)</script>",
                "order": 1,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_https_url_accepted(self):
        response = self.admin_client.post(
            "/api/v1/home/admin/banners/",
            {
                "title": "Valid Banner",
                "image_url": "https://example.com/banner.jpg",
                "link_type": "url",
                "link_url": "https://example.com",
                "order": 1,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_banner_without_url_accepted(self):
        response = self.admin_client.post(
            "/api/v1/home/admin/banners/",
            {
                "title": "No Link Banner",
                "image_url": "https://example.com/banner.jpg",
                "link_type": "none",
                "order": 1,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
