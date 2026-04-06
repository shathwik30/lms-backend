"""
Flush all data and seed the database with fresh LMS data.

Usage:  python manage.py seed_data
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analytics.models import DailyRevenue, LevelAnalytics
from apps.courses.models import Bookmark, Course, Session
from apps.doubts.models import DoubtReply, DoubtTicket
from apps.exams.models import (
    AttemptQuestion,
    Exam,
    ExamAttempt,
    Option,
    ProctoringViolation,
    Question,
)
from apps.feedback.models import SessionFeedback
from apps.home.models import Banner
from apps.levels.models import Level, Week
from apps.notifications.models import Notification
from apps.payments.models import PaymentTransaction, Purchase
from apps.progress.models import CourseProgress, LevelProgress, SessionProgress
from apps.users.models import IssueReport, User, UserPreference


class Command(BaseCommand):
    help = "Flush all data and seed the database with fresh LMS data"

    def handle(self, *args, **options):
        now = timezone.now()

        # ── Flush all data ──────────────────────────────────────
        self.stdout.write("Flushing all data ...")
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("""
                TRUNCATE TABLE
                    level_analytics,
                    daily_revenue,
                    notifications,
                    session_feedbacks,
                    issue_reports,
                    doubt_replies,
                    doubt_tickets,
                    bookmarks,
                    session_progress,
                    course_progress,
                    level_progress,
                    proctoring_violations,
                    attempt_questions,
                    exam_attempts,
                    options,
                    questions,
                    exams,
                    payment_transactions,
                    purchases,
                    sessions,
                    weeks,
                    courses,
                    levels,
                    banners,
                    user_preferences,
                    student_profiles,
                    users
                RESTART IDENTITY CASCADE
            """)
        self.stdout.write(self.style.SUCCESS("  All data flushed."))

        # ── Seed fresh data ─────────────────────────────────────
        self.stdout.write("Seeding fresh data ...")

        # ── Admin & Staff ───────────────────────────────────────
        admin = User.objects.create_superuser(
            email="admin@iitprep.com",
            password="Admin@123",
            full_name="Dr. Rajesh Kumar",
        )
        admin.phone = "+919876543210"
        admin.is_admin = True
        admin.save()

        staff = User.objects.create_user(
            email="staff@iitprep.com",
            password="Staff@123",
            full_name="Priya Sharma",
        )
        staff.is_staff = True
        staff.is_admin = True
        staff.is_student = False
        staff.phone = "+919876543211"
        staff.save()

        # ── Levels ──────────────────────────────────────────────
        levels_data = [
            {
                "name": "Foundation",
                "order": 1,
                "description": "Build a rock-solid base in Physics, Chemistry & Mathematics. Covers NCERT Class 11 fundamentals.",
                "price": Decimal("0"),
                "passing_percentage": Decimal("50.00"),
                "validity_days": 365,
                "max_final_exam_attempts": 5,
            },
            {
                "name": "Intermediate",
                "order": 2,
                "description": "Class 11 advanced problems and Class 12 core topics. Weekly tests sharpen exam temperament.",
                "price": Decimal("1999.00"),
                "passing_percentage": Decimal("55.00"),
                "validity_days": 365,
                "max_final_exam_attempts": 3,
            },
            {
                "name": "Advanced",
                "order": 3,
                "description": "JEE Advanced-level problem solving -- multi-concept questions, integer-type & matrix-match.",
                "price": Decimal("2999.00"),
                "passing_percentage": Decimal("60.00"),
                "validity_days": 365,
                "max_final_exam_attempts": 3,
            },
            {
                "name": "Mastery",
                "order": 4,
                "description": "Full-length mock tests, previous-year papers & rank-improvement strategies for top 1000 AIR.",
                "price": Decimal("3999.00"),
                "passing_percentage": Decimal("65.00"),
                "validity_days": 180,
                "max_final_exam_attempts": 2,
            },
        ]
        levels = []
        for ld in levels_data:
            levels.append(Level.objects.create(**ld))
        self.stdout.write(f"  Created {len(levels)} levels")

        # ── Courses per Level ───────────────────────────────────
        courses_map = {
            levels[0]: [
                (
                    "Physics -- Mechanics Basics",
                    "Newton's laws, kinematics, work-energy theorem, and rotational motion fundamentals.",
                ),
                (
                    "Chemistry -- Atomic Structure & Bonding",
                    "Atomic models, periodic trends, ionic and covalent bonding, VSEPR theory.",
                ),
                (
                    "Mathematics -- Algebra & Trigonometry",
                    "Quadratic equations, complex numbers, sequences, trigonometric identities and equations.",
                ),
            ],
            levels[1]: [
                (
                    "Physics -- Electromagnetism",
                    "Coulomb's law, Gauss's theorem, capacitance, magnetic effects of current, and EMI.",
                ),
                (
                    "Chemistry -- Organic Chemistry I",
                    "IUPAC nomenclature, reaction mechanisms, hydrocarbons, haloalkanes, and alcohols.",
                ),
                (
                    "Mathematics -- Calculus I",
                    "Limits, continuity, differentiation techniques, and applications of derivatives.",
                ),
            ],
            levels[2]: [
                (
                    "Physics -- Optics & Modern Physics",
                    "Wave optics, interference, diffraction, photoelectric effect, and nuclear physics.",
                ),
                (
                    "Chemistry -- Physical Chemistry",
                    "Thermodynamics, chemical equilibrium, electrochemistry, and chemical kinetics.",
                ),
                (
                    "Mathematics -- Calculus II & Vectors",
                    "Integration techniques, definite integrals, differential equations, and vector algebra.",
                ),
            ],
            levels[3]: [
                ("JEE Advanced Mock Series", "Full-syllabus mock tests modelled on the latest JEE Advanced pattern."),
                (
                    "Previous Year Paper Analysis",
                    "Detailed walkthroughs of IIT-JEE papers from 2018-2025 with strategy notes.",
                ),
            ],
        }

        all_courses = []
        for level, clist in courses_map.items():
            for title, desc in clist:
                all_courses.append(Course.objects.create(level=level, title=title, description=desc))
        self.stdout.write(f"  Created {len(all_courses)} courses")

        # ── Weeks & Sessions ────────────────────────────────────
        video_urls = [
            "https://www.youtube.com/watch?v=ZM7wVpHSdGE",
            "https://www.youtube.com/watch?v=3Md8GRCOONE",
            "https://www.youtube.com/watch?v=kpOEBGrtEhA",
            "https://www.youtube.com/watch?v=fNk_zzaMoSs",
        ]
        thumbnails = [
            "https://img.youtube.com/vi/ZM7wVpHSdGE/hqdefault.jpg",
            "https://img.youtube.com/vi/3Md8GRCOONE/hqdefault.jpg",
            "https://img.youtube.com/vi/kpOEBGrtEhA/hqdefault.jpg",
            "https://img.youtube.com/vi/fNk_zzaMoSs/hqdefault.jpg",
        ]

        session_titles_by_subject = {
            "Physics": [
                [
                    "Introduction & Units",
                    "Vectors and Scalars",
                    "Kinematics -- 1D Motion",
                    "Kinematics -- 2D Projectiles",
                    "Newton's First & Second Law",
                    "Newton's Third Law & FBD",
                    "Friction -- Static & Kinetic",
                    "Practice Problems Set 1",
                ],
                [
                    "Work and Energy",
                    "Conservation of Energy",
                    "Power and Collisions",
                    "Centre of Mass",
                    "Rotational Kinematics",
                    "Torque & Moment of Inertia",
                    "Angular Momentum",
                    "Practice Problems Set 2",
                ],
                [
                    "Gravitation",
                    "SHM -- Springs & Pendulums",
                    "Fluid Mechanics -- Pressure",
                    "Bernoulli's Principle",
                    "Surface Tension & Viscosity",
                    "Practice Problems Set 3",
                ],
            ],
            "Chemistry": [
                [
                    "Dalton to Bohr",
                    "Quantum Mechanical Model",
                    "Electronic Configuration",
                    "Periodic Table Trends",
                    "Ionisation Energy & Electronegativity",
                    "Ionic Bonding",
                    "Covalent Bonding & Hybridisation",
                    "Practice Problems Set 1",
                ],
                [
                    "VSEPR & Molecular Geometry",
                    "Metallic Bonding & Band Theory",
                    "Hydrogen Bonding",
                    "Intermolecular Forces",
                    "Solid State Basics",
                    "Practice Problems Set 2",
                ],
            ],
            "Mathematics": [
                [
                    "Sets & Relations",
                    "Functions -- Domain & Range",
                    "Quadratic Equations",
                    "Complex Numbers -- Basics",
                    "Complex Numbers -- Argand Plane",
                    "Sequences -- AP & GP",
                    "Binomial Theorem",
                    "Practice Problems Set 1",
                ],
                [
                    "Trigonometric Ratios",
                    "Trigonometric Identities",
                    "Trigonometric Equations",
                    "Inverse Trigonometry",
                    "Heights & Distances",
                    "Practice Problems Set 2",
                ],
                [
                    "Straight Lines",
                    "Circles",
                    "Conic Sections -- Parabola",
                    "Conic Sections -- Ellipse & Hyperbola",
                    "Practice Problems Set 3",
                ],
            ],
        }

        all_sessions = []
        all_weeks = []
        for course in all_courses:
            subject = "Physics"
            if "Chemistry" in course.title or "Organic" in course.title or "Physical" in course.title:
                subject = "Chemistry"
            elif "Math" in course.title or "Calculus" in course.title or "Algebra" in course.title:
                subject = "Mathematics"

            week_sessions = session_titles_by_subject.get(subject, session_titles_by_subject["Physics"])
            num_weeks = min(3, len(week_sessions))

            for wi in range(num_weeks):
                week = Week.objects.create(course=course, name=f"Week {wi + 1}", order=wi + 1)
                all_weeks.append(week)
                titles = week_sessions[wi]
                for si, stitle in enumerate(titles):
                    is_practice = "Practice" in stitle
                    s = Session.objects.create(
                        week=week,
                        title=stitle,
                        description=f"{stitle} -- detailed lecture covering key concepts with solved examples.",
                        video_url="" if is_practice else random.choice(video_urls),
                        thumbnail_url="" if is_practice else random.choice(thumbnails),
                        duration_seconds=0 if is_practice else random.randint(1200, 3600),
                        order=si + 1,
                        session_type="resource" if is_practice else "video",
                        resource_type="pdf" if is_practice else "",
                        file_url="https://drive.google.com/file/d/example/view" if is_practice else "",
                    )
                    all_sessions.append(s)

        self.stdout.write(f"  Created {len(all_weeks)} weeks, {len(all_sessions)} sessions")

        # ── Exams & Questions ───────────────────────────────────
        physics_questions = [
            (
                "A ball is thrown vertically upward with velocity 20 m/s. What is the maximum height reached? (g = 10 m/s2)",
                "easy",
                [("20 m", True), ("40 m", False), ("10 m", False), ("30 m", False)],
                "Using v2 = u2 - 2gh, at max height v=0, so h = u2/2g = 400/20 = 20 m.",
            ),
            (
                "A block of mass 5 kg is placed on a frictionless surface. A horizontal force of 10 N is applied. What is the acceleration?",
                "easy",
                [("2 m/s2", True), ("5 m/s2", False), ("10 m/s2", False), ("1 m/s2", False)],
                "F = ma, so a = F/m = 10/5 = 2 m/s2.",
            ),
            (
                "Two blocks of masses 3 kg and 5 kg are connected by a string over a frictionless pulley. Find the acceleration of the system.",
                "medium",
                [("2.45 m/s2", True), ("3.68 m/s2", False), ("4.9 m/s2", False), ("1.22 m/s2", False)],
                "a = (m2 - m1)g / (m1 + m2) = (5-3)*9.8 / 8 = 2.45 m/s2.",
            ),
            (
                "A projectile is fired at 60 degrees with horizontal at 40 m/s. Find the range. (g = 10 m/s2)",
                "medium",
                [("138.6 m", True), ("160 m", False), ("80 m", False), ("120 m", False)],
                "R = u2*sin(2*theta)/g = 1600 * sin120 / 10 = 138.6 m.",
            ),
            (
                "A satellite orbits Earth at height h = R (R = radius of Earth). What is the orbital velocity in terms of escape velocity ve at the surface?",
                "hard",
                [("ve / 2", True), ("ve / sqrt(2)", False), ("ve / 4", False), ("ve * sqrt(2)", False)],
                "At h=R, v_orbital = sqrt(gR/2). Since ve = sqrt(2gR), v_orbital = ve/2.",
            ),
        ]

        chemistry_questions = [
            (
                "Which quantum number determines the shape of an orbital?",
                "easy",
                [("Azimuthal (l)", True), ("Principal (n)", False), ("Magnetic (ml)", False), ("Spin (ms)", False)],
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
                "N has a half-filled 2p3 configuration which is extra stable, giving it higher IE than O.",
            ),
            (
                "In the reaction CH3CHO -> CH3COOH, the carbon of the aldehyde group is:",
                "medium",
                [("Oxidised", True), ("Reduced", False), ("Neither", False), ("Both", False)],
                "Oxidation state of C changes from +1 in CHO to +3 in COOH -- it is oxidised.",
            ),
            (
                "The hybridisation of Xe in XeF4 is:",
                "hard",
                [("sp3d2", True), ("sp3d", False), ("sp3", False), ("dsp3", False)],
                "XeF4 has 4 bond pairs + 2 lone pairs = 6 electron domains -> sp3d2 hybridisation.",
            ),
        ]

        maths_questions = [
            (
                "If the roots of x2 - 5x + 6 = 0 are alpha and beta, what is alpha2 + beta2?",
                "easy",
                [("13", True), ("11", False), ("25", False), ("17", False)],
                "alpha+beta=5, alpha*beta=6. alpha2+beta2 = (alpha+beta)2 - 2*alpha*beta = 25-12 = 13.",
            ),
            (
                "The value of sin(75 degrees) is:",
                "easy",
                [
                    ("(sqrt6 + sqrt2) / 4", True),
                    ("(sqrt6 - sqrt2) / 4", False),
                    ("(sqrt3 + 1) / 2*sqrt2", False),
                    ("sqrt3 / 2", False),
                ],
                "sin75 = sin(45+30) = sin45*cos30 + cos45*sin30 = (sqrt6+sqrt2)/4.",
            ),
            (
                "The number of terms in the expansion of (x + y + z)^10 is:",
                "medium",
                [("66", True), ("55", False), ("110", False), ("100", False)],
                "Number of terms = C(n+r-1, r-1) = C(12,2) = 66.",
            ),
            (
                "If f(x) = x3 - 3x + 2, the number of real roots is:",
                "medium",
                [("3", True), ("1", False), ("2", False), ("0", False)],
                "f'(x)=3x2-3=0 gives x=+-1. f(1)=0, f(-1)=4. f=(x-1)2(x+2), so 3 real roots.",
            ),
            (
                "Integral from 0 to pi of x*sin(x) dx equals:",
                "hard",
                [("pi", True), ("2*pi", False), ("0", False), ("pi/2", False)],
                "Using integration by parts: = [-x cos x] from 0 to pi + integral of cos x dx = pi + [sin x] from 0 to pi = pi.",
            ),
        ]

        all_exams = []
        question_bank = {"Physics": physics_questions, "Chemistry": chemistry_questions, "Mathematics": maths_questions}

        # Weekly exams for each week
        for week in all_weeks:
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
                title=f"{course.title} -- {week.name} Test",
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

        # Level final exams
        for level in levels:
            exam = Exam.objects.create(
                level=level,
                exam_type="level_final",
                title=f"{level.name} -- Level Final Exam",
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

        # Onboarding exam for each level
        for level in levels:
            onboarding_exam = Exam.objects.create(
                level=level,
                exam_type="onboarding",
                title=f"{level.name} Placement Assessment",
                duration_minutes=30,
                total_marks=20,
                passing_percentage=Decimal("50.00"),
                num_questions=5,
                is_proctored=False,
            )
            all_exams.append(onboarding_exam)

            all_q = physics_questions + chemistry_questions + maths_questions
            for _qi, (text, diff, opts, expl) in enumerate(all_q[:5]):
                q = Question.objects.create(
                    exam=onboarding_exam,
                    level=level,
                    text=f"[Placement] {text}",
                    difficulty=diff,
                    question_type="mcq",
                    marks=4,
                    negative_marks=Decimal("0"),
                    explanation=expl,
                )
                for otext, correct in opts:
                    Option.objects.create(question=q, text=otext, is_correct=correct)

        self.stdout.write(f"  Created {len(all_exams)} exams with questions")

        # ── Students ────────────────────────────────────────────
        students_data = [
            {
                "email": "arjun.mehta@gmail.com",
                "password": "Student@123",
                "full_name": "Arjun Mehta",
                "phone": "+919001000001",
                "gender": "male",
            },
            {
                "email": "sneha.iyer@gmail.com",
                "password": "Student@123",
                "full_name": "Sneha Iyer",
                "phone": "+919001000002",
                "gender": "female",
            },
            {
                "email": "rohan.das@gmail.com",
                "password": "Student@123",
                "full_name": "Rohan Das",
                "phone": "+919001000003",
                "gender": "male",
            },
            {
                "email": "ananya.singh@gmail.com",
                "password": "Student@123",
                "full_name": "Ananya Singh",
                "phone": "+919001000004",
                "gender": "female",
            },
            {
                "email": "vikram.patel@gmail.com",
                "password": "Student@123",
                "full_name": "Vikram Patel",
                "phone": "+919001000005",
                "gender": "male",
            },
            {
                "email": "priya.nair@gmail.com",
                "password": "Student@123",
                "full_name": "Priya Nair",
                "phone": "+919001000006",
                "gender": "female",
            },
            {
                "email": "karthik.reddy@gmail.com",
                "password": "Student@123",
                "full_name": "Karthik Reddy",
                "phone": "+919001000007",
                "gender": "male",
            },
            {
                "email": "divya.sharma@gmail.com",
                "password": "Student@123",
                "full_name": "Divya Sharma",
                "phone": "+919001000008",
                "gender": "female",
            },
            {
                "email": "aditya.joshi@gmail.com",
                "password": "Student@123",
                "full_name": "Aditya Joshi",
                "phone": "+919001000009",
                "gender": "male",
            },
            {
                "email": "meera.krishnan@gmail.com",
                "password": "Student@123",
                "full_name": "Meera Krishnan",
                "phone": "+919001000010",
                "gender": "female",
            },
            {
                "email": "rahul.gupta@gmail.com",
                "password": "Student@123",
                "full_name": "Rahul Gupta",
                "phone": "+919001000011",
                "gender": "male",
            },
            {
                "email": "ishita.verma@gmail.com",
                "password": "Student@123",
                "full_name": "Ishita Verma",
                "phone": "+919001000012",
                "gender": "female",
            },
            {
                "email": "nikhil.pandey@gmail.com",
                "password": "Student@123",
                "full_name": "Nikhil Pandey",
                "phone": "+919001000013",
                "gender": "male",
            },
            {
                "email": "kavya.menon@gmail.com",
                "password": "Student@123",
                "full_name": "Kavya Menon",
                "phone": "+919001000014",
                "gender": "female",
            },
            {
                "email": "siddharth.rao@gmail.com",
                "password": "Student@123",
                "full_name": "Siddharth Rao",
                "phone": "+919001000015",
                "gender": "prefer_not_to_say",
            },
        ]

        profiles = []
        for sd in students_data:
            gender = sd.pop("gender")
            pwd = sd.pop("password")
            user = User.objects.create_user(password=pwd, **sd)
            profile = user.student_profile
            profile.gender = gender
            profile.is_onboarding_completed = True
            profile.is_onboarding_exam_attempted = True
            profile.save()
            UserPreference.objects.get_or_create(user=user)
            profiles.append(profile)

        # Fresh student for onboarding/e2e journey
        fresh_user = User.objects.create_user(
            email="amit.tiwari@gmail.com",
            password="Student@123",
            full_name="Amit Tiwari",
            phone="+919001000016",
        )
        fresh_profile = fresh_user.student_profile
        fresh_profile.gender = "male"
        fresh_profile.is_onboarding_completed = False
        fresh_profile.is_onboarding_exam_attempted = False
        fresh_profile.save()
        UserPreference.objects.get_or_create(user=fresh_user)

        self.stdout.write(f"  Created {len(profiles) + 1} students")

        # ── Purchases & Payments ────────────────────────────────
        purchases = []
        for i, profile in enumerate(profiles):
            # Foundation -- free for everyone
            p = Purchase.objects.create(
                student=profile,
                level=levels[0],
                amount_paid=Decimal("0"),
                expires_at=now + timedelta(days=365),
                status="active",
            )
            purchases.append(p)
            PaymentTransaction.objects.create(
                purchase=p,
                student=profile,
                level=levels[0],
                razorpay_order_id=f"order_free_{profile.pk:04d}",
                razorpay_payment_id=f"pay_free_{profile.pk:04d}",
                amount=Decimal("0"),
                status="success",
            )

            # First 10 students bought Intermediate
            if i < 10:
                p2 = Purchase.objects.create(
                    student=profile,
                    level=levels[1],
                    amount_paid=Decimal("1999.00"),
                    expires_at=now + timedelta(days=365),
                    status="active",
                )
                purchases.append(p2)
                PaymentTransaction.objects.create(
                    purchase=p2,
                    student=profile,
                    level=levels[1],
                    razorpay_order_id=f"order_L2_{profile.pk:04d}",
                    razorpay_payment_id=f"pay_L2_{profile.pk:04d}",
                    amount=Decimal("1999.00"),
                    status="success",
                )

            # First 5 students bought Advanced
            if i < 5:
                p3 = Purchase.objects.create(
                    student=profile,
                    level=levels[2],
                    amount_paid=Decimal("2999.00"),
                    expires_at=now + timedelta(days=365),
                    status="active",
                )
                purchases.append(p3)
                PaymentTransaction.objects.create(
                    purchase=p3,
                    student=profile,
                    level=levels[2],
                    razorpay_order_id=f"order_L3_{profile.pk:04d}",
                    razorpay_payment_id=f"pay_L3_{profile.pk:04d}",
                    amount=Decimal("2999.00"),
                    status="success",
                )

            # Top 2 students bought Mastery
            if i < 2:
                p4 = Purchase.objects.create(
                    student=profile,
                    level=levels[3],
                    amount_paid=Decimal("3999.00"),
                    expires_at=now + timedelta(days=180),
                    status="active",
                )
                purchases.append(p4)
                PaymentTransaction.objects.create(
                    purchase=p4,
                    student=profile,
                    level=levels[3],
                    razorpay_order_id=f"order_L4_{profile.pk:04d}",
                    razorpay_payment_id=f"pay_L4_{profile.pk:04d}",
                    amount=Decimal("3999.00"),
                    status="success",
                )

        # One expired purchase
        exp_purchase = Purchase.objects.create(
            student=profiles[12],
            level=levels[1],
            amount_paid=Decimal("1999.00"),
            expires_at=now - timedelta(days=30),
            status="expired",
        )
        PaymentTransaction.objects.create(
            purchase=exp_purchase,
            student=profiles[12],
            level=levels[1],
            razorpay_order_id="order_EXP_0013",
            razorpay_payment_id="pay_EXP_0013",
            amount=Decimal("1999.00"),
            status="success",
        )

        # One failed payment
        PaymentTransaction.objects.create(
            student=profiles[14],
            level=levels[1],
            razorpay_order_id="order_FAIL_0015",
            amount=Decimal("1999.00"),
            status="failed",
        )

        # One pending payment
        PaymentTransaction.objects.create(
            student=profiles[13],
            level=levels[1],
            razorpay_order_id="order_PEND_0014",
            amount=Decimal("1999.00"),
            status="pending",
        )

        self.stdout.write(f"  Created {len(purchases)} purchases & payment transactions")

        # ── Set student levels ──────────────────────────────────
        for i, profile in enumerate(profiles):
            if i < 2:
                profile.current_level = levels[3]
                profile.highest_cleared_level = levels[2]
            elif i < 5:
                profile.current_level = levels[2]
                profile.highest_cleared_level = levels[1]
            elif i < 10:
                profile.current_level = levels[1]
                profile.highest_cleared_level = levels[0]
            else:
                profile.current_level = levels[0]
                profile.highest_cleared_level = None
            profile.save()

        # ── Level Progress ──────────────────────────────────────
        for i, profile in enumerate(profiles):
            lp_status = "exam_passed" if i < 10 else ("in_progress" if i < 13 else "not_started")
            LevelProgress.objects.create(
                student=profile,
                level=levels[0],
                purchase=purchases[i * (1 + (i < 10) + (i < 5) + (i < 2))],
                status=lp_status,
                started_at=now - timedelta(days=random.randint(30, 90)),
                completed_at=(now - timedelta(days=random.randint(5, 25))) if lp_status == "exam_passed" else None,
            )
            if i < 10:
                LevelProgress.objects.create(
                    student=profile,
                    level=levels[1],
                    status="exam_passed" if i < 5 else "in_progress",
                    started_at=now - timedelta(days=random.randint(10, 40)),
                    completed_at=(now - timedelta(days=random.randint(1, 10))) if i < 5 else None,
                )
            if i < 5:
                LevelProgress.objects.create(
                    student=profile,
                    level=levels[2],
                    status="in_progress" if i < 3 else "syllabus_complete",
                    started_at=now - timedelta(days=random.randint(5, 20)),
                )
            if i < 2:
                LevelProgress.objects.create(
                    student=profile,
                    level=levels[3],
                    status="in_progress",
                    started_at=now - timedelta(days=random.randint(1, 10)),
                )

        # ── Session & Course Progress ───────────────────────────
        for i, profile in enumerate(profiles):
            accessible_levels = [levels[0]]
            if i < 10:
                accessible_levels.append(levels[1])
            if i < 5:
                accessible_levels.append(levels[2])
            if i < 2:
                accessible_levels.append(levels[3])

            for course in all_courses:
                if course.level not in accessible_levels:
                    continue

                sessions = Session.objects.filter(week__course=course).order_by("week__order", "order")
                total = sessions.count()
                if total == 0:
                    continue

                completion_ratio = (
                    random.uniform(0.4, 1.0)
                    if course.level.order <= profile.current_level.order - 1
                    else random.uniform(0.1, 0.6)
                )
                completed_count = int(total * completion_ratio)

                course_status = (
                    "completed"
                    if completed_count == total
                    else ("in_progress" if completed_count > 0 else "not_started")
                )
                CourseProgress.objects.create(
                    student=profile,
                    course=course,
                    status=course_status,
                    started_at=now - timedelta(days=random.randint(10, 60)) if completed_count > 0 else None,
                    completed_at=now - timedelta(days=random.randint(1, 10)) if course_status == "completed" else None,
                )

                for _j, session in enumerate(sessions[:completed_count]):
                    SessionProgress.objects.create(
                        student=profile,
                        session=session,
                        watched_seconds=session.duration_seconds if session.duration_seconds > 0 else 0,
                        is_completed=True,
                        completed_at=now - timedelta(days=random.randint(1, 50)),
                    )
                if completed_count < total:
                    in_progress_sessions = list(sessions[completed_count : completed_count + 2])
                    for session in in_progress_sessions:
                        SessionProgress.objects.create(
                            student=profile,
                            session=session,
                            watched_seconds=random.randint(60, session.duration_seconds)
                            if session.duration_seconds > 0
                            else 0,
                            is_completed=False,
                        )

        self.stdout.write("  Created session & course progress")

        # ── Exam Attempts ───────────────────────────────────────
        weekly_exams = Exam.objects.filter(exam_type="weekly")
        final_exams = Exam.objects.filter(exam_type="level_final")

        for i, profile in enumerate(profiles):
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

        # ── Bookmarks ──────────────────────────────────────────
        for _i, profile in enumerate(profiles[:8]):
            bookmark_sessions = random.sample(all_sessions[:30], min(random.randint(2, 5), len(all_sessions[:30])))
            for session in bookmark_sessions:
                Bookmark.objects.create(student=profile, session=session)

        # ── Doubts ──────────────────────────────────────────────
        doubt_data = [
            (
                "Confusion in Newton's Third Law application",
                "When we push a wall, the wall pushes back with equal force. Then why doesn't the wall move? I'm confused about action-reaction pairs acting on different bodies.",
                "session",
                "open",
            ),
            (
                "Sign convention in lens formula",
                "In the derivation of 1/v - 1/u = 1/f, I'm getting wrong answers. Can you clarify the sign convention for concave and convex lenses?",
                "session",
                "answered",
            ),
            (
                "Doubt in organic reaction mechanism",
                "In SN1 vs SN2, how do I decide which mechanism a given substrate will follow? The textbook examples are clear but mixed problems confuse me.",
                "topic",
                "in_review",
            ),
            (
                "Integration by parts -- choosing u and dv",
                "I know the LIATE rule but it doesn't always work. For integral of e^x * sin(x) dx, how do I decide?",
                "session",
                "answered",
            ),
            (
                "Doubt about Gauss's law application",
                "Can Gauss's law be applied to a non-uniform electric field? The textbook only shows symmetric cases.",
                "session",
                "open",
            ),
            (
                "Chemical equilibrium Le Chatelier's principle",
                "If we increase temperature for an exothermic reaction, the book says equilibrium shifts backward. But doesn't increasing T increase rate of both forward and backward?",
                "topic",
                "closed",
            ),
            (
                "Complex number argument range",
                "Why is the principal argument defined in (-pi, pi] and not [0, 2*pi)? Does it matter for JEE?",
                "session",
                "open",
            ),
            (
                "Matrix question from PYQ",
                "In JEE 2023 Paper 1, Q12 about matrix A^2 = A, I got a different answer. Can you explain the approach?",
                "exam_question",
                "in_review",
            ),
        ]

        all_doubt_sessions = list(Session.objects.filter(session_type="video")[:20])
        all_doubt_questions = list(Question.objects.all()[:5])

        for di, (title, desc, ctx, status) in enumerate(doubt_data):
            profile = profiles[di % len(profiles)]
            ticket = DoubtTicket.objects.create(
                student=profile,
                title=title,
                description=desc,
                status=status,
                context_type=ctx,
                session=random.choice(all_doubt_sessions) if ctx == "session" else None,
                exam_question=random.choice(all_doubt_questions) if ctx == "exam_question" else None,
                assigned_to=staff if status in ("in_review", "answered") else None,
                bonus_marks=Decimal("2.00") if status == "answered" else Decimal("0"),
            )

            if status in ("answered", "closed"):
                DoubtReply.objects.create(
                    ticket=ticket,
                    author=staff,
                    message="Great question! Let me explain this step by step. The key concept here is...",
                )
                DoubtReply.objects.create(
                    ticket=ticket,
                    author=profile.user,
                    message="Thank you, that makes much more sense now! I'll practice more problems on this.",
                )
                if status == "closed":
                    DoubtReply.objects.create(
                        ticket=ticket,
                        author=staff,
                        message="Glad it helped! Closing this ticket. Feel free to raise a new one if you have more doubts.",
                    )

            if status == "in_review":
                DoubtReply.objects.create(
                    ticket=ticket,
                    author=staff,
                    message="I've received your doubt. Let me prepare a detailed explanation -- will reply within 24 hours.",
                )

        self.stdout.write(f"  Created {len(doubt_data)} doubt tickets with replies")

        # ── Feedback ────────────────────────────────────────────
        feedback_comments = [
            "Excellent explanation! The examples were very helpful.",
            "Good session but could use more practice problems.",
            "The pace was a bit fast. Would appreciate slower derivations.",
            "Loved the visualisation of the concept. Crystal clear!",
            "Average session. Expected more depth on this topic.",
            "Best session so far! The trick for solving these quickly is golden.",
            "",
            "Needs improvement in audio quality but content was solid.",
        ]

        completed_progress = SessionProgress.objects.filter(is_completed=True).select_related("student", "session")[:50]
        feedback_count = 0
        for sp in completed_progress:
            if random.random() < 0.6:
                SessionFeedback.objects.create(
                    student=sp.student,
                    session=sp.session,
                    overall_rating=random.randint(3, 5),
                    difficulty_rating=random.randint(2, 5),
                    clarity_rating=random.randint(3, 5),
                    comment=random.choice(feedback_comments),
                )
                feedback_count += 1

        self.stdout.write(f"  Created {feedback_count} session feedbacks")

        # ── Issue Reports ───────────────────────────────────────
        issues_data = [
            (
                "bug",
                "Video not loading on Session 3",
                "The video player shows a blank screen with a spinner. I've tried refreshing multiple times. Using Chrome on Android.",
                True,
                "We've identified the issue -- the video CDN was down in your region. It should work now. Please try again.",
            ),
            (
                "payment",
                "Double charged for Level 2",
                "I was charged 1999 twice for the Intermediate level. Transaction IDs: pay_xyz123 and pay_xyz124. Please refund the duplicate.",
                False,
                "",
            ),
            (
                "content",
                "Typo in Chemistry Week 2 notes",
                "In the PDF for Covalent Bonding, page 3 says 'elctron' instead of 'electron'. Also the diagram labels are swapped.",
                True,
                "Fixed! Thank you for reporting this.",
            ),
            (
                "account",
                "Cannot change profile picture",
                "When I try to upload a new profile picture, it says 'File too large' even though my image is only 500 KB.",
                False,
                "",
            ),
            (
                "other",
                "Request for dark mode",
                "Can you please add a dark mode option? Studying late at night and the bright screen strains my eyes.",
                False,
                "",
            ),
            (
                "bug",
                "Exam timer not syncing",
                "During the weekly test, the timer showed 25 minutes remaining but the exam auto-submitted saying time is up.",
                True,
                "This was a timezone sync issue that has been patched in the latest update. If you face this again please let us know.",
            ),
        ]

        for ii, (cat, subj, desc, resolved, response) in enumerate(issues_data):
            IssueReport.objects.create(
                user=profiles[ii % len(profiles)].user,
                category=cat,
                subject=subj,
                description=desc,
                is_resolved=resolved,
                admin_response=response,
                device_info=random.choice(["Samsung Galaxy S23", "iPhone 14", "OnePlus 11", "Pixel 8"]),
                browser_info=random.choice(["Chrome 120", "Safari 17", "Firefox 121"]),
                os_info=random.choice(["Android 14", "iOS 17", "Android 13"]),
            )

        self.stdout.write(f"  Created {len(issues_data)} issue reports")

        # ── Notifications ───────────────────────────────────────
        notif_templates = [
            (
                "purchase",
                "Payment Successful",
                "Your purchase of {level} level has been confirmed. Happy learning!",
                False,
            ),
            ("exam_result", "Exam Result Available", "Your result for {exam} is ready. You scored {score}%!", False),
            ("doubt_reply", "New Reply on Your Doubt", "An instructor has replied to your doubt: '{title}'.", True),
            (
                "level_unlock",
                "New Level Unlocked!",
                "Congratulations! You've unlocked the {level} level. Start exploring now.",
                False,
            ),
            (
                "general",
                "Welcome to IIT Prep Academy",
                "Welcome aboard! Start with the Foundation level to build your base.",
                True,
            ),
            (
                "course_expiry",
                "Subscription Expiring Soon",
                "Your {level} level access expires in 7 days. Renew now to continue.",
                False,
            ),
        ]

        for profile in profiles:
            for ntype, title, msg, is_read in notif_templates[: random.randint(2, len(notif_templates))]:
                Notification.objects.create(
                    user=profile.user,
                    title=title,
                    message=msg.format(
                        level="Foundation", exam="Weekly Test", score=random.randint(60, 95), title="Newton's Third Law"
                    ),
                    notification_type=ntype,
                    is_read=is_read,
                )

        self.stdout.write("  Created notifications")

        # ── Banners ─────────────────────────────────────────────
        Banner.objects.create(
            title="JEE 2026 Crash Course",
            subtitle="Intensive 90-day program starting April 1st",
            image_url="https://images.unsplash.com/photo-1523050854058-8df90110c476?w=1200",
            link_type="level",
            link_id=levels[2].pk,
            order=1,
        )
        Banner.objects.create(
            title="Foundation Level -- Free Access",
            subtitle="Start your IIT-JEE journey today at zero cost",
            image_url="https://images.unsplash.com/photo-1546410531-og48a8e14ee2?w=1200",
            link_type="level",
            link_id=levels[0].pk,
            order=2,
        )
        Banner.objects.create(
            title="Weekly Doubt Sessions Live",
            subtitle="Every Saturday 4 PM -- get your doubts resolved by IITians",
            image_url="https://images.unsplash.com/photo-1501504905252-473c47e087f8?w=1200",
            link_type="url",
            link_url="https://meet.google.com/example",
            order=3,
        )

        self.stdout.write("  Created banners")

        # ── Analytics ───────────────────────────────────────────
        for day_offset in range(30):
            date = (now - timedelta(days=day_offset)).date()
            daily_rev = Decimal(str(random.randint(2000, 15000)))
            daily_txns = random.randint(1, 8)
            DailyRevenue.objects.create(
                date=date,
                total_revenue=daily_rev,
                total_transactions=daily_txns,
            )
            for level in levels:
                LevelAnalytics.objects.create(
                    level=level,
                    date=date,
                    total_attempts=random.randint(0, 20),
                    total_passes=random.randint(0, 15),
                    total_failures=random.randint(0, 8),
                    total_purchases=random.randint(0, 5),
                    revenue=Decimal(str(random.randint(0, 5000))),
                )

        self.stdout.write("  Created 30 days of analytics data")

        # ── Summary ─────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS("\nFlush + Reseed complete!\n"))
        self.stdout.write("=" * 55)
        self.stdout.write("  CREDENTIALS")
        self.stdout.write("=" * 55)
        self.stdout.write("  Admin:   admin@iitprep.com    / Admin@123")
        self.stdout.write("  Staff:   staff@iitprep.com    / Staff@123")
        self.stdout.write("  Students (all use password Student@123):")
        for sd in students_data:
            self.stdout.write(f"    - {sd['email']}")
        self.stdout.write("=" * 55)
