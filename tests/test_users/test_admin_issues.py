from django.test import TestCase
from rest_framework import status

from apps.users.models import IssueReport
from core.constants import ErrorMessage
from core.test_utils import TestFactory


class AdminIssueReportListViewTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.student_user, self.profile = self.factory.create_student()
        self.student_client = self.factory.get_auth_client(self.student_user)

    def test_list_empty(self):
        response = self.admin_client.get("/api/v1/auth/admin/issues/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_list_returns_all_issues(self):
        IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.BUG,
            subject="Bug report",
            description="Something is broken",
        )
        IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.PAYMENT,
            subject="Payment issue",
            description="Payment failed",
        )
        response = self.admin_client.get("/api/v1/auth/admin/issues/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_list_includes_user_email(self):
        IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.BUG,
            subject="Test",
            description="Test desc",
        )
        response = self.admin_client.get("/api/v1/auth/admin/issues/")
        self.assertEqual(response.data["results"][0]["user_email"], self.student_user.email)

    def test_filter_by_category(self):
        IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.BUG,
            subject="Bug",
            description="Bug desc",
        )
        IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.PAYMENT,
            subject="Payment",
            description="Payment desc",
        )
        response = self.admin_client.get("/api/v1/auth/admin/issues/?category=bug")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["category"], "bug")

    def test_filter_by_is_resolved(self):
        IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.BUG,
            subject="Resolved",
            description="Already fixed",
            is_resolved=True,
        )
        IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.BUG,
            subject="Open",
            description="Not fixed",
        )
        response = self.admin_client.get("/api/v1/auth/admin/issues/?is_resolved=true")
        self.assertEqual(response.data["count"], 1)

    def test_student_cannot_access(self):
        response = self.student_client.get("/api/v1/auth/admin/issues/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminIssueReportUpdateViewTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.student_user, self.profile = self.factory.create_student()
        self.student_client = self.factory.get_auth_client(self.student_user)

        self.report = IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.BUG,
            subject="Test bug",
            description="Something broke",
        )

    def test_get_issue_detail(self):
        response = self.admin_client.get(f"/api/v1/auth/admin/issues/{self.report.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.report.pk)
        self.assertEqual(response.data["subject"], "Test bug")

    def test_get_issue_detail_not_found(self):
        response = self.admin_client.get("/api/v1/auth/admin/issues/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)

    def test_resolve_issue(self):
        response = self.admin_client.patch(
            f"/api/v1/auth/admin/issues/{self.report.pk}/",
            data={"is_resolved": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.report.refresh_from_db()
        self.assertTrue(self.report.is_resolved)

    def test_not_found(self):
        response = self.admin_client.patch(
            "/api/v1/auth/admin/issues/99999/",
            data={"is_resolved": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)

    def test_student_cannot_update(self):
        response = self.student_client.patch(
            f"/api/v1/auth/admin/issues/{self.report.pk}/",
            data={"is_resolved": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_get_issue_detail(self):
        response = self.student_client.get(f"/api/v1/auth/admin/issues/{self.report.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_read_only_fields_not_changed(self):
        response = self.admin_client.patch(
            f"/api/v1/auth/admin/issues/{self.report.pk}/",
            data={"subject": "Hacked subject", "is_resolved": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.report.refresh_from_db()
        self.assertEqual(self.report.subject, "Test bug")
        self.assertTrue(self.report.is_resolved)


class AdminIssueEnrichedFieldsTests(TestCase):
    """Tests for enriched fields on the admin issue endpoints."""

    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.student_user, self.profile = self.factory.create_student()
        self.student_client = self.factory.get_auth_client(self.student_user)

    def test_response_includes_student_name(self):
        IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.BUG,
            subject="Bug",
            description="Desc",
        )
        response = self.admin_client.get("/api/v1/auth/admin/issues/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        issue = response.data["results"][0]
        self.assertIn("student_name", issue)
        self.assertEqual(issue["student_name"], self.student_user.full_name)

    def test_response_includes_profile_picture(self):
        IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.BUG,
            subject="Bug",
            description="Desc",
        )
        response = self.admin_client.get("/api/v1/auth/admin/issues/")
        issue = response.data["results"][0]
        self.assertIn("student_profile_picture", issue)

    def test_response_includes_device_fields(self):
        IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.BUG,
            subject="Bug",
            description="Desc",
            device_info="iPhone 14",
            browser_info="Safari 17",
            os_info="iOS 17",
        )
        response = self.admin_client.get("/api/v1/auth/admin/issues/")
        issue = response.data["results"][0]
        self.assertIn("device_info", issue)
        self.assertIn("browser_info", issue)
        self.assertIn("os_info", issue)
        self.assertEqual(issue["device_info"], "iPhone 14")
        self.assertEqual(issue["browser_info"], "Safari 17")
        self.assertEqual(issue["os_info"], "iOS 17")

    def test_admin_can_write_response(self):
        report = IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.BUG,
            subject="Bug",
            description="Desc",
        )
        response = self.admin_client.patch(
            f"/api/v1/auth/admin/issues/{report.pk}/",
            data={"admin_response": "We are looking into this."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["admin_response"], "We are looking into this.")

    def test_admin_response_persists(self):
        report = IssueReport.objects.create(
            user=self.student_user,
            category=IssueReport.Category.BUG,
            subject="Bug",
            description="Desc",
        )
        self.admin_client.patch(
            f"/api/v1/auth/admin/issues/{report.pk}/",
            data={"admin_response": "Fixed in next release."},
            format="json",
        )
        report.refresh_from_db()
        self.assertEqual(report.admin_response, "Fixed in next release.")

    def test_create_issue_with_device_info(self):
        response = self.student_client.post(
            "/api/v1/auth/report-issue/",
            data={
                "category": "bug",
                "subject": "App crash",
                "description": "Crashes on launch",
                "device_info": "Pixel 7",
                "browser_info": "Chrome 120",
                "os_info": "Android 14",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        report = IssueReport.objects.get(subject="App crash")
        self.assertEqual(report.device_info, "Pixel 7")
        self.assertEqual(report.browser_info, "Chrome 120")
        self.assertEqual(report.os_info, "Android 14")
