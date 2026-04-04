"""
Create the onboarding (placement) exam with questions if it does not exist.

Safe to run on production — skips creation if an active onboarding exam
already exists.

Usage:  python manage.py seed_onboarding_exam
        python manage.py seed_onboarding_exam --force   # recreate even if one exists
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.exams.models import Exam, Option, Question
from apps.levels.models import Level

QUESTIONS = [
    # ── Physics ─────────────────────────────────────────────
    (
        "A ball is thrown vertically upward with velocity 20 m/s. What is the maximum height reached? (g = 10 m/s²)",
        "easy",
        [("20 m", True), ("40 m", False), ("10 m", False), ("30 m", False)],
        "Using v² = u² - 2gh, at max height v=0, so h = u²/2g = 400/20 = 20 m.",
    ),
    (
        "A block of mass 5 kg is placed on a frictionless surface. "
        "A horizontal force of 10 N is applied. What is the acceleration?",
        "easy",
        [("2 m/s²", True), ("5 m/s²", False), ("10 m/s²", False), ("1 m/s²", False)],
        "F = ma, so a = F/m = 10/5 = 2 m/s².",
    ),
    (
        "Two blocks of masses 3 kg and 5 kg are connected by a string over a "
        "frictionless pulley. Find the acceleration of the system.",
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
        "A satellite orbits Earth at height h = R (R = radius of Earth). "
        "What is the orbital velocity in terms of escape velocity vₑ at the surface?",
        "hard",
        [("vₑ / 2", True), ("vₑ / √2", False), ("vₑ / 4", False), ("vₑ √2", False)],
        "At h=R, v_orbital = √(gR/2). Since vₑ = √(2gR), v_orbital = vₑ/2.",
    ),
    # ── Chemistry ───────────────────────────────────────────
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
    # ── Mathematics ─────────────────────────────────────────
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
        "f'(x)=3x²-3=0 gives x=±1. f(1)=0, f(-1)=4. f=(x-1)²(x+2), so 3 real roots.",
    ),
    (
        "∫₀^π x sin(x) dx equals:",
        "hard",
        [("π", True), ("2π", False), ("0", False), ("π/2", False)],
        "Using integration by parts: = [-x cos x]₀^π + ∫cos x dx = π + [sin x]₀^π = π.",
    ),
]


class Command(BaseCommand):
    help = "Create the onboarding placement exam (safe for production)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing onboarding exam and recreate it",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        first_level = Level.objects.filter(is_active=True).order_by("order").first()
        if not first_level:
            self.stderr.write("No active levels found. Create levels first.")
            return

        existing = Exam.objects.filter(
            exam_type=Exam.ExamType.ONBOARDING,
            is_active=True,
        ).first()

        if existing and not options["force"]:
            self.stdout.write(f"Active onboarding exam already exists (id={existing.id}). Use --force to recreate.")
            return

        if existing and options["force"]:
            self.stdout.write(f"Deleting existing onboarding exam (id={existing.id})...")
            existing.delete()

        exam = Exam.objects.create(
            level=first_level,
            exam_type="onboarding",
            title="Placement Assessment",
            duration_minutes=45,
            total_marks=60,
            passing_percentage=Decimal("40.00"),
            num_questions=15,
            is_proctored=False,
        )

        for text, difficulty, opts, explanation in QUESTIONS:
            q = Question.objects.create(
                exam=exam,
                level=first_level,
                text=f"[Placement] {text}",
                difficulty=difficulty,
                question_type="mcq",
                marks=4,
                negative_marks=Decimal("0"),
                explanation=explanation,
            )
            for option_text, is_correct in opts:
                Option.objects.create(question=q, text=option_text, is_correct=is_correct)

        self.stdout.write(
            self.style.SUCCESS(
                f"Created onboarding exam (id={exam.id}) with {len(QUESTIONS)} questions on level '{first_level.name}'"
            )
        )
