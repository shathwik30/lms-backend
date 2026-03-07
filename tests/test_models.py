"""
Tests for model __str__, properties, constraints, and managers across all apps.
"""

from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from apps.analytics.models import DailyRevenue, LevelAnalytics
from apps.certificates.models import Certificate
from apps.courses.models import Bookmark, Resource, Session
from apps.doubts.models import DoubtReply, DoubtTicket
from apps.exams.models import (
    AttemptQuestion,
    Exam,
    ExamAttempt,
    ProctoringViolation,
    Question,
)
from apps.feedback.models import SessionFeedback
from apps.home.models import Banner
from apps.levels.models import Level
from apps.notifications.models import Notification
from apps.payments.models import PaymentTransaction, Purchase
from apps.progress.models import CourseProgress, LevelProgress, SessionProgress
from apps.users.models import IssueReport, User, UserPreference
from core.test_utils import TestFactory


class UserModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_user_str(self):
        user, _ = self.factory.create_student(email="alice@test.com")
        self.assertEqual(str(user), "alice@test.com")

    def test_admin_str(self):
        admin = self.factory.create_admin(email="admin@test.com")
        self.assertEqual(str(admin), "admin@test.com")

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="pass123")

    def test_superuser_defaults(self):
        admin = User.objects.create_superuser(email="super@test.com", password="pass123", full_name="Super")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_admin)
        self.assertFalse(admin.is_student)

    def test_student_profile_str(self):
        user, profile = self.factory.create_student(email="bob@test.com")
        self.assertEqual(str(profile), "Profile: bob@test.com")

    def test_issue_report_str(self):
        user, _ = self.factory.create_student()
        report = IssueReport.objects.create(user=user, subject="Test Issue", description="Desc")
        self.assertEqual(str(report), f"{user.email}: Test Issue")

    def test_user_preference_str(self):
        user, _ = self.factory.create_student()
        pref = UserPreference.objects.create(user=user)
        self.assertEqual(str(pref), f"Preferences: {user.email}")

    def test_user_preference_defaults(self):
        user, _ = self.factory.create_student()
        pref = UserPreference.objects.create(user=user)
        self.assertTrue(pref.push_notifications)
        self.assertTrue(pref.email_notifications)
        self.assertTrue(pref.doubt_reply_notifications)
        self.assertTrue(pref.exam_result_notifications)
        self.assertTrue(pref.promotional_notifications)


class LevelModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_level_str(self):
        level = self.factory.create_level(order=3, name="Advanced")
        self.assertEqual(str(level), "Level 3: Advanced")

    def test_level_ordering(self):
        l2 = self.factory.create_level(order=2)
        l1 = self.factory.create_level(order=1)
        levels = list(Level.objects.all())
        self.assertEqual(levels[0], l1)
        self.assertEqual(levels[1], l2)

    def test_level_defaults(self):
        level = self.factory.create_level()
        self.assertTrue(level.is_active)
        self.assertEqual(level.max_final_exam_attempts, 3)
        self.assertEqual(level.validity_days, 365)

    def test_week_str(self):
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        week = self.factory.create_week(course, order=1, name="Week 1")
        self.assertEqual(str(week), f"{course.title} → Week 1")

    def test_week_level_property(self):
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        week = self.factory.create_week(course)
        self.assertEqual(week.level, level)

    def test_week_unique_constraint(self):
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        self.factory.create_week(course, order=1)
        with self.assertRaises(IntegrityError):
            self.factory.create_week(course, order=1, name="Duplicate")


class CourseModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_course_str(self):
        level = self.factory.create_level()
        course = self.factory.create_course(level, title="Physics 101")
        self.assertEqual(str(course), "Physics 101")

    def test_session_str(self):
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        week = self.factory.create_week(course)
        session = self.factory.create_session(week, order=1)
        self.assertEqual(str(session), "Session 1")

    def test_session_types(self):
        self.assertEqual(Session.SessionType.VIDEO, "video")
        self.assertEqual(Session.SessionType.RESOURCE, "resource")
        self.assertEqual(Session.SessionType.PRACTICE_EXAM, "practice_exam")
        self.assertEqual(Session.SessionType.PROCTORED_EXAM, "proctored_exam")

    def test_bookmark_str(self):
        user, profile = self.factory.create_student()
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        week = self.factory.create_week(course)
        session = self.factory.create_session(week)
        bookmark = Bookmark.objects.create(student=profile, session=session)
        self.assertIn(user.email, str(bookmark))
        self.assertIn(session.title, str(bookmark))

    def test_bookmark_unique_constraint(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        week = self.factory.create_week(course)
        session = self.factory.create_session(week)
        Bookmark.objects.create(student=profile, session=session)
        with self.assertRaises(IntegrityError):
            Bookmark.objects.create(student=profile, session=session)

    def test_resource_str(self):
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        week = self.factory.create_week(course)
        session = self.factory.create_session(week)
        resource = Resource.objects.create(
            session=session,
            title="Notes PDF",
            file_url="https://example.com/notes.pdf",
            resource_type=Resource.ResourceType.PDF,
        )
        self.assertEqual(str(resource), "Notes PDF")

    def test_resource_check_constraint_rejects_orphan(self):
        with self.assertRaises(IntegrityError):
            Resource.objects.create(
                title="Orphan",
                file_url="https://example.com/orphan.pdf",
                resource_type=Resource.ResourceType.PDF,
            )


class ExamModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_question_str(self):
        level = self.factory.create_level()
        q, _ = self.factory.create_question(level)
        self.assertIn("Q#", str(q))
        self.assertIn("medium", str(q))

    def test_option_str(self):
        level = self.factory.create_level()
        q, _ = self.factory.create_question(level)
        option = q.options.first()
        self.assertIn("Option for Q#", str(option))

    def test_exam_str(self):
        level = self.factory.create_level()
        exam = self.factory.create_exam(level)
        self.assertIn(level.name, str(exam))

    def test_exam_types(self):
        self.assertEqual(Exam.ExamType.WEEKLY, "weekly")
        self.assertEqual(Exam.ExamType.LEVEL_FINAL, "level_final")
        self.assertEqual(Exam.ExamType.ONBOARDING, "onboarding")

    def test_exam_attempt_str(self):
        user, profile = self.factory.create_student()
        level = self.factory.create_level()
        exam = self.factory.create_exam(level)
        attempt = ExamAttempt.objects.create(student=profile, exam=exam, total_marks=20)
        self.assertIn(exam.title, str(attempt))

    def test_attempt_question_str(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        q, _ = self.factory.create_question(level)
        exam = self.factory.create_exam(level)
        attempt = ExamAttempt.objects.create(student=profile, exam=exam, total_marks=20)
        aq = AttemptQuestion.objects.create(attempt=attempt, question=q, order=1)
        self.assertIn(f"Q#{q.pk}", str(aq))
        self.assertIn(f"Attempt #{attempt.pk}", str(aq))

    def test_attempt_question_unique_constraint(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        q, _ = self.factory.create_question(level)
        exam = self.factory.create_exam(level)
        attempt = ExamAttempt.objects.create(student=profile, exam=exam, total_marks=20)
        AttemptQuestion.objects.create(attempt=attempt, question=q, order=1)
        with self.assertRaises(IntegrityError):
            AttemptQuestion.objects.create(attempt=attempt, question=q, order=2)

    def test_proctoring_violation_str(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        exam = self.factory.create_exam(level)
        attempt = ExamAttempt.objects.create(student=profile, exam=exam, total_marks=20)
        violation = ProctoringViolation.objects.create(
            attempt=attempt,
            violation_type=ProctoringViolation.ViolationType.TAB_SWITCH,
            warning_number=1,
        )
        self.assertIn("tab_switch", str(violation))
        self.assertIn("Warning 1", str(violation))

    def test_question_types(self):
        self.assertEqual(Question.QuestionType.MCQ, "mcq")
        self.assertEqual(Question.QuestionType.MULTI_MCQ, "multi_mcq")
        self.assertEqual(Question.QuestionType.FILL_BLANK, "fill_blank")

    def test_question_difficulty_choices(self):
        self.assertEqual(Question.Difficulty.EASY, "easy")
        self.assertEqual(Question.Difficulty.MEDIUM, "medium")
        self.assertEqual(Question.Difficulty.HARD, "hard")


class PaymentModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_purchase_str(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        purchase = self.factory.create_purchase(profile, level)
        self.assertIn(level.name, str(purchase))

    def test_purchase_is_valid_active(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        purchase = self.factory.create_purchase(profile, level)
        self.assertTrue(purchase.is_valid)

    def test_purchase_is_valid_expired(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        purchase = self.factory.create_expired_purchase(profile, level)
        self.assertFalse(purchase.is_valid)

    def test_purchase_is_valid_revoked(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        purchase = self.factory.create_purchase(profile, level)
        purchase.status = Purchase.Status.REVOKED
        purchase.save(update_fields=["status"])
        self.assertFalse(purchase.is_valid)

    def test_transaction_str(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        txn = PaymentTransaction.objects.create(
            student=profile,
            level=level,
            gateway_order_id="order_123",
            amount=Decimal("999.00"),
        )
        self.assertIn("order_123", str(txn))
        self.assertIn("pending", str(txn))

    def test_purchase_status_choices(self):
        self.assertEqual(Purchase.Status.ACTIVE, "active")
        self.assertEqual(Purchase.Status.EXPIRED, "expired")
        self.assertEqual(Purchase.Status.REVOKED, "revoked")


class ProgressModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_session_progress_str(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        week = self.factory.create_week(course)
        session = self.factory.create_session(week)
        sp = SessionProgress.objects.create(student=profile, session=session)
        self.assertIn(session.title, str(sp))

    def test_course_progress_str(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        cp = CourseProgress.objects.create(student=profile, course=course)
        self.assertIn(course.title, str(cp))
        self.assertIn("not_started", str(cp))

    def test_level_progress_str(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        lp = LevelProgress.objects.create(student=profile, level=level)
        self.assertIn(level.name, str(lp))

    def test_session_progress_unique_constraint(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        week = self.factory.create_week(course)
        session = self.factory.create_session(week)
        SessionProgress.objects.create(student=profile, session=session)
        with self.assertRaises(IntegrityError):
            SessionProgress.objects.create(student=profile, session=session)

    def test_course_progress_unique_constraint(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        CourseProgress.objects.create(student=profile, course=course)
        with self.assertRaises(IntegrityError):
            CourseProgress.objects.create(student=profile, course=course)

    def test_level_progress_unique_constraint(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        LevelProgress.objects.create(student=profile, level=level)
        with self.assertRaises(IntegrityError):
            LevelProgress.objects.create(student=profile, level=level)

    def test_level_progress_status_choices(self):
        self.assertEqual(LevelProgress.Status.NOT_STARTED, "not_started")
        self.assertEqual(LevelProgress.Status.IN_PROGRESS, "in_progress")
        self.assertEqual(LevelProgress.Status.SYLLABUS_COMPLETE, "syllabus_complete")
        self.assertEqual(LevelProgress.Status.EXAM_PASSED, "exam_passed")
        self.assertEqual(LevelProgress.Status.EXAM_FAILED, "exam_failed")


class DoubtModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_doubt_ticket_str(self):
        _, profile = self.factory.create_student()
        ticket = DoubtTicket.objects.create(
            student=profile,
            title="My Question",
            description="Details",
            context_type=DoubtTicket.ContextType.TOPIC,
        )
        self.assertIn("My Question", str(ticket))

    def test_doubt_reply_str(self):
        user, profile = self.factory.create_student()
        ticket = DoubtTicket.objects.create(
            student=profile,
            title="Q",
            description="D",
            context_type=DoubtTicket.ContextType.TOPIC,
        )
        reply = DoubtReply.objects.create(ticket=ticket, author=user, message="Answer")
        self.assertIn(f"Doubt #{ticket.pk}", str(reply))

    def test_doubt_status_choices(self):
        self.assertEqual(DoubtTicket.Status.OPEN, "open")
        self.assertEqual(DoubtTicket.Status.IN_REVIEW, "in_review")
        self.assertEqual(DoubtTicket.Status.ANSWERED, "answered")
        self.assertEqual(DoubtTicket.Status.CLOSED, "closed")

    def test_doubt_context_types(self):
        self.assertEqual(DoubtTicket.ContextType.SESSION, "session")
        self.assertEqual(DoubtTicket.ContextType.TOPIC, "topic")
        self.assertEqual(DoubtTicket.ContextType.EXAM_QUESTION, "exam_question")


class FeedbackModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_feedback_str(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        week = self.factory.create_week(course)
        session = self.factory.create_session(week)
        feedback = SessionFeedback.objects.create(
            student=profile,
            session=session,
            rating=5,
            difficulty_rating=3,
            clarity_rating=4,
        )
        self.assertIn(session.title, str(feedback))

    def test_feedback_unique_constraint(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        course = self.factory.create_course(level)
        week = self.factory.create_week(course)
        session = self.factory.create_session(week)
        SessionFeedback.objects.create(
            student=profile,
            session=session,
            rating=5,
            difficulty_rating=3,
            clarity_rating=4,
        )
        with self.assertRaises(IntegrityError):
            SessionFeedback.objects.create(
                student=profile,
                session=session,
                rating=3,
                difficulty_rating=2,
                clarity_rating=3,
            )


class AnalyticsModelTests(TestCase):
    def test_daily_revenue_str(self):
        dr = DailyRevenue.objects.create(date="2026-01-01")
        self.assertIn("2026-01-01", str(dr))

    def test_level_analytics_str(self):
        factory = TestFactory()
        level = factory.create_level()
        la = LevelAnalytics.objects.create(level=level, date="2026-01-01")
        self.assertIn(level.name, str(la))

    def test_level_analytics_unique_constraint(self):
        factory = TestFactory()
        level = factory.create_level()
        LevelAnalytics.objects.create(level=level, date="2026-01-01")
        with self.assertRaises(IntegrityError):
            LevelAnalytics.objects.create(level=level, date="2026-01-01")


class NotificationModelTests(TestCase):
    def test_notification_str(self):
        factory = TestFactory()
        user, _ = factory.create_student()
        notif = Notification.objects.create(user=user, title="Hello", message="World")
        self.assertIn(user.email, str(notif))
        self.assertIn("Hello", str(notif))

    def test_notification_defaults(self):
        factory = TestFactory()
        user, _ = factory.create_student()
        notif = Notification.objects.create(user=user, title="Test", message="Msg")
        self.assertFalse(notif.is_read)
        self.assertEqual(notif.notification_type, Notification.NotificationType.GENERAL)

    def test_notification_types(self):
        self.assertEqual(Notification.NotificationType.PURCHASE, "purchase")
        self.assertEqual(Notification.NotificationType.EXAM_RESULT, "exam_result")
        self.assertEqual(Notification.NotificationType.DOUBT_REPLY, "doubt_reply")


class CertificateModelTests(TestCase):
    def setUp(self):
        self.factory = TestFactory()

    def test_certificate_str(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        cert = Certificate.objects.create(student=profile, level=level)
        self.assertIn(profile.user.email, str(cert))
        self.assertIn(level.name, str(cert))

    def test_certificate_auto_generates_number(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        cert = Certificate.objects.create(student=profile, level=level)
        self.assertTrue(cert.certificate_number.startswith("CERT-"))
        self.assertTrue(len(cert.certificate_number) > 10)

    def test_certificate_unique_per_student_level(self):
        _, profile = self.factory.create_student()
        level = self.factory.create_level()
        Certificate.objects.create(student=profile, level=level)
        with self.assertRaises(IntegrityError):
            Certificate.objects.create(student=profile, level=level)


class BannerModelTests(TestCase):
    def test_banner_str(self):
        banner = Banner.objects.create(
            title="Welcome",
            image_url="https://example.com/banner.jpg",
        )
        self.assertEqual(str(banner), "Welcome")

    def test_banner_defaults(self):
        banner = Banner.objects.create(
            title="Test",
            image_url="https://example.com/b.jpg",
        )
        self.assertTrue(banner.is_active)
        self.assertEqual(banner.order, 0)
        self.assertEqual(banner.link_type, Banner.LinkType.NONE)

    def test_banner_ordering(self):
        b2 = Banner.objects.create(
            title="Second",
            image_url="https://example.com/2.jpg",
            order=2,
        )
        b1 = Banner.objects.create(
            title="First",
            image_url="https://example.com/1.jpg",
            order=1,
        )
        banners = list(Banner.objects.all())
        self.assertEqual(banners[0], b1)
        self.assertEqual(banners[1], b2)
