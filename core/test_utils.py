"""
Shared test factories for creating test data across all apps.

Usage:
    from core.test_utils import TestFactory

    factory = TestFactory()
    student_user, profile = factory.create_student()
    level = factory.create_level(order=1)
    ...
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.courses.models import Course, Session
from apps.exams.models import Exam, Option, Question
from apps.feedback.models import SessionFeedback
from apps.levels.models import Level, Week
from apps.payments.models import Purchase
from apps.progress.models import LevelProgress, SessionProgress

User = get_user_model()


class TestFactory:
    def create_student(self, email="student@test.com", password="testpass123"):
        user = User.objects.create_user(
            email=email,
            password=password,
            full_name="Test Student",
        )
        # Signal auto-creates StudentProfile
        return user, user.student_profile

    def create_admin(self, email="admin@test.com", password="testpass123"):
        return User.objects.create_superuser(
            email=email,
            password=password,
            full_name="Test Admin",
        )

    def get_auth_client(self, user):
        client = APIClient()
        token = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        return client

    def create_level(self, order=1, name=None, passing_pct=50, price=999, validity_days=365):
        return Level.objects.create(
            name=name or f"Level {order}",
            order=order,
            passing_percentage=passing_pct,
            price=price,
            validity_days=validity_days,
        )

    def create_course(self, level, title=None):
        return Course.objects.create(
            level=level,
            title=title or f"{level.name} Course",
        )

    def create_week(self, course, order=1, name=None):
        return Week.objects.create(
            course=course,
            name=name or f"Week {order}",
            order=order,
        )

    def create_session(self, week, order=1, duration=2700, session_type=Session.SessionType.VIDEO):
        return Session.objects.create(
            week=week,
            title=f"Session {order}",
            video_url="https://example.com/video.mp4" if session_type == Session.SessionType.VIDEO else "",
            duration_seconds=duration,
            order=order,
            session_type=session_type,
        )

    def create_question(self, exam, level=None, marks=4):
        q = Question.objects.create(
            exam=exam,
            level=level or exam.level,
            text=f"Test question for {(level or exam.level).name}?",
            difficulty="medium",
            marks=marks,
        )
        correct = Option.objects.create(question=q, text="Correct", is_correct=True)
        Option.objects.create(question=q, text="Wrong 1", is_correct=False)
        Option.objects.create(question=q, text="Wrong 2", is_correct=False)
        Option.objects.create(question=q, text="Wrong 3", is_correct=False)
        return q, correct

    def create_exam(
        self,
        level,
        week=None,
        course=None,
        exam_type=Exam.ExamType.LEVEL_FINAL,
        num_questions=5,
        duration=60,
        passing_pct=50,
    ):
        return Exam.objects.create(
            level=level,
            week=week,
            course=course,
            exam_type=exam_type,
            title=f"{level.name} {exam_type} Exam",
            duration_minutes=duration,
            total_marks=num_questions * 4,
            passing_percentage=passing_pct,
            num_questions=num_questions,
        )

    def create_purchase(self, profile, level, days_valid=None):
        if days_valid is None:
            days_valid = level.validity_days
        return Purchase.objects.create(
            student=profile,
            level=level,
            amount_paid=level.price,
            expires_at=timezone.now() + timedelta(days=days_valid),
        )

    def create_expired_purchase(self, profile, level):
        return Purchase.objects.create(
            student=profile,
            level=level,
            amount_paid=level.price,
            expires_at=timezone.now() - timedelta(days=1),
            status=Purchase.Status.ACTIVE,
        )

    def complete_session(self, profile, session):
        """Mark a session as watched + submit feedback (for video sessions)."""
        SessionProgress.objects.create(
            student=profile,
            session=session,
            watched_seconds=session.duration_seconds,
            is_completed=True,
            completed_at=timezone.now(),
        )
        if session.session_type == Session.SessionType.VIDEO:
            SessionFeedback.objects.create(
                student=profile,
                session=session,
                rating=4,
                difficulty_rating=3,
                clarity_rating=5,
            )

    def pass_level(self, profile, level):
        """Mark a level as passed in LevelProgress + update profile."""
        LevelProgress.objects.update_or_create(
            student=profile,
            level=level,
            defaults={
                "status": LevelProgress.Status.EXAM_PASSED,
                "completed_at": timezone.now(),
            },
        )
        profile.highest_cleared_level = level
        profile.save()

    def setup_full_level(self, order=1, num_sessions=2, num_questions=5):
        """Create a complete level with course, weeks, sessions, questions, exam."""
        level = self.create_level(order=order)
        course = self.create_course(level)
        week = self.create_week(course, order=1)
        sessions = [self.create_session(week, order=i + 1) for i in range(num_sessions)]
        exam = self.create_exam(level, num_questions=num_questions)
        questions_and_options = [self.create_question(exam) for _ in range(num_questions)]
        return {
            "level": level,
            "course": course,
            "week": week,
            "sessions": sessions,
            "questions": questions_and_options,
            "exam": exam,
        }
