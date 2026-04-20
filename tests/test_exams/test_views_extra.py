from django.test import TestCase

from apps.exams.models import Exam, ProctoringViolation
from core.constants import ErrorMessage
from core.test_utils import TestFactory


class ExamStartViewTests(TestCase):
    """Tests for ExamStartView covering the exam-not-found path."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)

    def test_exam_not_found_returns_404(self):
        """Starting a non-existent exam returns 404."""
        response = self.client.post("/api/v1/exams/00000000-0000-0000-0000-000000000000/start/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)

    def test_inactive_exam_returns_404(self):
        """Starting an inactive exam returns 404."""
        level = self.factory.create_level(order=1)
        exam = self.factory.create_exam(level)
        exam.is_active = False
        exam.save(update_fields=["is_active"])

        response = self.client.post(f"/api/v1/exams/{exam.pk}/start/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)


class ReportViolationViewTests(TestCase):
    """Tests for ReportViolationView covering 404 and violation-data-in-response paths."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)

    def test_attempt_not_found_returns_404(self):
        """Reporting a violation for a non-existent attempt returns 404."""
        response = self.client.post(
            "/api/v1/exams/attempts/00000000-0000-0000-0000-000000000000/report-violation/",
            data={
                "violation_type": ProctoringViolation.ViolationType.TAB_SWITCH,
                "details": "Switched tab",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)

    def test_report_violation_success_returns_violation_data(self):
        """Successful violation report returns violation data with warning counts."""
        level = self.factory.create_level(order=1)
        exam = self.factory.create_exam(level, exam_type=Exam.ExamType.WEEKLY)
        for _ in range(5):
            self.factory.create_question(exam)
        exam.is_proctored = True
        exam.max_warnings = 5
        exam.save(update_fields=["is_proctored", "max_warnings"])

        # Student needs purchase to start exam
        self.factory.create_purchase(self.profile, level)

        # Start the exam
        start_response = self.client.post(f"/api/v1/exams/{exam.pk}/start/")
        self.assertIn(start_response.status_code, [200, 201])
        attempt_id = start_response.data["id"]

        # Report a violation
        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/report-violation/",
            data={
                "violation_type": ProctoringViolation.ViolationType.TAB_SWITCH,
                "details": "Student switched to another tab",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("violation_type", response.data)
        self.assertEqual(response.data["total_warnings"], 1)
        self.assertEqual(response.data["max_warnings"], 5)
        self.assertFalse(response.data["is_disqualified"])

    def test_report_violation_non_proctored_exam_returns_400(self):
        """Reporting violation for non-proctored exam returns error."""
        level = self.factory.create_level(order=1)
        exam = self.factory.create_exam(level, exam_type=Exam.ExamType.WEEKLY)
        for _ in range(5):
            self.factory.create_question(exam)
        # is_proctored defaults to False

        self.factory.create_purchase(self.profile, level)

        start_response = self.client.post(f"/api/v1/exams/{exam.pk}/start/")
        self.assertIn(start_response.status_code, [200, 201])
        attempt_id = start_response.data["id"]

        response = self.client.post(
            f"/api/v1/exams/attempts/{attempt_id}/report-violation/",
            data={
                "violation_type": ProctoringViolation.ViolationType.TAB_SWITCH,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], ErrorMessage.EXAM_NOT_PROCTORED)


class AttemptViolationsViewTests(TestCase):
    """Tests for AttemptViolationsView covering the not-found path."""

    def setUp(self):
        self.factory = TestFactory()
        self.user, self.profile = self.factory.create_student()
        self.client = self.factory.get_auth_client(self.user)

    def test_attempt_not_found_returns_404(self):
        """Fetching violations for a non-existent attempt returns 404."""
        response = self.client.get("/api/v1/exams/attempts/00000000-0000-0000-0000-000000000000/violations/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], ErrorMessage.NOT_FOUND)

    def test_attempt_violations_success(self):
        """Fetching violations for a valid attempt returns violation list."""
        level = self.factory.create_level(order=1)
        exam = self.factory.create_exam(level, exam_type=Exam.ExamType.WEEKLY)
        for _ in range(5):
            self.factory.create_question(exam)
        exam.is_proctored = True
        exam.max_warnings = 5
        exam.save(update_fields=["is_proctored", "max_warnings"])

        self.factory.create_purchase(self.profile, level)

        start_response = self.client.post(f"/api/v1/exams/{exam.pk}/start/")
        self.assertIn(start_response.status_code, [200, 201])
        attempt_id = start_response.data["id"]

        response = self.client.get(f"/api/v1/exams/attempts/{attempt_id}/violations/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("violations", response.data)
        self.assertEqual(response.data["total_warnings"], 0)
        self.assertEqual(response.data["max_warnings"], 5)
        self.assertFalse(response.data["is_disqualified"])
