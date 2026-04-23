from decimal import Decimal

from django.test import TestCase
from rest_framework import status

from apps.notifications.models import Notification
from apps.payments.models import Purchase
from apps.progress.models import LevelProgress
from apps.users.models import AdminStudentActionLog
from core.test_utils import TestFactory


class AdminStudentActionEndpointTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()
        self.admin = self.factory.create_admin()
        self.admin_client = self.factory.get_auth_client(self.admin)
        self.student_user, self.profile = self.factory.create_student()
        self.student_client = self.factory.get_auth_client(self.student_user)

        self.data = self.factory.setup_full_level(order=1)
        self.level = self.data["level"]
        self.level2 = self.factory.create_level(order=2)

    def test_reset_exam_attempts_endpoint(self):
        for session in self.data["sessions"]:
            self.factory.complete_session(self.profile, session)

        progress = LevelProgress.objects.create(
            student=self.profile,
            level=self.level,
            status=LevelProgress.Status.EXAM_FAILED,
            final_exam_attempts_used=3,
        )

        response = self.admin_client.post(
            f"/api/v1/auth/admin/students/{self.profile.pk}/reset-exam-attempts/",
            {"level_id": self.level.pk, "reason": "Support approved another attempt."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        progress.refresh_from_db()
        self.assertEqual(progress.final_exam_attempts_used, 0)
        self.assertEqual(progress.status, LevelProgress.Status.SYLLABUS_COMPLETE)
        log = AdminStudentActionLog.objects.get(
            student=self.profile,
            action_type=AdminStudentActionLog.ActionType.RESET_EXAM_ATTEMPTS,
        )
        self.assertEqual(log.reason, "Support approved another attempt.")

    def test_unlock_level_endpoint_grants_purchase_and_progress(self):
        response = self.admin_client.post(
            f"/api/v1/auth/admin/students/{self.profile.pk}/unlock-level/",
            {"level_id": self.level2.pk, "reason": "Granted complimentary access."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        purchase = Purchase.objects.get(student=self.profile, level=self.level2)
        self.assertEqual(purchase.amount_paid, Decimal("0"))
        self.assertEqual(purchase.status, Purchase.Status.ACTIVE)

        progress = LevelProgress.objects.get(student=self.profile, level=self.level2)
        self.assertEqual(progress.status, LevelProgress.Status.IN_PROGRESS)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_level, self.level2)

        log = AdminStudentActionLog.objects.get(
            student=self.profile,
            action_type=AdminStudentActionLog.ActionType.UNLOCK_LEVEL,
        )
        self.assertEqual(log.reason, "Granted complimentary access.")
        self.assertEqual(log.purchase, purchase)

    def test_manual_pass_endpoint_marks_level_passed(self):
        response = self.admin_client.post(
            f"/api/v1/auth/admin/students/{self.profile.pk}/manual-pass/",
            {"level_id": self.level.pk, "reason": "Imported from offline exam result."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        progress = LevelProgress.objects.get(student=self.profile, level=self.level)
        self.assertEqual(progress.status, LevelProgress.Status.EXAM_PASSED)
        self.assertEqual(progress.final_exam_attempts_used, 0)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.highest_cleared_level, self.level)
        self.assertEqual(self.profile.current_level, self.level)

        log = AdminStudentActionLog.objects.get(
            student=self.profile,
            action_type=AdminStudentActionLog.ActionType.MANUAL_PASS,
        )
        self.assertEqual(log.reason, "Imported from offline exam result.")

    def test_extend_validity_endpoint_updates_latest_level_purchase_and_logs_reason(self):
        purchase = self.factory.create_purchase(self.profile, self.level, days_valid=15)
        old_expiry = purchase.expires_at

        response = self.admin_client.post(
            f"/api/v1/auth/admin/students/{self.profile.pk}/extend-validity/",
            {"level_id": self.level.pk, "extra_days": 10, "reason": "App downtime compensation."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        purchase.refresh_from_db()
        self.assertGreater(purchase.expires_at, old_expiry)
        self.assertEqual(purchase.extended_by_days, 10)
        self.assertEqual(purchase.extended_by, self.admin)

        log = AdminStudentActionLog.objects.get(
            student=self.profile,
            action_type=AdminStudentActionLog.ActionType.EXTEND_VALIDITY,
        )
        self.assertEqual(log.reason, "App downtime compensation.")
        self.assertEqual(log.purchase, purchase)

    def test_admin_detail_includes_action_history(self):
        self.admin_client.post(
            f"/api/v1/auth/admin/students/{self.profile.pk}/manual-pass/",
            {"level_id": self.level.pk, "reason": "Imported from offline exam result."},
            format="json",
        )

        response = self.admin_client.get(f"/api/v1/auth/admin/students/{self.profile.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["admin_action_history"]), 1)
        self.assertEqual(response.data["admin_action_history"][0]["action_type"], "manual_pass")

    def test_student_cannot_access_admin_action_endpoints(self):
        response = self.student_client.post(
            f"/api/v1/auth/admin/students/{self.profile.pk}/manual-pass/",
            {"level_id": self.level.pk, "reason": "Nope."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_send_reminder_endpoint_creates_notification(self):
        response = self.admin_client.post(
            f"/api/v1/auth/admin/students/{self.profile.pk}/send-reminder/",
            {"message": "Please come back and finish your pending lessons."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Reminder sent successfully.")
        notification = Notification.objects.get(user=self.student_user)
        self.assertEqual(notification.title, "Engagement Reminder")
        self.assertIn("finish your pending lessons", notification.message)
