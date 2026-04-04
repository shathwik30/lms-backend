"""
Reseed exam data (exams, questions, options, attempts, proctoring violations).

Clears existing exam-related data and recreates it from scratch,
using the levels, weeks, courses, and students already in the database.

Usage:  python manage.py reseed_exams
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.exams.models import (
    AttemptQuestion,
    Exam,
    ExamAttempt,
    Option,
    ProctoringViolation,
    Question,
)
from apps.levels.models import Level, Week
from apps.users.models import User


class Command(BaseCommand):
    help = "Reseed exam data (exams, questions, options, attempts, violations)"

    def handle(self, *args, **options):
        now = timezone.now()

        # ── Validate prerequisites ──────────────────────────────
        levels = list(Level.objects.order_by("order"))
        weeks = list(Week.objects.select_related("course", "course__level").order_by("course__level__order", "order"))
        profiles = list(
            User.objects.filter(is_staff=False, is_superuser=False)
            .exclude(student_profile=None)
            .values_list("student_profile", flat=True)
        )

        if not levels:
            self.stderr.write("No levels found. Run seed_data first.")
            return
        if not weeks:
            self.stderr.write("No weeks found. Run seed_data first.")
            return

        from apps.users.models import StudentProfile

        profiles = list(StudentProfile.objects.select_related("current_level").order_by("pk"))
        if not profiles:
            self.stderr.write("No student profiles found. Run seed_data first.")
            return

        # ── Wipe existing exam data ─────────────────────────────
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE TABLE proctoring_violations, attempt_questions, "
                "exam_attempts, options, questions, exams RESTART IDENTITY CASCADE"
            )

        self.stdout.write("  Cleared all exam-related tables")

        # ── Question banks ──────────────────────────────────────
        physics_questions = [
            (
                "A ball is thrown vertically upward with velocity 20 m/s. What is the maximum height reached? (g = 10 m/s²)",
                "easy",
                [("20 m", True), ("40 m", False), ("10 m", False), ("30 m", False)],
                "Using v² = u² - 2gh, at max height v=0, so h = u²/2g = 400/20 = 20 m.",
            ),
            (
                "A block of mass 5 kg is placed on a frictionless surface. A horizontal force of 10 N is applied. What is the acceleration?",
                "easy",
                [("2 m/s²", True), ("5 m/s²", False), ("10 m/s²", False), ("1 m/s²", False)],
                "F = ma, so a = F/m = 10/5 = 2 m/s².",
            ),
            (
                "Two blocks of masses 3 kg and 5 kg are connected by a string over a frictionless pulley. Find the acceleration of the system.",
                "medium",
                [("2.45 m/s²", True), ("3.68 m/s²", False), ("4.9 m/s²", False), ("1.22 m/s²", False)],
                "a = (m₂ - m₁)g / (m₁ + m₂) = (5-3)×9.8 / 8 = 2.45 m/s².",
            ),
            (
                "A projectile is fired at 60° with horizontal at 40 m/s. Find the range. (g = 10 m/s²)",
                "medium",
                [("138.6 m", True), ("160 m", False), ("80 m", False), ("120 m", False)],
                "R = u²sin(2θ)/g = 1600 × sin120° / 10 = 138.6 m.",
            ),
            (
                "A satellite orbits Earth at height h = R (R = radius of Earth). What is the orbital velocity in terms of escape velocity vₑ at the surface?",
                "hard",
                [("vₑ / 2", True), ("vₑ / √2", False), ("vₑ / 4", False), ("vₑ √2", False)],
                "At h=R, v_orbital = √(gR/2). Since vₑ = √(2gR), v_orbital = vₑ/2.",
            ),
        ]

        chemistry_questions = [
            (
                "Which quantum number determines the shape of an orbital?",
                "easy",
                [("Azimuthal (l)", True), ("Principal (n)", False), ("Magnetic (mₗ)", False), ("Spin (mₛ)", False)],
                "The azimuthal quantum number l defines the orbital shape: l=0 (s), l=1 (p), l=2 (d).",
            ),
            (
                "How many nodes are present in a 3p orbital?",
                "easy",
                [("2", True), ("1", False), ("3", False), ("0", False)],
                "Total nodes = n-1 = 2. For 3p: 1 radial + 1 angular = 2.",
            ),
            (
                "Which of the following has the highest first ionisation energy?",
                "medium",
                [("Nitrogen", True), ("Oxygen", False), ("Carbon", False), ("Boron", False)],
                "N has a half-filled 2p³ configuration which is extra stable, giving it higher IE than O.",
            ),
            (
                "In the reaction CH₃CHO → CH₃COOH, the carbon of the aldehyde group is:",
                "medium",
                [("Oxidised", True), ("Reduced", False), ("Neither", False), ("Both", False)],
                "Oxidation state of C changes from +1 in CHO to +3 in COOH — it is oxidised.",
            ),
            (
                "The hybridisation of Xe in XeF₄ is:",
                "hard",
                [("sp³d²", True), ("sp³d", False), ("sp³", False), ("dsp³", False)],
                "XeF₄ has 4 bond pairs + 2 lone pairs = 6 electron domains → sp³d² hybridisation.",
            ),
        ]

        maths_questions = [
            (
                "If the roots of x² - 5x + 6 = 0 are α and β, what is α² + β²?",
                "easy",
                [("13", True), ("11", False), ("25", False), ("17", False)],
                "α+β=5, αβ=6. α²+β² = (α+β)² - 2αβ = 25-12 = 13.",
            ),
            (
                "The value of sin(75°) is:",
                "easy",
                [("(√6 + √2) / 4", True), ("(√6 − √2) / 4", False), ("(√3 + 1) / 2√2", False), ("√3 / 2", False)],
                "sin75° = sin(45°+30°) = sin45°cos30° + cos45°sin30° = (√6+√2)/4.",
            ),
            (
                "The number of terms in the expansion of (x + y + z)¹⁰ is:",
                "medium",
                [("66", True), ("55", False), ("110", False), ("100", False)],
                "Number of terms = C(n+r-1, r-1) = C(12,2) = 66.",
            ),
            (
                "If f(x) = x³ − 3x + 2, the number of real roots is:",
                "medium",
                [("3", True), ("1", False), ("2", False), ("0", False)],
                "f'(x)=3x²-3=0 gives x=±1. f(1)=0, f(-1)=4. Since f has a root at x=1 and changes sign, it has 3 real roots (1 is a repeated root, so f=(x-1)²(x+2)).",
            ),
            (
                "∫₀^π x sin(x) dx equals:",
                "hard",
                [("π", True), ("2π", False), ("0", False), ("π/2", False)],
                "Using integration by parts: = [-x cos x]₀^π + ∫cos x dx = π + [sin x]₀^π = π.",
            ),
        ]

        question_bank = {
            "Physics": physics_questions,
            "Chemistry": chemistry_questions,
            "Mathematics": maths_questions,
        }

        # ── Weekly exams ────────────────────────────────────────
        all_exams = []
        for week in weeks:
            course = week.course
            subject = "Physics"
            if "Chemistry" in course.title or "Organic" in course.title or "Physical" in course.title:
                subject = "Chemistry"
            elif "Math" in course.title or "Calculus" in course.title or "Algebra" in course.title:
                subject = "Mathematics"

            exam = Exam.objects.create(
                level=course.level,
                week=week,
                course=course,
                exam_type="weekly",
                title=f"{course.title} — {week.name} Test",
                duration_minutes=30,
                total_marks=20,
                passing_percentage=Decimal("50.00"),
                num_questions=5,
                is_proctored=False,
            )
            all_exams.append(exam)

            qbank = question_bank.get(subject, physics_questions)
            for _qi, (text, diff, opts, expl) in enumerate(qbank):
                q = Question.objects.create(
                    exam=exam,
                    level=course.level,
                    text=text,
                    difficulty=diff,
                    question_type="mcq",
                    marks=4,
                    negative_marks=Decimal("1.00"),
                    explanation=expl,
                )
                for otext, correct in opts:
                    Option.objects.create(question=q, text=otext, is_correct=correct)

        self.stdout.write(f"  Created {len([e for e in all_exams if e.exam_type == 'weekly'])} weekly exams")

        # ── Level final exams ───────────────────────────────────
        for level in levels:
            exam = Exam.objects.create(
                level=level,
                exam_type="level_final",
                title=f"{level.name} — Level Final Exam",
                duration_minutes=90,
                total_marks=100,
                passing_percentage=level.passing_percentage,
                num_questions=25,
                is_proctored=True,
                max_warnings=3,
            )
            all_exams.append(exam)
            all_q = physics_questions + chemistry_questions + maths_questions
            for qi, (text, diff, opts, expl) in enumerate(all_q):
                q = Question.objects.create(
                    exam=exam,
                    level=level,
                    text=f"[Final] {text}",
                    difficulty=diff,
                    question_type="mcq" if qi % 3 != 2 else "multi_mcq",
                    marks=4,
                    negative_marks=Decimal("1.00"),
                    explanation=expl,
                )
                for otext, correct in opts:
                    Option.objects.create(question=q, text=otext, is_correct=correct)

        self.stdout.write(f"  Created {len(levels)} level final exams")

        # ── Onboarding exam ─────────────────────────────────────
        onboarding_exam = Exam.objects.create(
            level=levels[0],
            exam_type="onboarding",
            title="Placement Assessment",
            duration_minutes=45,
            total_marks=60,
            passing_percentage=Decimal("40.00"),
            num_questions=15,
            is_proctored=False,
        )
        all_exams.append(onboarding_exam)
        for _qi, (text, diff, opts, expl) in enumerate(
            (physics_questions + chemistry_questions + maths_questions)[:15]
        ):
            q = Question.objects.create(
                exam=onboarding_exam,
                level=levels[0],
                text=f"[Placement] {text}",
                difficulty=diff,
                question_type="mcq",
                marks=4,
                negative_marks=Decimal("0"),
                explanation=expl,
            )
            for otext, correct in opts:
                Option.objects.create(question=q, text=otext, is_correct=correct)

        self.stdout.write(f"  Created {len(all_exams)} total exams with questions")

        # ── Exam Attempts ───────────────────────────────────────
        weekly_exams = Exam.objects.filter(exam_type="weekly")
        final_exams = Exam.objects.filter(exam_type="level_final")

        for i, profile in enumerate(profiles):
            if not profile.current_level:
                continue
            # Weekly exam attempts
            accessible_weekly = weekly_exams.filter(level__order__lte=profile.current_level.order)
            for exam in accessible_weekly[: random.randint(2, min(6, accessible_weekly.count()))]:
                questions = list(exam.questions.all())
                if not questions:
                    continue
                score = sum(q.marks for q in questions) * Decimal(str(random.uniform(0.3, 1.0)))
                score = round(score, 2)
                is_passed = score >= exam.total_marks * exam.passing_percentage / 100

                attempt = ExamAttempt.objects.create(
                    student=profile,
                    exam=exam,
                    submitted_at=now - timedelta(days=random.randint(1, 60)),
                    status="submitted",
                    score=score,
                    total_marks=exam.total_marks,
                    is_passed=is_passed,
                )

                for qi, question in enumerate(questions):
                    q_options = list(question.options.all())
                    correct_opt = next((o for o in q_options if o.is_correct), None)
                    got_right = random.random() < 0.6
                    selected = (
                        correct_opt if got_right and correct_opt else (random.choice(q_options) if q_options else None)
                    )
                    AttemptQuestion.objects.create(
                        attempt=attempt,
                        question=question,
                        selected_option=selected,
                        is_correct=got_right,
                        marks_awarded=question.marks if got_right else -question.negative_marks,
                        order=qi + 1,
                    )

            # Final exam attempts for cleared levels
            if i < 10:
                final_l1 = final_exams.filter(level=levels[0]).first()
                if final_l1:
                    questions = list(final_l1.questions.all())
                    attempt = ExamAttempt.objects.create(
                        student=profile,
                        exam=final_l1,
                        submitted_at=now - timedelta(days=random.randint(15, 50)),
                        status="submitted",
                        score=Decimal(str(random.randint(55, 95))),
                        total_marks=100,
                        is_passed=True,
                    )
                    for qi, question in enumerate(questions[:15]):
                        q_options = list(question.options.all())
                        correct_opt = next((o for o in q_options if o.is_correct), None)
                        AttemptQuestion.objects.create(
                            attempt=attempt,
                            question=question,
                            selected_option=correct_opt,
                            is_correct=True,
                            marks_awarded=question.marks,
                            order=qi + 1,
                        )

        # One timed-out attempt
        if len(profiles) > 11:
            timed_out_exam = weekly_exams.first()
            if timed_out_exam:
                ExamAttempt.objects.create(
                    student=profiles[11],
                    exam=timed_out_exam,
                    submitted_at=now - timedelta(days=5),
                    status="timed_out",
                    score=Decimal("4.00"),
                    total_marks=timed_out_exam.total_marks,
                    is_passed=False,
                )

        # One in-progress attempt
        if len(profiles) > 10:
            in_progress_exam = weekly_exams.last()
            if in_progress_exam:
                ExamAttempt.objects.create(
                    student=profiles[10],
                    exam=in_progress_exam,
                    status="in_progress",
                    score=None,
                    total_marks=in_progress_exam.total_marks,
                    is_passed=None,
                )

        # One disqualified attempt with proctoring violations
        if len(profiles) > 7 and len(levels) > 1:
            final_l2 = final_exams.filter(level=levels[1]).first()
            if final_l2:
                dq_attempt = ExamAttempt.objects.create(
                    student=profiles[7],
                    exam=final_l2,
                    submitted_at=now - timedelta(days=3),
                    status="submitted",
                    score=Decimal("45.00"),
                    total_marks=100,
                    is_passed=False,
                    is_disqualified=True,
                )
                for vi, vtype in enumerate(["tab_switch", "full_screen_exit", "tab_switch", "multi_face"]):
                    ProctoringViolation.objects.create(
                        attempt=dq_attempt,
                        violation_type=vtype,
                        warning_number=vi + 1,
                        details=f"Violation detected at {5 + vi * 10} minutes into the exam.",
                    )

        self.stdout.write("  Created exam attempts & proctoring violations")
        self.stdout.write(self.style.SUCCESS("Done — exam data reseeded."))
