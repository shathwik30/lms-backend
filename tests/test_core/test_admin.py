from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from apps.analytics.admin import (
    DailyRevenueAdmin,
    LevelAnalyticsAdmin,
)
from apps.analytics.models import DailyRevenue, LevelAnalytics
from apps.courses.admin import CourseAdmin, SessionAdmin
from apps.courses.models import Course, Session
from apps.doubts.admin import DoubtTicketAdmin
from apps.doubts.models import DoubtTicket
from apps.exams.admin import ExamAdmin, ExamAttemptAdmin
from apps.exams.models import ExamAttempt
from apps.feedback.admin import SessionFeedbackAdmin
from apps.feedback.models import SessionFeedback
from apps.levels.admin import LevelAdmin, WeekAdmin
from apps.levels.models import Level, Week
from apps.payments.admin import PurchaseAdmin
from apps.payments.models import Purchase
from apps.progress.admin import (
    LevelProgressAdmin,
    SessionProgressAdmin,
)
from apps.progress.models import (
    LevelProgress,
    SessionProgress,
)
from apps.users.admin import UserAdmin
from apps.users.models import User
from core.test_utils import TestFactory


class AdminSiteTestMixin:
    """Provides admin site and request factory."""

    def setUp(self):
        self.site = AdminSite()
        self.rf = RequestFactory()
        self.factory = TestFactory()
        self.admin_user = self.factory.create_admin()
        self.request = self.rf.get("/admin/")
        self.request.user = self.admin_user


class CsvExportTests(AdminSiteTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.data = self.factory.setup_full_level(order=1)

    def test_export_levels_csv(self):
        ma = LevelAdmin(Level, self.site)
        qs = Level.objects.all()
        response = ma.export_as_csv(self.request, qs)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "text/csv",
        )
        content = response.content.decode()
        self.assertIn("name", content)
        self.assertIn(self.data["level"].name, content)

    def test_export_purchases_csv(self):
        _, profile = self.factory.create_student()
        self.factory.create_purchase(
            profile,
            self.data["level"],
        )
        ma = PurchaseAdmin(Purchase, self.site)
        qs = Purchase.objects.all()
        response = ma.export_as_csv(self.request, qs)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("amount_paid", content)

    def test_export_empty_queryset(self):
        ma = LevelAdmin(Level, self.site)
        qs = Level.objects.none()
        response = ma.export_as_csv(self.request, qs)
        self.assertEqual(response.status_code, 200)
        lines = (
            response.content.decode()
            .strip()
            .split(
                "\n",
            )
        )
        self.assertEqual(len(lines), 1)  # header only


