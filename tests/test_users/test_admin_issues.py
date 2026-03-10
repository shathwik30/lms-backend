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
