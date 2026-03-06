from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.courses.models import Course, Resource, Session
from apps.exams.models import Exam, Option, Question
from apps.levels.models import Level, Week

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the database with sample data for development and testing"

    def handle(self, *args, **options):
        self.stdout.write("Seeding database...")

        # ── Super Admin ──
        admin, created = User.objects.get_or_create(
            email="admin@lms.com",
            defaults={
                "full_name": "Super Admin",
                "is_admin": True,
                "is_staff": True,
                "is_superuser": True,
                "is_student": False,
            },
        )
        if created:
            admin.set_password("admin123")
            admin.save()
            self.stdout.write(self.style.SUCCESS("  Created admin: admin@lms.com / admin123"))
        else:
            self.stdout.write("  Admin already exists, skipping.")

        # ── Test Student ──
        student, created = User.objects.get_or_create(
            email="student@lms.com",
            defaults={
                "full_name": "Test Student",
                "phone": "9999999999",
                "is_student": True,
            },
        )
        if created:
            student.set_password("student123")
            student.save()
            self.stdout.write(self.style.SUCCESS("  Created student: student@lms.com / student123"))
        else:
            self.stdout.write("  Student already exists, skipping.")

        # ── Levels ──
        levels_data = [
            {
                "name": "Foundation",
                "order": 1,
                "passing_percentage": 50,
                "description": "Basic concepts and fundamentals of Physics, Chemistry & Maths.",
            },
            {
                "name": "Intermediate",
                "order": 2,
                "passing_percentage": 55,
                "description": "Application-level problems and deeper understanding.",
            },
            {
                "name": "Advanced",
                "order": 3,
                "passing_percentage": 60,
                "description": "Competition-level problems and advanced techniques.",
            },
            {"name": "Elite", "order": 4, "passing_percentage": 65, "description": "IIT-JEE Advanced level mastery."},
        ]

        levels = []
        for ld in levels_data:
            level, _ = Level.objects.get_or_create(order=ld["order"], defaults=ld)
            levels.append(level)
        self.stdout.write(self.style.SUCCESS(f"  Created {len(levels)} levels"))

        # ── Weeks ──
        weeks_data = {
            0: ["Kinematics", "Laws of Motion", "Work & Energy"],
            1: ["Rotational Motion", "Gravitation", "Thermodynamics"],
            2: ["Electrostatics", "Current Electricity", "Magnetism"],
            3: ["Optics", "Modern Physics", "Nuclear Physics"],
        }

        all_weeks = []
        for idx, level in enumerate(levels):
            for w_order, w_name in enumerate(weeks_data[idx], start=1):
                week, _ = Week.objects.get_or_create(
                    level=level,
                    order=w_order,
                    defaults={"name": f"Week {w_order}: {w_name}"},
                )
                all_weeks.append(week)
        self.stdout.write(self.style.SUCCESS(f"  Created {len(all_weeks)} weeks"))

        # ── Courses ──
        for level in levels:
            Course.objects.get_or_create(
                level=level,
                defaults={
                    "title": f"{level.name} Complete Course",
                    "description": f"Full syllabus course for {level.name} level.",
                    "price": 499 + (level.order * 500),
                    "validity_days": 45,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"  Created {len(levels)} courses"))

        # ── Sessions (3 per week) ──
        session_count = 0
        for week in all_weeks:
            for s_order in range(1, 4):
                session, created = Session.objects.get_or_create(
                    week=week,
                    order=s_order,
                    defaults={
                        "title": f"{week.name} - Lecture {s_order}",
                        "description": f"Video lecture {s_order} for {week.name}.",
                        "video_url": f"https://example.com/videos/{week.level.order}/{week.order}/{s_order}.mp4",
                        "duration_seconds": 2700,
                    },
                )
                if created:
                    session_count += 1

                    # Add a PDF resource per session
                    Resource.objects.get_or_create(
                        session=session,
                        title=f"{session.title} - Notes",
                        defaults={
                            "file_url": f"https://example.com/notes/{week.level.order}/{week.order}/{s_order}.pdf",
                            "resource_type": "pdf",
                        },
                    )
        self.stdout.write(self.style.SUCCESS(f"  Created {session_count} sessions with resources"))

        # ── Questions (10 per level, with 4 options each) ──
        question_count = 0
        for level in levels:
            for q_num in range(1, 11):
                q, created = Question.objects.get_or_create(
                    level=level,
                    text=f"Sample question {q_num} for {level.name} level?",
                    defaults={
                        "difficulty": ["easy", "medium", "hard"][q_num % 3],
                        "marks": 4,
                    },
                )
                if created:
                    question_count += 1
                    for opt_num in range(1, 5):
                        Option.objects.create(
                            question=q,
                            text=f"Option {opt_num}",
                            is_correct=(opt_num == 1),
                        )
        self.stdout.write(self.style.SUCCESS(f"  Created {question_count} questions with options"))

        # ── Exams (1 level final per level + 1 weekly per first week) ──
        exam_count = 0
        for level in levels:
            _, created = Exam.objects.get_or_create(
                level=level,
                exam_type="level_final",
                defaults={
                    "title": f"{level.name} Final Exam",
                    "duration_minutes": 60,
                    "total_marks": 40,
                    "passing_percentage": level.passing_percentage,
                    "num_questions": 10,
                },
            )
            if created:
                exam_count += 1

            first_week = level.weeks.order_by("order").first()
            if first_week:
                _, created = Exam.objects.get_or_create(
                    level=level,
                    week=first_week,
                    exam_type="weekly",
                    defaults={
                        "title": f"{first_week.name} Quiz",
                        "duration_minutes": 30,
                        "total_marks": 20,
                        "passing_percentage": 40,
                        "num_questions": 5,
                    },
                )
                if created:
                    exam_count += 1

        self.stdout.write(self.style.SUCCESS(f"  Created {exam_count} exams"))

        self.stdout.write(self.style.SUCCESS("\nSeed complete!"))
        self.stdout.write(self.style.SUCCESS("  Admin login:   admin@lms.com / admin123"))
        self.stdout.write(self.style.SUCCESS("  Student login:  student@lms.com / student123"))