class BulkActionTests(AdminSiteTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.data = self.factory.setup_full_level(order=1)

    def test_make_levels_inactive(self):
        ma = LevelAdmin(Level, self.site)
        qs = Level.objects.all()
        from core.admin import make_inactive

        make_inactive(ma, self.request, qs)
        self.assertFalse(
            Level.objects.get(
                pk=self.data["level"].pk,
            ).is_active,
        )

    def test_make_levels_active(self):
        Level.objects.all().update(is_active=False)
        ma = LevelAdmin(Level, self.site)
        qs = Level.objects.all()
        from core.admin import make_active

        make_active(ma, self.request, qs)
        self.assertTrue(
            Level.objects.get(
                pk=self.data["level"].pk,
            ).is_active,
        )

    def test_revoke_purchases(self):
        _, profile = self.factory.create_student()
        purchase = self.factory.create_purchase(
            profile,
            self.data["level"],
        )
        ma = PurchaseAdmin(Purchase, self.site)
        qs = Purchase.objects.filter(pk=purchase.pk)
        ma.mark_revoked(self.request, qs)
        purchase.refresh_from_db()
        self.assertEqual(
            purchase.status,
            Purchase.Status.REVOKED,
        )

    def test_mark_doubts_closed(self):
        _, profile = self.factory.create_student()
        ticket = DoubtTicket.objects.create(
            student=profile,
            title="Test",
            description="Desc",
            context_type=DoubtTicket.ContextType.TOPIC,
        )
        ma = DoubtTicketAdmin(DoubtTicket, self.site)
        qs = DoubtTicket.objects.filter(pk=ticket.pk)
        ma.mark_closed(self.request, qs)
        ticket.refresh_from_db()
        self.assertEqual(
            ticket.status,
            DoubtTicket.Status.CLOSED,
        )

    def test_mark_doubts_answered(self):
        _, profile = self.factory.create_student()
        ticket = DoubtTicket.objects.create(
            student=profile,
            title="Test",
            description="Desc",
            context_type=DoubtTicket.ContextType.TOPIC,
        )
        ma = DoubtTicketAdmin(DoubtTicket, self.site)
        qs = DoubtTicket.objects.filter(pk=ticket.pk)
        ma.mark_answered(self.request, qs)
        ticket.refresh_from_db()
        self.assertEqual(
            ticket.status,
            DoubtTicket.Status.ANSWERED,
        )


class ComputedFieldTests(AdminSiteTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.data = self.factory.setup_full_level(
            order=1,
            num_sessions=2,
            num_questions=5,
        )
        _, self.profile = self.factory.create_student()

    def test_level_course_count(self):
        ma = LevelAdmin(Level, self.site)
        self.assertEqual(
            ma.course_count(self.data["level"]),
            1,
        )

    def test_level_question_count(self):
        ma = LevelAdmin(Level, self.site)
        self.assertEqual(
            ma.question_count(self.data["level"]),
            5,
        )

    def test_week_session_count(self):
        ma = WeekAdmin(Week, self.site)
        self.assertEqual(
            ma.session_count(self.data["week"]),
            2,
        )

    def test_course_week_count(self):
        ma = CourseAdmin(Course, self.site)
        self.assertEqual(
            ma.week_count(self.data["course"]),
            1,
        )

    def test_session_duration_display(self):
        ma = SessionAdmin(Session, self.site)
        session = self.data["sessions"][0]
        result = ma.duration_display(session)
        self.assertIn("m", result)

    def test_exam_attempt_count(self):
        ma = ExamAdmin(
            type(self.data["exam"]),
            self.site,
        )
        self.assertEqual(
            ma.attempt_count(self.data["exam"]),
            0,
        )

    def test_purchase_validity_badge_valid(self):
        ma = PurchaseAdmin(Purchase, self.site)
        p = self.factory.create_purchase(
            self.profile,
            self.data["level"],
        )
        self.assertTrue(ma.validity_badge(p))

    def test_purchase_validity_badge_expired(self):
        ma = PurchaseAdmin(Purchase, self.site)
        p = self.factory.create_expired_purchase(
            self.profile,
            self.data["level"],
        )
        self.assertFalse(ma.validity_badge(p))

    def test_watch_progress_display(self):
        ma = SessionProgressAdmin(
            SessionProgress,
            self.site,
        )
        session = self.data["sessions"][0]
        sp = SessionProgress.objects.create(
            student=self.profile,
            session=session,
            watched_seconds=1350,
        )
        result = ma.watch_progress(sp)
        self.assertIn("50%", result)

    def test_watch_progress_zero_duration(self):
        ma = SessionProgressAdmin(
            SessionProgress,
            self.site,
        )
        session = Session.objects.create(
            week=self.data["week"],
            title="Zero",
            video_url="https://x.com/v",
            duration_seconds=0,
            order=99,
        )
        sp = SessionProgress.objects.create(
            student=self.profile,
            session=session,
        )
        self.assertEqual(ma.watch_progress(sp), "—")

    def test_exam_score_display(self):
        ma = ExamAttemptAdmin(ExamAttempt, self.site)
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
            score=15,
        )
        result = ma.score_display(attempt)
        self.assertIn("15", result)
        self.assertIn("75%", result)

    def test_exam_score_display_none(self):
        ma = ExamAttemptAdmin(ExamAttempt, self.site)
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
        )
        self.assertEqual(ma.score_display(attempt), "—")

    def test_pass_badge_passed(self):
        ma = ExamAttemptAdmin(ExamAttempt, self.site)
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
            is_passed=True,
        )
        result = ma.pass_badge(attempt)
        self.assertIn("PASSED", result)

    def test_pass_badge_failed(self):
        ma = ExamAttemptAdmin(ExamAttempt, self.site)
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
            is_passed=False,
        )
        result = ma.pass_badge(attempt)
        self.assertIn("FAILED", result)

    def test_pass_badge_none(self):
        ma = ExamAttemptAdmin(ExamAttempt, self.site)
        attempt = ExamAttempt.objects.create(
            student=self.profile,
            exam=self.data["exam"],
            total_marks=20,
        )
        self.assertEqual(ma.pass_badge(attempt), "—")

    def test_doubt_reply_count(self):
        ma = DoubtTicketAdmin(DoubtTicket, self.site)
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="Test",
            description="Desc",
            context_type=DoubtTicket.ContextType.TOPIC,
        )
        self.assertEqual(ma.reply_count(ticket), 0)

    def test_doubt_title_preview_short(self):
        ma = DoubtTicketAdmin(DoubtTicket, self.site)
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="Short",
            description="Desc",
            context_type=DoubtTicket.ContextType.TOPIC,
        )
        self.assertEqual(
            ma.title_preview(ticket),
            "Short",
        )

    def test_doubt_title_preview_long(self):
        ma = DoubtTicketAdmin(DoubtTicket, self.site)
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="A" * 80,
            description="Desc",
            context_type=DoubtTicket.ContextType.TOPIC,
        )
        result = ma.title_preview(ticket)
        self.assertTrue(result.endswith("..."))
        self.assertEqual(len(result), 63)

    def test_question_text_preview(self):
        from apps.exams.admin import QuestionAdmin  # noqa: F811
        from apps.exams.models import Question

        ma = QuestionAdmin(Question, self.site)
        q = self.data["questions"][0][0]
        result = ma.text_preview(q)
        self.assertIsInstance(result, str)

    def test_feedback_comment_preview_empty(self):
        ma = SessionFeedbackAdmin(
            SessionFeedback,
            self.site,
        )
        fb = SessionFeedback.objects.create(
            student=self.profile,
            session=self.data["sessions"][0],
            overall_rating=4,
            difficulty_rating=3,
            clarity_rating=5,
        )
        self.assertEqual(ma.comment_preview(fb), "—")

    def test_feedback_comment_preview_long(self):
        ma = SessionFeedbackAdmin(
            SessionFeedback,
            self.site,
        )
        fb = SessionFeedback.objects.create(
            student=self.profile,
            session=self.data["sessions"][0],
            overall_rating=4,
            difficulty_rating=3,
            clarity_rating=5,
            comment="X" * 80,
        )
        result = ma.comment_preview(fb)
        self.assertTrue(result.endswith("..."))


class StatusBadgeTests(AdminSiteTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.data = self.factory.setup_full_level(order=1)
        _, self.profile = self.factory.create_student()

    def test_purchase_status_badge(self):
        ma = PurchaseAdmin(Purchase, self.site)
        p = self.factory.create_purchase(
            self.profile,
            self.data["level"],
        )
        result = ma.status_badge(p)
        self.assertIn("Active", result)

    def test_level_progress_status_badge(self):
        ma = LevelProgressAdmin(LevelProgress, self.site)
        lp = LevelProgress.objects.create(
            student=self.profile,
            level=self.data["level"],
            status=LevelProgress.Status.IN_PROGRESS,
        )
        result = ma.status_badge(lp)
        self.assertIn("In Progress", result)

    def test_doubt_status_badge(self):
        ma = DoubtTicketAdmin(DoubtTicket, self.site)
        ticket = DoubtTicket.objects.create(
            student=self.profile,
            title="Test",
            description="Desc",
            context_type=DoubtTicket.ContextType.TOPIC,
        )
        result = ma.status_badge(ticket)
        self.assertIn("Open", result)

    def test_user_role_badge_admin(self):
        ma = UserAdmin(User, self.site)
        result = ma.role_badge(self.admin_user)
        self.assertIn("Admin", result)

    def test_user_role_badge_student(self):
        ma = UserAdmin(User, self.site)
        user, _ = self.factory.create_student(
            email="badge@test.com",
        )
        result = ma.role_badge(user)
        self.assertIn("Student", result)

    def test_analytics_pass_rate(self):
        ma = LevelAnalyticsAdmin(
            LevelAnalytics,
            self.site,
        )
        la = LevelAnalytics.objects.create(
            level=self.data["level"],
            date="2026-01-01",
            total_passes=8,
            total_failures=2,
        )
        result = ma.pass_rate(la)
        self.assertIn("80%", result)

    def test_analytics_pass_rate_zero(self):
        ma = LevelAnalyticsAdmin(
            LevelAnalytics,
            self.site,
        )
        la = LevelAnalytics.objects.create(
            level=self.data["level"],
            date="2026-01-02",
        )
        self.assertEqual(ma.pass_rate(la), "—")

    def test_revenue_display(self):
        ma = DailyRevenueAdmin(DailyRevenue, self.site)
        dr = DailyRevenue.objects.create(
            date="2026-01-01",
            total_revenue=5000,
            total_transactions=10,
        )
        result = ma.total_revenue_display(dr)
        self.assertIn("5000", result)


class CsvInjectionSecurityTests(TestCase):
    """Tests for _sanitize_csv_value CSV injection prevention."""

    def test_formula_value_escaped(self):
        from core.admin import _sanitize_csv_value

        self.assertEqual(
            _sanitize_csv_value("=1+1"),
            "'=1+1",
        )

    def test_plus_sign_escaped(self):
        from core.admin import _sanitize_csv_value

        self.assertEqual(
            _sanitize_csv_value("+cmd|' /C calc'!A0"),
            "'+cmd|' /C calc'!A0",
        )

    def test_at_sign_escaped(self):
        from core.admin import _sanitize_csv_value

        self.assertEqual(
            _sanitize_csv_value("@SUM(A1:A10)"),
            "'@SUM(A1:A10)",
        )

    def test_normal_value_not_escaped(self):
        from core.admin import _sanitize_csv_value

        self.assertEqual(
            _sanitize_csv_value("Hello World"),
            "Hello World",
        )

    def test_none_value_handled(self):
        from core.admin import _sanitize_csv_value

        self.assertEqual(
            _sanitize_csv_value(None),
            "",
        )


class ThrottlingTests(TestCase):
    """Tests for SafeScopedRateThrottle."""

    def setUp(self):
        self.throttle = self._make_throttle()

    @staticmethod
    def _make_throttle():
        from core.throttling import SafeScopedRateThrottle

        return SafeScopedRateThrottle()

    @staticmethod
    def _make_request():
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        return factory.get("/fake/")

    def test_allows_when_no_scope(self):
        """Returns True when the view has no throttle_scope."""
        request = self._make_request()
        view = type("FakeView", (), {})()  # no throttle_scope
        self.assertTrue(
            self.throttle.allow_request(request, view),
        )

    def test_allows_when_scope_has_no_rate(self):
        """Returns True when scope exists but has no configured rate."""
        request = self._make_request()
        view = type(
            "FakeView",
            (),
            {"throttle_scope": "nonexistent_scope_xyz"},
        )()
        self.assertTrue(
            self.throttle.allow_request(request, view),
        )

    def test_get_rate_catches_improperly_configured(self):
        """get_rate() returns None instead of raising ImproperlyConfigured."""
        from core.throttling import SafeScopedRateThrottle

        throttle = SafeScopedRateThrottle()
        throttle.scope = "nonexistent_scope_xyz"
        self.assertIsNone(throttle.get_rate())
