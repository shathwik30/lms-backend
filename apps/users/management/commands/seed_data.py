import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analytics.models import DailyRevenue, LevelAnalytics
from apps.courses.models import Course, Session
from apps.doubts.models import DoubtReply, DoubtTicket
from apps.exams.models import Exam, ExamAttempt, Option, Question
from apps.feedback.models import SessionFeedback
from apps.home.models import Banner
from apps.levels.models import Level, Week
from apps.notifications.models import Notification
from apps.payments.models import PaymentTransaction, Purchase
from apps.progress.models import CourseProgress, LevelProgress, SessionProgress
from apps.users.models import StudentProfile, UserPreference

User = get_user_model()

# ─── Realistic Content Data ─────────────────────────────────────────────

LEVELS = [
    {
        "name": "Foundation",
        "order": 1,
        "price": Decimal("1999.00"),
        "validity_days": 180,
        "passing_percentage": Decimal("50.00"),
        "max_final_exam_attempts": 3,
        "description": "Build a rock-solid understanding of core concepts in Physics, Chemistry, and Mathematics. Ideal for students beginning their JEE/NEET preparation journey.",
    },
    {
        "name": "Intermediate",
        "order": 2,
        "price": Decimal("2999.00"),
        "validity_days": 180,
        "passing_percentage": Decimal("55.00"),
        "max_final_exam_attempts": 3,
        "description": "Strengthen problem-solving skills with application-level questions and multi-concept problems across all subjects.",
    },
    {
        "name": "Advanced",
        "order": 3,
        "price": Decimal("3999.00"),
        "validity_days": 240,
        "passing_percentage": Decimal("60.00"),
        "max_final_exam_attempts": 3,
        "description": "Master advanced techniques, tackle competition-level problems, and develop the analytical thinking needed for top ranks.",
    },
    {
        "name": "Elite",
        "order": 4,
        "price": Decimal("4999.00"),
        "validity_days": 365,
        "passing_percentage": Decimal("65.00"),
        "max_final_exam_attempts": 2,
        "description": "The ultimate tier for serious aspirants. Covers JEE Advanced level problems with comprehensive mock tests and timed practice.",
    },
]

COURSES_PER_LEVEL = {
    1: [
        ("Physics Fundamentals", "Mechanics, units & measurements, vectors, and basic kinematics."),
        ("Chemistry Basics", "Atomic structure, periodic table, chemical bonding, and stoichiometry."),
        ("Mathematics Essentials", "Sets, relations, functions, trigonometry, and coordinate geometry basics."),
    ],
    2: [
        ("Classical Mechanics", "Newton's laws in depth, work-energy theorem, rotational dynamics, and gravitation."),
        ("Physical & Inorganic Chemistry", "Thermodynamics, equilibrium, ionic equilibrium, and qualitative analysis."),
        ("Algebra & Calculus I", "Quadratics, sequences & series, limits, continuity, and differentiation."),
    ],
    3: [
        ("Electrodynamics & Waves", "Electrostatics, current electricity, magnetism, EMI, and wave optics."),
        ("Organic Chemistry", "GOC, reaction mechanisms, named reactions, and stereochemistry."),
        ("Calculus II & Vectors", "Integration, differential equations, 3D geometry, and vector algebra."),
    ],
    4: [
        ("Modern Physics & Optics", "Dual nature of matter, atomic models, nuclear physics, and ray optics."),
        (
            "Advanced Inorganic & Physical Chemistry",
            "Coordination compounds, metallurgy, electrochemistry, and surface chemistry.",
        ),
        ("Probability & Discrete Mathematics", "Permutations, combinations, probability, matrices, and determinants."),
    ],
}

WEEKS_PER_COURSE = {
    # Level 1
    "Physics Fundamentals": [
        "Units, Dimensions & Measurements",
        "Scalars and Vectors",
        "Kinematics in 1D",
        "Kinematics in 2D (Projectile & Circular Motion)",
    ],
    "Chemistry Basics": [
        "Atomic Structure & Quantum Numbers",
        "Periodic Table & Periodicity",
        "Chemical Bonding (Ionic & Covalent)",
        "Mole Concept & Stoichiometry",
    ],
    "Mathematics Essentials": [
        "Sets, Relations & Functions",
        "Trigonometric Ratios & Identities",
        "Coordinate Geometry — Straight Lines",
        "Coordinate Geometry — Circles & Conics Intro",
    ],
    # Level 2
    "Classical Mechanics": [
        "Newton's Laws of Motion",
        "Friction & Constraints",
        "Work, Energy & Power",
        "Rotational Dynamics & Moment of Inertia",
        "Gravitation & Satellite Motion",
    ],
    "Physical & Inorganic Chemistry": [
        "Thermodynamics — First & Second Law",
        "Chemical Equilibrium",
        "Ionic Equilibrium & pH",
        "Redox Reactions & Volumetric Analysis",
        "Qualitative Inorganic Analysis",
    ],
    "Algebra & Calculus I": [
        "Complex Numbers",
        "Quadratic Equations & Inequalities",
        "Sequences, Series & Mathematical Induction",
        "Limits & Continuity",
        "Differentiation & Applications",
    ],
    # Level 3
    "Electrodynamics & Waves": [
        "Electrostatics — Coulomb's Law & Field",
        "Gauss's Law & Potential",
        "Capacitors & Dielectrics",
        "Current Electricity & Circuits",
        "Magnetic Effects of Current",
        "Electromagnetic Induction & AC",
    ],
    "Organic Chemistry": [
        "General Organic Chemistry (GOC)",
        "Hydrocarbons — Alkanes, Alkenes, Alkynes",
        "Aromatic Compounds & Electrophilic Substitution",
        "Alcohols, Phenols & Ethers",
        "Aldehydes, Ketones & Carboxylic Acids",
        "Amines & Polymers",
    ],
    "Calculus II & Vectors": [
        "Indefinite Integration Techniques",
        "Definite Integrals & Area Under Curves",
        "Differential Equations",
        "Vector Algebra & Products",
        "3D Geometry — Lines & Planes",
        "Applications of Derivatives (Maxima/Minima)",
    ],
    # Level 4
    "Modern Physics & Optics": [
        "Ray Optics — Reflection & Refraction",
        "Wave Optics — Interference & Diffraction",
        "Dual Nature of Radiation & Matter",
        "Atoms — Bohr Model & Spectra",
        "Nuclei & Radioactivity",
    ],
    "Advanced Inorganic & Physical Chemistry": [
        "Coordination Compounds & Crystal Field Theory",
        "Metallurgy & Extractive Processes",
        "Electrochemistry & Nernst Equation",
        "Chemical Kinetics & Rate Laws",
        "Surface Chemistry & Colloids",
    ],
    "Probability & Discrete Mathematics": [
        "Permutations & Combinations",
        "Binomial Theorem",
        "Probability — Classical & Conditional",
        "Matrices & Determinants",
        "Linear Programming",
    ],
}

# Realistic session titles per subject area
VIDEO_SESSION_TEMPLATES = [
    "Concept Introduction — {topic}",
    "Solved Examples — {topic}",
    "Problem-Solving Strategies — {topic}",
]

RESOURCE_SESSION_TEMPLATES = [
    "Formula Sheet & Quick Reference — {topic}",
]

STUDENT_NAMES = [
    ("Aarav Sharma", "aarav.sharma@gmail.com", "9876543210"),
    ("Priya Patel", "priya.patel@gmail.com", "9876543211"),
    ("Rohan Mehta", "rohan.mehta@outlook.com", "9876543212"),
    ("Ananya Singh", "ananya.singh@gmail.com", "9876543213"),
    ("Vikram Reddy", "vikram.reddy@yahoo.com", "9876543214"),
    ("Sneha Gupta", "sneha.gupta@gmail.com", "9876543215"),
    ("Arjun Nair", "arjun.nair@outlook.com", "9876543216"),
    ("Kavya Iyer", "kavya.iyer@gmail.com", "9876543217"),
    ("Aditya Joshi", "aditya.joshi@gmail.com", "9876543218"),
    ("Meera Krishnan", "meera.krishnan@yahoo.com", "9876543219"),
    ("Rahul Verma", "rahul.verma@gmail.com", "9876543220"),
    ("Ishita Banerjee", "ishita.banerjee@gmail.com", "9876543221"),
    ("Karthik Sundaram", "karthik.sundaram@outlook.com", "9876543222"),
    ("Divya Rao", "divya.rao@gmail.com", "9876543223"),
    ("Nikhil Deshmukh", "nikhil.deshmukh@gmail.com", "9876543224"),
    ("Pooja Mishra", "pooja.mishra@yahoo.com", "9876543225"),
    ("Siddharth Kapoor", "siddharth.kapoor@gmail.com", "9876543226"),
    ("Riya Agarwal", "riya.agarwal@gmail.com", "9876543227"),
    ("Amit Choudhary", "amit.choudhary@outlook.com", "9876543228"),
    ("Neha Saxena", "neha.saxena@gmail.com", "9876543229"),
    ("Varun Bhatt", "varun.bhatt@gmail.com", "9876543230"),
    ("Shreya Tiwari", "shreya.tiwari@yahoo.com", "9876543231"),
    ("Manish Kumar", "manish.kumar@gmail.com", "9876543232"),
    ("Tanvi Deshpande", "tanvi.deshpande@gmail.com", "9876543233"),
    ("Raj Malhotra", "raj.malhotra@outlook.com", "9876543234"),
    ("Anjali Pillai", "anjali.pillai@gmail.com", "9876543235"),
    ("Deepak Pandey", "deepak.pandey@gmail.com", "9876543236"),
    ("Simran Kaur", "simran.kaur@yahoo.com", "9876543237"),
    ("Harsh Vardhan", "harsh.vardhan@gmail.com", "9876543238"),
    ("Nandini Bose", "nandini.bose@gmail.com", "9876543239"),
]

ADMIN_STAFF = [
    ("Dr. Rajesh Kumar", "rajesh.kumar@lms.com"),
    ("Prof. Sunita Rao", "sunita.rao@lms.com"),
    ("Ankit Srivastava", "ankit.srivastava@lms.com"),
]

QUESTION_BANK = {
    "Physics Fundamentals": [
        (
            "A car accelerates uniformly from rest to 72 km/h in 10 seconds. What is the acceleration?",
            "easy",
            [("2 m/s²", True), ("7.2 m/s²", False), ("20 m/s²", False), ("0.2 m/s²", False)],
            "Convert 72 km/h to 20 m/s. Then a = (20-0)/10 = 2 m/s².",
        ),
        (
            "The dimensional formula of torque is the same as that of:",
            "medium",
            [("Work", True), ("Force", False), ("Momentum", False), ("Power", False)],
            "Torque = Force × Distance = [MLT⁻²][L] = [ML²T⁻²], same as work.",
        ),
        (
            "A projectile is fired at 60° with the horizontal. What is the ratio of its range to its maximum height?",
            "hard",
            [("2√3", True), ("√3", False), ("4√3", False), ("√3/2", False)],
            "R/H = (u²sin2θ/g) / (u²sin²θ/2g) = 2cosθ/sinθ = 2cot60° = 2/√3... Actually R/H = 4cotθ = 4/√3 = 4√3/3. Let me recalculate: R = u²sin120°/g, H = u²sin²60°/(2g). R/H = 2sin60°cos60°/(sin²60°/2) = 4cos60°/sin60° = 4×(1/2)/(√3/2) = 4/√3 = 4√3/3.",
        ),
        (
            "Two vectors of magnitudes 3 and 4 are perpendicular. What is the magnitude of their resultant?",
            "easy",
            [("5", True), ("7", False), ("1", False), ("12", False)],
            "For perpendicular vectors: |R| = √(3² + 4²) = √25 = 5.",
        ),
        (
            "A ball is thrown vertically upward with velocity 20 m/s. The maximum height reached is (g=10 m/s²):",
            "easy",
            [("20 m", True), ("40 m", False), ("10 m", False), ("200 m", False)],
            "H = u²/(2g) = 400/20 = 20 m.",
        ),
        (
            "The SI unit of angular momentum is:",
            "easy",
            [("kg m²/s", True), ("kg m/s", False), ("N·m", False), ("J·s/m", False)],
            "Angular momentum L = Iω, SI unit = kg·m²·s⁻¹ = kg m²/s.",
        ),
        (
            "In uniform circular motion, the acceleration is directed:",
            "medium",
            [
                ("Towards the center", True),
                ("Away from center", False),
                ("Along the tangent", False),
                ("At 45° to radius", False),
            ],
            "In UCM, acceleration is centripetal — always pointing toward the center.",
        ),
        (
            "A body of mass 5 kg is moving with velocity 10 m/s. A force is applied for 2 seconds and the velocity becomes 14 m/s. The force applied is:",
            "medium",
            [("10 N", True), ("5 N", False), ("20 N", False), ("15 N", False)],
            "F = ma = m(v-u)/t = 5×(14-10)/2 = 5×2 = 10 N.",
        ),
    ],
    "Chemistry Basics": [
        (
            "The maximum number of electrons in the 3rd shell is:",
            "easy",
            [("18", True), ("8", False), ("32", False), ("2", False)],
            "Max electrons in nth shell = 2n² = 2(3²) = 18.",
        ),
        (
            "Which of the following has the highest ionization energy?",
            "medium",
            [("Helium", True), ("Neon", False), ("Lithium", False), ("Sodium", False)],
            "Helium has the highest IE among all elements due to its small size and complete 1s² configuration.",
        ),
        (
            "The shape of SF₆ molecule is:",
            "medium",
            [("Octahedral", True), ("Tetrahedral", False), ("Trigonal bipyramidal", False), ("Square planar", False)],
            "SF₆ has sp³d² hybridization with 6 bonding pairs and 0 lone pairs → octahedral.",
        ),
        (
            "How many moles of water are produced when 2 moles of H₂ react with excess O₂?",
            "easy",
            [("2 moles", True), ("1 mole", False), ("4 moles", False), ("0.5 moles", False)],
            "2H₂ + O₂ → 2H₂O. 2 moles H₂ produce 2 moles H₂O.",
        ),
        (
            "The bond angle in water molecule is approximately:",
            "easy",
            [("104.5°", True), ("109.5°", False), ("120°", False), ("180°", False)],
            "Due to 2 lone pairs on oxygen, the bond angle is compressed from 109.5° to 104.5°.",
        ),
        (
            "Which quantum number determines the shape of an orbital?",
            "easy",
            [("Azimuthal (l)", True), ("Principal (n)", False), ("Magnetic (ml)", False), ("Spin (ms)", False)],
            "The azimuthal quantum number l determines the shape: l=0 sphere, l=1 dumbbell, etc.",
        ),
        (
            "The element with atomic number 29 belongs to which block?",
            "medium",
            [("d-block", True), ("s-block", False), ("p-block", False), ("f-block", False)],
            "Z=29 is Copper [Ar] 3d¹⁰4s¹, a d-block element.",
        ),
        (
            "Covalent bond is formed by:",
            "easy",
            [
                ("Sharing of electrons", True),
                ("Transfer of electrons", False),
                ("Sharing of protons", False),
                ("Electrostatic attraction", False),
            ],
            "Covalent bonds are formed by mutual sharing of electron pairs between atoms.",
        ),
    ],
    "Mathematics Essentials": [
        (
            "If A = {1,2,3} and B = {2,3,4}, then A ∩ B is:",
            "easy",
            [("{2,3}", True), ("{1,2,3,4}", False), ("{1,4}", False), ("{}", False)],
            "A ∩ B contains elements common to both sets = {2,3}.",
        ),
        (
            "The value of sin²45° + cos²45° is:",
            "easy",
            [("1", True), ("0", False), ("√2", False), ("1/2", False)],
            "This is the Pythagorean identity: sin²θ + cos²θ = 1 for any θ.",
        ),
        (
            "The slope of the line 3x + 4y - 12 = 0 is:",
            "easy",
            [("-3/4", True), ("3/4", False), ("4/3", False), ("-4/3", False)],
            "Rearranging: y = -3x/4 + 3. Slope = -3/4.",
        ),
        (
            "If f(x) = x² - 4x + 3, then f(1) is:",
            "easy",
            [("0", True), ("1", False), ("-1", False), ("3", False)],
            "f(1) = 1 - 4 + 3 = 0.",
        ),
        (
            "The equation x² + y² - 6x + 8y + 9 = 0 represents a circle with radius:",
            "medium",
            [("4", True), ("3", False), ("5", False), ("9", False)],
            "Center (3,-4), r² = 9+16-9 = 16, r = 4.",
        ),
        (
            "The value of tan(π/4) is:",
            "easy",
            [("1", True), ("0", False), ("√3", False), ("1/√3", False)],
            "tan(45°) = sin45°/cos45° = 1.",
        ),
        (
            "The domain of f(x) = √(x-2) is:",
            "medium",
            [("[2, ∞)", True), ("(-∞, 2]", False), ("(2, ∞)", False), ("ℝ", False)],
            "We need x-2 ≥ 0, so x ≥ 2. Domain = [2, ∞).",
        ),
        (
            "If sin A = 3/5, then cos A is (A is in first quadrant):",
            "easy",
            [("4/5", True), ("3/5", False), ("5/3", False), ("-4/5", False)],
            "cos A = √(1-sin²A) = √(1-9/25) = √(16/25) = 4/5 (positive in Q1).",
        ),
    ],
    "Classical Mechanics": [
        (
            "A block of mass 2 kg on a frictionless surface is acted upon by a force F = 6t N. The velocity at t = 3s is:",
            "medium",
            [("13.5 m/s", True), ("9 m/s", False), ("27 m/s", False), ("4.5 m/s", False)],
            "a = F/m = 3t. v = ∫0→3 3t dt = 3t²/2|₀³ = 27/2 = 13.5 m/s.",
        ),
        (
            "The coefficient of friction between a block and surface is 0.4. The angle of friction is:",
            "medium",
            [("~21.8°", True), ("~30°", False), ("~45°", False), ("~11.3°", False)],
            "tan(θ) = μ = 0.4, θ = tan⁻¹(0.4) ≈ 21.8°.",
        ),
        (
            "A spring of spring constant 200 N/m is compressed by 0.1 m. The potential energy stored is:",
            "easy",
            [("1 J", True), ("2 J", False), ("0.5 J", False), ("10 J", False)],
            "PE = ½kx² = ½×200×0.01 = 1 J.",
        ),
        (
            "The moment of inertia of a solid sphere about its diameter is:",
            "medium",
            [("2MR²/5", True), ("MR²/2", False), ("2MR²/3", False), ("MR²", False)],
            "For a solid sphere, I = 2MR²/5 about any diameter.",
        ),
        (
            "The escape velocity from Earth's surface is approximately:",
            "easy",
            [("11.2 km/s", True), ("7.9 km/s", False), ("3.1 km/s", False), ("15.4 km/s", False)],
            "vₑ = √(2gR) ≈ √(2×9.8×6.4×10⁶) ≈ 11.2 km/s.",
        ),
        (
            "A body moving in a circle of radius 2m completes one revolution in 4s. Its centripetal acceleration is:",
            "medium",
            [("π² m/s²", True), ("2π² m/s²", False), ("4π² m/s²", False), ("π²/2 m/s²", False)],
            "ω = 2π/T = 2π/4 = π/2 rad/s. a = ω²r = (π/2)²×2 = π²/2... Let me recalculate: a = ω²r = (π/2)²×2 = π²×2/4 = π²/2 m/s².",
        ),
        (
            "In an elastic collision between two equal masses, the velocities are:",
            "medium",
            [("Exchanged", True), ("Both become zero", False), ("Unchanged", False), ("Both halved", False)],
            "In a 1D elastic collision between equal masses, the velocities are simply exchanged.",
        ),
        (
            "Power is defined as:",
            "easy",
            [
                ("Rate of doing work", True),
                ("Work × Time", False),
                ("Force × Displacement", False),
                ("Force / Time", False),
            ],
            "Power = dW/dt = rate of doing work. SI unit: Watt.",
        ),
    ],
    "Physical & Inorganic Chemistry": [
        (
            "For an exothermic reaction at constant pressure, ΔH is:",
            "easy",
            [("Negative", True), ("Positive", False), ("Zero", False), ("Undefined", False)],
            "Exothermic means heat is released, so ΔH < 0.",
        ),
        (
            "Le Chatelier's principle is applicable to:",
            "medium",
            [
                ("Equilibrium systems", True),
                ("Irreversible reactions", False),
                ("Spontaneous processes only", False),
                ("Endothermic reactions only", False),
            ],
            "Le Chatelier's principle applies to systems at equilibrium when subjected to a stress.",
        ),
        (
            "The pH of a 0.01 M HCl solution is:",
            "easy",
            [("2", True), ("1", False), ("0.01", False), ("7", False)],
            "pH = -log[H⁺] = -log(0.01) = -log(10⁻²) = 2.",
        ),
        (
            "In the reaction 2KMnO₄ + 16HCl → ..., KMnO₄ acts as:",
            "medium",
            [("Oxidizing agent", True), ("Reducing agent", False), ("Catalyst", False), ("Acid", False)],
            "KMnO₄ is reduced (Mn goes from +7 to +2), so it acts as an oxidizing agent.",
        ),
        (
            "The flame test color for sodium compounds is:",
            "easy",
            [("Golden yellow", True), ("Crimson red", False), ("Apple green", False), ("Lilac", False)],
            "Sodium gives a characteristic golden yellow flame.",
        ),
        (
            "The enthalpy of formation of an element in its standard state is:",
            "easy",
            [("Zero", True), ("Positive", False), ("Negative", False), ("Cannot be determined", False)],
            "By convention, ΔHf° of an element in its standard state is zero.",
        ),
        (
            "Which of the following is an intensive property?",
            "medium",
            [("Temperature", True), ("Volume", False), ("Enthalpy", False), ("Internal energy", False)],
            "Temperature does not depend on the amount of substance — it is intensive.",
        ),
        (
            "The conjugate base of H₂O is:",
            "easy",
            [("OH⁻", True), ("H₃O⁺", False), ("O²⁻", False), ("H⁺", False)],
            "When H₂O donates a proton, it becomes OH⁻ (its conjugate base).",
        ),
    ],
    "Algebra & Calculus I": [
        (
            "The modulus of the complex number 3 + 4i is:",
            "easy",
            [("5", True), ("7", False), ("√7", False), ("25", False)],
            "|3+4i| = √(9+16) = √25 = 5.",
        ),
        (
            "If the roots of x² - 5x + 6 = 0 are α and β, then α + β is:",
            "easy",
            [("5", True), ("6", False), ("-5", False), ("-6", False)],
            "By Vieta's formulas, sum of roots = -(-5)/1 = 5.",
        ),
        (
            "The sum of the first 10 terms of the AP 2, 5, 8, ... is:",
            "medium",
            [("155", True), ("150", False), ("160", False), ("145", False)],
            "a=2, d=3. S₁₀ = 10/2 × [2×2 + 9×3] = 5 × [4+27] = 5×31 = 155.",
        ),
        (
            "lim(x→0) sin(x)/x equals:",
            "easy",
            [("1", True), ("0", False), ("∞", False), ("Does not exist", False)],
            "This is a fundamental limit: lim(x→0) sinx/x = 1.",
        ),
        (
            "The derivative of x³ - 3x² + 2x is:",
            "easy",
            [("3x² - 6x + 2", True), ("x³ - 3x²", False), ("3x² - 6x", False), ("x² - 6x + 2", False)],
            "d/dx(x³) = 3x², d/dx(-3x²) = -6x, d/dx(2x) = 2.",
        ),
        (
            "If |z₁| = 2 and |z₂| = 3, the maximum value of |z₁ + z₂| is:",
            "medium",
            [("5", True), ("6", False), ("√13", False), ("1", False)],
            "By triangle inequality, |z₁+z₂| ≤ |z₁|+|z₂| = 2+3 = 5.",
        ),
        (
            "The nth term of the GP 2, 6, 18, ... is:",
            "medium",
            [("2 × 3ⁿ⁻¹", True), ("2 × 3ⁿ", False), ("3 × 2ⁿ⁻¹", False), ("6ⁿ⁻¹", False)],
            "a=2, r=3. Tₙ = arⁿ⁻¹ = 2×3ⁿ⁻¹.",
        ),
        (
            "The function f(x) = |x| is continuous at x=0 but:",
            "medium",
            [
                ("Not differentiable at x=0", True),
                ("Differentiable everywhere", False),
                ("Discontinuous at x=0", False),
                ("Not defined at x=0", False),
            ],
            "f(x)=|x| has a sharp corner at x=0 — left derivative is -1, right is +1.",
        ),
    ],
    "Electrodynamics & Waves": [
        (
            "The electric field inside a conductor in electrostatic equilibrium is:",
            "easy",
            [("Zero", True), ("Maximum", False), ("Equal to surface field", False), ("Infinite", False)],
            "In electrostatic equilibrium, charges reside on the surface and E=0 inside.",
        ),
        (
            "Gauss's law relates electric flux to:",
            "easy",
            [
                ("Enclosed charge", True),
                ("Total charge", False),
                ("Surface area", False),
                ("Electric potential", False),
            ],
            "Gauss's law: ∮E·dA = Q_enclosed/ε₀.",
        ),
        (
            "Two capacitors of 3μF and 6μF in series have equivalent capacitance:",
            "medium",
            [("2 μF", True), ("9 μF", False), ("4.5 μF", False), ("1.5 μF", False)],
            "1/C = 1/3 + 1/6 = 2/6 + 1/6 = 3/6 = 1/2. C = 2 μF.",
        ),
        (
            "The resistance of a wire is doubled when its length is:",
            "easy",
            [("Doubled", True), ("Halved", False), ("Squared", False), ("Unchanged", False)],
            "R = ρL/A. If L doubles, R doubles (for same material and cross-section).",
        ),
        (
            "The force on a current-carrying conductor in a magnetic field is given by:",
            "medium",
            [("F = BIL sinθ", True), ("F = BIL cosθ", False), ("F = BIL", False), ("F = BIL/sinθ", False)],
            "The force is F = BIL sinθ, where θ is the angle between I and B.",
        ),
        (
            "In electromagnetic induction, the induced EMF is proportional to:",
            "medium",
            [
                ("Rate of change of flux", True),
                ("Magnetic flux", False),
                ("Area of loop", False),
                ("Resistance of loop", False),
            ],
            "Faraday's law: EMF = -dΦ/dt. EMF depends on rate of change of flux.",
        ),
        (
            "The unit of magnetic flux is:",
            "easy",
            [("Weber", True), ("Tesla", False), ("Henry", False), ("Gauss", False)],
            "Magnetic flux Φ = B·A, measured in Weber (Wb) = T·m².",
        ),
        (
            "In Young's double slit experiment, fringe width increases when:",
            "hard",
            [
                ("Wavelength increases", True),
                ("Slit separation increases", False),
                ("Screen distance decreases", False),
                ("Slit width increases", False),
            ],
            "Fringe width β = λD/d. Increases with λ and D, decreases with d.",
        ),
    ],
    "Organic Chemistry": [
        (
            "The IUPAC name of CH₃CHO is:",
            "easy",
            [("Ethanal", True), ("Methanal", False), ("Propanal", False), ("Ethanol", False)],
            "CH₃CHO is a 2-carbon aldehyde → ethanal.",
        ),
        (
            "Markovnikov's rule applies to addition of HBr to:",
            "medium",
            [("Propene", True), ("Ethene", False), ("Benzene", False), ("Acetylene", False)],
            "Markovnikov's rule applies to unsymmetrical alkenes like propene.",
        ),
        (
            "Benzene undergoes:",
            "medium",
            [
                ("Electrophilic substitution", True),
                ("Nucleophilic substitution", False),
                ("Electrophilic addition", False),
                ("Free radical addition", False),
            ],
            "Benzene's aromatic stability favors substitution over addition.",
        ),
        (
            "The functional group -OH is characteristic of:",
            "easy",
            [("Alcohols", True), ("Aldehydes", False), ("Ketones", False), ("Amines", False)],
            "The hydroxyl group -OH defines alcohols (and phenols).",
        ),
        (
            "Which reagent converts an aldehyde to a carboxylic acid?",
            "medium",
            [("KMnO₄", True), ("LiAlH₄", False), ("NaBH₄", False), ("Zn-Hg/HCl", False)],
            "KMnO₄ is a strong oxidizer that oxidizes aldehydes to carboxylic acids.",
        ),
        (
            "Primary amines react with HNO₂ to form:",
            "hard",
            [("Alcohols + N₂", True), ("Nitrosamines", False), ("Diazonium salts only", False), ("No reaction", False)],
            "Aliphatic primary amines + HNO₂ → alcohol + N₂ + H₂O (unstable diazonium).",
        ),
        (
            "The hybridization of carbon in benzene is:",
            "easy",
            [("sp²", True), ("sp³", False), ("sp", False), ("sp³d", False)],
            "Each carbon in benzene is sp² hybridized with one unhybridized p orbital.",
        ),
        (
            "Tollen's reagent is used to test for:",
            "easy",
            [("Aldehydes", True), ("Ketones", False), ("Alcohols", False), ("Ethers", False)],
            "Tollen's test (silver mirror) is specific for aldehydes — they reduce Ag⁺ to Ag.",
        ),
    ],
    "Calculus II & Vectors": [
        (
            "∫ 1/x dx equals:",
            "easy",
            [("ln|x| + C", True), ("x² + C", False), ("1/x² + C", False), ("e^x + C", False)],
            "The integral of 1/x is the natural logarithm: ln|x| + C.",
        ),
        (
            "The area under y = x² from x=0 to x=3 is:",
            "medium",
            [("9", True), ("27", False), ("3", False), ("6", False)],
            "∫₀³ x² dx = [x³/3]₀³ = 27/3 = 9.",
        ),
        (
            "The order of the differential equation dy/dx + y = e^x is:",
            "easy",
            [("1", True), ("2", False), ("0", False), ("3", False)],
            "The highest derivative is dy/dx (first order), so the ODE is of order 1.",
        ),
        (
            "If a = 2i + 3j and b = i - j, then a · b is:",
            "easy",
            [("-1", True), ("5", False), ("1", False), ("-5", False)],
            "a·b = 2(1) + 3(-1) = 2 - 3 = -1.",
        ),
        (
            "The direction cosines of the line joining (1,2,3) and (4,6,3) satisfy l² + m² + n² =:",
            "easy",
            [("1", True), ("0", False), ("3", False), ("It depends", False)],
            "Direction cosines always satisfy l² + m² + n² = 1 by definition.",
        ),
        (
            "The maximum value of f(x) = -x² + 4x - 3 is:",
            "medium",
            [("1", True), ("3", False), ("-3", False), ("4", False)],
            "f'(x) = -2x+4 = 0 → x=2. f(2) = -4+8-3 = 1. Since f''(2) = -2 < 0, it's a maximum.",
        ),
        (
            "∫₀^π sinx dx equals:",
            "easy",
            [("2", True), ("0", False), ("1", False), ("π", False)],
            "∫₀^π sinx dx = [-cosx]₀^π = -cosπ + cos0 = 1+1 = 2.",
        ),
        (
            "The cross product of parallel vectors is:",
            "easy",
            [("Zero vector", True), ("Unit vector", False), ("Same as dot product", False), ("Undefined", False)],
            "If a ∥ b, then a × b = |a||b|sin0° n̂ = 0.",
        ),
    ],
    "Modern Physics & Optics": [
        (
            "The focal length of a concave mirror of radius 20 cm is:",
            "easy",
            [("10 cm", True), ("20 cm", False), ("40 cm", False), ("5 cm", False)],
            "f = R/2 = 20/2 = 10 cm.",
        ),
        (
            "In Young's double slit experiment, central fringe is:",
            "easy",
            [("Bright", True), ("Dark", False), ("Depends on wavelength", False), ("Missing", False)],
            "At the center, path difference = 0, so constructive interference → bright fringe.",
        ),
        (
            "The photoelectric effect demonstrates:",
            "medium",
            [
                ("Particle nature of light", True),
                ("Wave nature of light", False),
                ("Dual nature of matter", False),
                ("Interference", False),
            ],
            "Photoelectric effect shows light behaves as particles (photons) with energy hν.",
        ),
        (
            "In Bohr's model, the radius of the nth orbit is proportional to:",
            "medium",
            [("n²", True), ("n", False), ("1/n", False), ("1/n²", False)],
            "rₙ = a₀n²/Z. The radius is proportional to n².",
        ),
        (
            "The half-life of a radioactive substance is 10 years. After 30 years, the fraction remaining is:",
            "medium",
            [("1/8", True), ("1/4", False), ("1/3", False), ("1/16", False)],
            "30 years = 3 half-lives. Fraction = (1/2)³ = 1/8.",
        ),
        (
            "The energy of a photon with wavelength 600 nm is approximately (h=6.6×10⁻³⁴):",
            "hard",
            [("3.3 × 10⁻¹⁹ J", True), ("6.6 × 10⁻¹⁹ J", False), ("1.1 × 10⁻¹⁹ J", False), ("3.3 × 10⁻³⁴ J", False)],
            "E = hc/λ = (6.6×10⁻³⁴ × 3×10⁸) / (600×10⁻⁹) = 3.3×10⁻¹⁹ J.",
        ),
        (
            "Snell's law states that:",
            "easy",
            [
                ("n₁ sinθ₁ = n₂ sinθ₂", True),
                ("n₁ cosθ₁ = n₂ cosθ₂", False),
                ("n₁/sinθ₁ = n₂/sinθ₂", False),
                ("n₁ tanθ₁ = n₂ tanθ₂", False),
            ],
            "Snell's law of refraction: n₁ sinθ₁ = n₂ sinθ₂.",
        ),
        (
            "Total internal reflection occurs when light travels from:",
            "medium",
            [
                ("Denser to rarer medium", True),
                ("Rarer to denser medium", False),
                ("Any two media", False),
                ("Vacuum to glass", False),
            ],
            "TIR occurs when light goes from optically denser to rarer medium at angle > critical angle.",
        ),
    ],
    "Advanced Inorganic & Physical Chemistry": [
        (
            "The coordination number in [Co(NH₃)₆]³⁺ is:",
            "easy",
            [("6", True), ("3", False), ("12", False), ("4", False)],
            "Co is surrounded by 6 NH₃ ligands, so coordination number = 6.",
        ),
        (
            "In the extraction of aluminium, the ore used is:",
            "easy",
            [("Bauxite", True), ("Haematite", False), ("Galena", False), ("Cinnabar", False)],
            "Aluminium is extracted from bauxite (Al₂O₃·2H₂O) by Hall-Héroult process.",
        ),
        (
            "The standard electrode potential of SHE is:",
            "easy",
            [("0 V", True), ("1 V", False), ("-1 V", False), ("0.5 V", False)],
            "By convention, the Standard Hydrogen Electrode (SHE) potential is defined as 0 V.",
        ),
        (
            "For a first-order reaction, the half-life is:",
            "medium",
            [
                ("Independent of concentration", True),
                ("Proportional to concentration", False),
                ("Inversely proportional to concentration", False),
                ("Proportional to concentration²", False),
            ],
            "For first-order: t₁/₂ = 0.693/k, independent of initial concentration.",
        ),
        (
            "Colloidal solutions show Tyndall effect because of:",
            "medium",
            [
                ("Scattering of light", True),
                ("Absorption of light", False),
                ("Reflection of light", False),
                ("Refraction of light", False),
            ],
            "Colloidal particles scatter light (Tyndall effect) due to their size (1-1000 nm).",
        ),
        (
            "Crystal field splitting energy is larger in:",
            "hard",
            [
                ("Octahedral complexes", True),
                ("Tetrahedral complexes", False),
                ("Square planar complexes", False),
                ("Linear complexes", False),
            ],
            "Δₒ (octahedral) > Δₜ (tetrahedral). Specifically, Δₜ = 4/9 Δₒ.",
        ),
        (
            "The Nernst equation is used to calculate:",
            "medium",
            [
                ("Cell potential at non-standard conditions", True),
                ("Standard cell potential", False),
                ("Gibbs free energy", False),
                ("Equilibrium constant directly", False),
            ],
            "Nernst equation: E = E° - (RT/nF)lnQ, gives cell potential at non-standard conditions.",
        ),
        (
            "Which metal is extracted by leaching with cyanide solution?",
            "medium",
            [("Gold", True), ("Iron", False), ("Aluminium", False), ("Copper", False)],
            "Gold is extracted by cyanide leaching: 4Au + 8NaCN + 2H₂O + O₂ → 4Na[Au(CN)₂] + 4NaOH.",
        ),
    ],
    "Probability & Discrete Mathematics": [
        (
            "The number of ways to arrange 5 books on a shelf is:",
            "easy",
            [("120", True), ("25", False), ("60", False), ("24", False)],
            "5! = 5×4×3×2×1 = 120.",
        ),
        (
            "The coefficient of x³ in (1+x)⁵ is:",
            "medium",
            [("10", True), ("5", False), ("15", False), ("20", False)],
            "C(5,3) = 5!/(3!2!) = 10.",
        ),
        (
            "If P(A) = 0.3 and P(B) = 0.4, and A, B are independent, then P(A∩B) is:",
            "medium",
            [("0.12", True), ("0.7", False), ("0.1", False), ("0.3", False)],
            "For independent events: P(A∩B) = P(A)×P(B) = 0.3×0.4 = 0.12.",
        ),
        (
            "The determinant of a 2×2 identity matrix is:",
            "easy",
            [("1", True), ("0", False), ("2", False), ("-1", False)],
            "det(I₂) = 1×1 - 0×0 = 1.",
        ),
        (
            "In linear programming, the feasible region is:",
            "medium",
            [
                ("Intersection of all constraints", True),
                ("Union of all constraints", False),
                ("Always unbounded", False),
                ("A single point", False),
            ],
            "The feasible region is the set of all points satisfying all constraints simultaneously.",
        ),
        (
            "If A is a 3×3 matrix with det(A) = 5, then det(2A) is:",
            "hard",
            [("40", True), ("10", False), ("20", False), ("80", False)],
            "det(kA) = k³ det(A) for 3×3 matrix. det(2A) = 2³×5 = 40.",
        ),
        (
            "The number of diagonals in a hexagon is:",
            "medium",
            [("9", True), ("6", False), ("12", False), ("3", False)],
            "Diagonals = n(n-3)/2 = 6(3)/2 = 9.",
        ),
        (
            "The probability of getting at least one head in 3 coin tosses is:",
            "easy",
            [("7/8", True), ("1/8", False), ("3/8", False), ("1/2", False)],
            "P(at least 1 head) = 1 - P(no head) = 1 - (1/2)³ = 1 - 1/8 = 7/8.",
        ),
    ],
}

DOUBT_TITLES = [
    "Can you explain the derivation of this formula?",
    "Why does this approach not work for this type of problem?",
    "I'm confused about when to apply this theorem",
    "How to solve problems involving multiple concepts?",
    "What's the difference between these two methods?",
    "Need clarification on the sign convention used here",
    "Is there a shortcut for solving these types of questions?",
    "I keep getting the wrong answer for this problem",
    "Can you provide more practice problems on this topic?",
    "The video explanation was too fast, can you re-explain?",
    "How is this formula derived from first principles?",
    "What are the common mistakes to avoid in this chapter?",
]

BANNER_DATA = [
    (
        "New Session Alert: JEE 2026 Batch Open!",
        "Register now and get 20% early bird discount",
        "https://cdn.example.com/banners/jee-2026-batch.jpg",
    ),
    (
        "Free Mock Test Series",
        "Attempt our free All-India mock test every Sunday",
        "https://cdn.example.com/banners/free-mock-test.jpg",
    ),
    (
        "Master Organic Chemistry",
        "Join our special crash course on reaction mechanisms",
        "https://cdn.example.com/banners/organic-chem.jpg",
    ),
    (
        "Toppers' Strategies Webinar",
        "Learn from last year's AIR Top 100 rankers",
        "https://cdn.example.com/banners/toppers-webinar.jpg",
    ),
    (
        "Doubt Resolution: 24/7",
        "Get your doubts resolved within 2 hours, guaranteed",
        "https://cdn.example.com/banners/doubt-resolution.jpg",
    ),
]


class Command(BaseCommand):
    help = "Seed the database with realistic data for development and testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing data before seeding",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing all existing data...")
            self._flush_all()

        random.seed(42)  # Reproducible randomness
        now = timezone.now()

        self.stdout.write("\nSeeding database with realistic data...")

        # ── 1. Admin & Staff ──
        self._create_admin()
        staff_users = self._create_staff()

        # ── 2. Levels ──
        levels = self._create_levels()

        # ── 3. Courses, Weeks, Sessions, Resources ──
        courses, all_weeks, all_sessions = self._create_curriculum(levels)

        # ── 4. Questions & Exams ──
        self._create_questions_and_exams(levels, courses, all_weeks)

        # ── 5. Students ──
        students = self._create_students(levels)

        # ── 6. Purchases & Transactions ──
        self._create_purchases(students, levels, now)

        # ── 7. Progress Data ──
        self._create_progress(students, levels, courses, all_sessions, now)

        # ── 8. Exam Attempts ──
        self._create_exam_attempts(students, levels, now)

        # ── 9. Doubts & Replies ──
        self._create_doubts(students, staff_users, all_sessions, now)

        # ── 10. Feedback ──
        self._create_feedback(students, all_sessions)

        # ── 11. Notifications ──
        self._create_notifications(students, levels, now)

        # ── 12. Banners ──
        self._create_banners()

        # ── 13. Analytics ──
        self._create_analytics(levels, now)

        self.stdout.write(self.style.SUCCESS("\nSeed complete!"))
        self.stdout.write(self.style.SUCCESS("  Admin login:    admin@lms.com / admin123"))
        self.stdout.write(self.style.SUCCESS("  Staff logins:   rajesh.kumar@lms.com / staff123"))
        self.stdout.write(self.style.SUCCESS("  Student login:  aarav.sharma@gmail.com / student123"))
        self.stdout.write(self.style.SUCCESS(f"  Total students: {len(students)}"))

    # ─── Flush ────────────────────────────────────────────────────────────

    def _flush_all(self):
        from django.apps import apps

        # Delete in reverse dependency order
        models_to_flush = [
            "analytics.LevelAnalytics",
            "analytics.DailyRevenue",
            "notifications.Notification",
            "feedback.SessionFeedback",
            "doubts.DoubtReply",
            "doubts.DoubtTicket",
            "exams.ProctoringViolation",
            "exams.AttemptQuestion",
            "exams.ExamAttempt",
            "progress.SessionProgress",
            "progress.CourseProgress",
            "progress.LevelProgress",
            "payments.PaymentTransaction",
            "payments.Purchase",
            "exams.Option",
            "exams.Question",
            "exams.Exam",
            "courses.Resource",
            "courses.Bookmark",
            "courses.Session",
            "levels.Week",
            "courses.Course",
            "levels.Level",
            "home.Banner",
            "users.UserPreference",
            "users.IssueReport",
            "users.StudentProfile",
            "users.User",
        ]
        for label in models_to_flush:
            app_label, model_name = label.split(".")
            try:
                model = apps.get_model(app_label, model_name)
                count = model.objects.count()
                if count:
                    model.objects.all().delete()
                    self.stdout.write(f"  Deleted {count} {label} records")
            except LookupError:
                pass
        self.stdout.write(self.style.SUCCESS("  Flush complete.\n"))

    # ─── 1. Admin & Staff ─────────────────────────────────────────────────

    def _create_admin(self):
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
        self.stdout.write(self.style.SUCCESS("  [1/14] Admin created"))
        return admin

    def _create_staff(self):
        staff_users = []
        for name, email in ADMIN_STAFF:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "full_name": name,
                    "is_admin": True,
                    "is_staff": True,
                    "is_student": False,
                },
            )
            if created:
                user.set_password("staff123")
                user.save()
            staff_users.append(user)
        self.stdout.write(self.style.SUCCESS(f"  [2/14] {len(staff_users)} staff members created"))
        return staff_users

    # ─── 2. Levels ────────────────────────────────────────────────────────

    def _create_levels(self):
        levels = []
        for ld in LEVELS:
            level, _ = Level.objects.get_or_create(order=ld["order"], defaults=ld)
            levels.append(level)
        self.stdout.write(self.style.SUCCESS(f"  [3/14] {len(levels)} levels created"))
        return levels

    # ─── 3. Curriculum ────────────────────────────────────────────────────

    def _create_curriculum(self, levels):
        courses = []
        all_weeks = []
        all_sessions = []

        for level in levels:
            course_defs = COURSES_PER_LEVEL[level.order]
            for title, description in course_defs:
                course, _ = Course.objects.get_or_create(
                    level=level,
                    title=title,
                    defaults={"description": description},
                )
                courses.append(course)

                week_names = WEEKS_PER_COURSE.get(title, [])
                for w_order, w_name in enumerate(week_names, start=1):
                    week, _ = Week.objects.get_or_create(
                        course=course,
                        order=w_order,
                        defaults={"name": w_name},
                    )
                    all_weeks.append(week)

                    s_order = 0
                    # Video sessions (concept + solved examples)
                    for tmpl in VIDEO_SESSION_TEMPLATES:
                        s_order += 1
                        session, created = Session.objects.get_or_create(
                            week=week,
                            order=s_order,
                            defaults={
                                "title": tmpl.format(topic=w_name),
                                "description": f"Video lecture covering {w_name}.",
                                "video_url": f"https://cdn.example.com/videos/{level.order}/{course.pk}/{week.pk}/{s_order}.mp4",
                                "duration_seconds": random.randint(1200, 3600),
                                "session_type": Session.SessionType.VIDEO,
                            },
                        )
                        all_sessions.append(session)

                    # Resource session
                    s_order += 1
                    tmpl = RESOURCE_SESSION_TEMPLATES[0]
                    session, created = Session.objects.get_or_create(
                        week=week,
                        order=s_order,
                        defaults={
                            "title": tmpl.format(topic=w_name),
                            "description": f"Downloadable formula sheet for {w_name}.",
                            "session_type": Session.SessionType.RESOURCE,
                            "duration_seconds": 0,
                            "file_url": f"https://cdn.example.com/resources/{level.order}/{course.pk}/{week.pk}/formula-sheet.pdf",
                            "resource_type": Session.ResourceType.PDF,
                        },
                    )
                    all_sessions.append(session)

                    # Practice exam session (last session in week)
                    s_order += 1
                    session, _ = Session.objects.get_or_create(
                        week=week,
                        order=s_order,
                        defaults={
                            "title": f"Practice Quiz — {w_name}",
                            "description": f"Unlimited practice quiz on {w_name}.",
                            "session_type": Session.SessionType.PRACTICE_EXAM,
                            "duration_seconds": 0,
                        },
                    )
                    all_sessions.append(session)

        self.stdout.write(
            self.style.SUCCESS(
                f"  [4/14] {len(courses)} courses, {len(all_weeks)} weeks, {len(all_sessions)} sessions created"
            )
        )
        return courses, all_weeks, all_sessions

    # ─── 4. Questions & Exams ─────────────────────────────────────────────

    def _create_questions_and_exams(self, levels, courses, all_weeks):
        q_count = 0
        exam_count = 0

        # Create exams first, then assign questions to them
        level_final_exams = {}
        for level in levels:
            exam, created = Exam.objects.get_or_create(
                level=level,
                exam_type=Exam.ExamType.LEVEL_FINAL,
                defaults={
                    "title": f"{level.name} Level — Final Examination",
                    "duration_minutes": 90,
                    "total_marks": 80,
                    "passing_percentage": level.passing_percentage,
                    "num_questions": 20,
                    "is_proctored": True,
                    "max_warnings": 3,
                },
            )
            level_final_exams[level.pk] = exam
            if created:
                exam_count += 1

        weekly_exams = {}
        for course in courses:
            weeks = Week.objects.filter(course=course).order_by("order")
            for week in weeks:
                exam, created = Exam.objects.get_or_create(
                    level=course.level,
                    week=week,
                    course=course,
                    exam_type=Exam.ExamType.WEEKLY,
                    defaults={
                        "title": f"{week.name} — Weekly Quiz",
                        "duration_minutes": 20,
                        "total_marks": 20,
                        "passing_percentage": Decimal("40.00"),
                        "num_questions": 5,
                    },
                )
                weekly_exams[(course.pk, week.pk)] = exam
                if created:
                    exam_count += 1

        # Now create questions assigned to their respective exams
        for course in courses:
            level_exam = level_final_exams[course.level_id]
            course_questions = QUESTION_BANK.get(course.title, [])
            for q_data in course_questions:
                text, difficulty, options_data, explanation = q_data
                q, created = Question.objects.get_or_create(
                    exam=level_exam,
                    level=course.level,
                    text=text,
                    defaults={
                        "difficulty": difficulty,
                        "marks": 4,
                        "negative_marks": Decimal("1.00") if difficulty != "easy" else Decimal("0"),
                        "explanation": explanation,
                        "question_type": Question.QuestionType.MCQ,
                    },
                )
                if created:
                    q_count += 1
                    for opt_text, is_correct in options_data:
                        Option.objects.create(question=q, text=opt_text, is_correct=is_correct)

            # Add multi-select and fill-in-the-blank questions to the level final exam
            multi_q, created = Question.objects.get_or_create(
                exam=level_exam,
                level=course.level,
                text=f"Select ALL correct statements about {course.title.lower()}:",
                defaults={
                    "difficulty": "hard",
                    "marks": 4,
                    "negative_marks": Decimal("2.00"),
                    "question_type": Question.QuestionType.MULTI_MCQ,
                    "explanation": "Multiple correct answers possible — partial marking may apply.",
                },
            )
            if created:
                q_count += 1
                Option.objects.create(question=multi_q, text="Statement A is correct", is_correct=True)
                Option.objects.create(question=multi_q, text="Statement B is incorrect", is_correct=False)
                Option.objects.create(question=multi_q, text="Statement C is correct", is_correct=True)
                Option.objects.create(question=multi_q, text="Statement D is incorrect", is_correct=False)

            fill_q, created = Question.objects.get_or_create(
                exam=level_exam,
                level=course.level,
                text=f"The SI unit commonly associated with a key quantity in {course.title.lower()} is ___.",
                defaults={
                    "difficulty": "medium",
                    "marks": 2,
                    "question_type": Question.QuestionType.FILL_BLANK,
                    "correct_text_answer": "unit",
                    "explanation": "Fill in the standard SI unit for the quantity.",
                },
            )
            if created:
                q_count += 1

            # Also add a few questions to weekly exams for this course
            weeks = Week.objects.filter(course=course).order_by("order")
            for week in weeks:
                weekly_exam = weekly_exams.get((course.pk, week.pk))
                if weekly_exam:
                    for i in range(min(5, len(course_questions))):
                        text, difficulty, options_data, explanation = course_questions[i]
                        wq, wcreated = Question.objects.get_or_create(
                            exam=weekly_exam,
                            level=course.level,
                            text=f"[Weekly] {text}",
                            defaults={
                                "difficulty": difficulty,
                                "marks": 4,
                                "negative_marks": Decimal("1.00") if difficulty != "easy" else Decimal("0"),
                                "explanation": explanation,
                                "question_type": Question.QuestionType.MCQ,
                            },
                        )
                        if wcreated:
                            q_count += 1
                            for opt_text, is_correct in options_data:
                                Option.objects.create(question=wq, text=opt_text, is_correct=is_correct)

        # Update level final exam total_marks based on actual question count
        for level in levels:
            exam = level_final_exams[level.pk]
            actual_count = exam.questions.filter(is_active=True).count()
            num_q = min(actual_count, 20)
            if num_q != exam.num_questions or num_q * 4 != exam.total_marks:
                exam.num_questions = num_q
                exam.total_marks = num_q * 4
                exam.save(update_fields=["num_questions", "total_marks"])

        self.stdout.write(self.style.SUCCESS(f"  [5/14] {q_count} questions, {exam_count} exams created"))

    # ─── 5. Students ──────────────────────────────────────────────────────

    def _create_students(self, levels):
        students = []
        for idx, (name, email, phone) in enumerate(STUDENT_NAMES):
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "full_name": name,
                    "phone": phone,
                    "is_student": True,
                },
            )
            if created:
                user.set_password("student123")
                user.save()
            profile, _ = StudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    "is_onboarding_completed": idx < 25,  # Most students completed onboarding
                    "is_onboarding_exam_attempted": idx < 25,
                },
            )
            UserPreference.objects.get_or_create(user=user)
            students.append((user, profile))
        self.stdout.write(self.style.SUCCESS(f"  [6/14] {len(students)} students created"))
        return students

    # ─── 6. Purchases ─────────────────────────────────────────────────────

    def _create_purchases(self, students, levels, now):
        purchase_count = 0
        txn_count = 0

        for idx, (_user, profile) in enumerate(students):
            # First 20 students bought level 1
            if idx < 20:
                p, created = self._create_single_purchase(profile, levels[0], now, days_ago=random.randint(30, 150))
                if created:
                    purchase_count += 1
                    txn_count += 1

            # First 12 also bought level 2
            if idx < 12:
                p, created = self._create_single_purchase(profile, levels[1], now, days_ago=random.randint(10, 60))
                if created:
                    purchase_count += 1
                    txn_count += 1

            # First 5 bought level 3
            if idx < 5:
                p, created = self._create_single_purchase(profile, levels[2], now, days_ago=random.randint(5, 30))
                if created:
                    purchase_count += 1
                    txn_count += 1

            # Top 2 students bought level 4
            if idx < 2:
                p, created = self._create_single_purchase(profile, levels[3], now, days_ago=random.randint(1, 10))
                if created:
                    purchase_count += 1
                    txn_count += 1

        # Add a few expired purchases
        for idx in range(20, 25):
            user, profile = students[idx]
            p, created = self._create_single_purchase(
                profile,
                levels[0],
                now,
                days_ago=200,
                expired=True,
            )
            if created:
                purchase_count += 1
                txn_count += 1

        self.stdout.write(self.style.SUCCESS(f"  [7/14] {purchase_count} purchases, {txn_count} transactions created"))

    def _create_single_purchase(self, profile, level, now, days_ago=30, expired=False):
        purchased_at = now - timedelta(days=days_ago)
        if expired:
            expires_at = purchased_at + timedelta(days=level.validity_days)
            status = Purchase.Status.EXPIRED if expires_at < now else Purchase.Status.ACTIVE
        else:
            expires_at = purchased_at + timedelta(days=level.validity_days)
            status = Purchase.Status.ACTIVE

        purchase, created = Purchase.objects.get_or_create(
            student=profile,
            level=level,
            defaults={
                "amount_paid": level.price,
                "expires_at": expires_at,
                "status": status,
            },
        )
        if created:
            PaymentTransaction.objects.create(
                purchase=purchase,
                student=profile,
                level=level,
                razorpay_order_id=f"order_{profile.pk}_{level.pk}_{random.randint(10000, 99999)}",
                razorpay_payment_id=f"pay_{random.randint(100000, 999999)}",
                amount=level.price,
                status=PaymentTransaction.Status.SUCCESS,
            )
            # Backdate purchased_at
            Purchase.objects.filter(pk=purchase.pk).update(purchased_at=purchased_at)
        return purchase, created

    # ─── 7. Progress ──────────────────────────────────────────────────────

    def _create_progress(self, students, levels, courses, all_sessions, now):
        sp_count = 0
        cp_count = 0
        lp_count = 0

        for idx, (_user, profile) in enumerate(students):
            if idx >= 20:
                continue  # Only students with purchases get progress

            # Level 1 progress — most students have significant progress
            level1_courses = [c for c in courses if c.level == levels[0]]
            l1_sessions = [s for s in all_sessions if s.week.course.level == levels[0]]

            if idx < 15:
                # Completed all of level 1
                for session in l1_sessions:
                    if session.session_type == Session.SessionType.VIDEO:
                        _, created = SessionProgress.objects.get_or_create(
                            student=profile,
                            session=session,
                            defaults={
                                "watched_seconds": session.duration_seconds,
                                "is_completed": True,
                                "completed_at": now - timedelta(days=random.randint(20, 100)),
                            },
                        )
                        if created:
                            sp_count += 1
                    elif session.session_type == Session.SessionType.RESOURCE:
                        _, created = SessionProgress.objects.get_or_create(
                            student=profile,
                            session=session,
                            defaults={
                                "is_completed": True,
                                "completed_at": now - timedelta(days=random.randint(20, 100)),
                            },
                        )
                        if created:
                            sp_count += 1
                    elif session.session_type == Session.SessionType.PRACTICE_EXAM:
                        _, created = SessionProgress.objects.get_or_create(
                            student=profile,
                            session=session,
                            defaults={
                                "is_completed": True,
                                "is_exam_passed": True,
                                "completed_at": now - timedelta(days=random.randint(20, 100)),
                            },
                        )
                        if created:
                            sp_count += 1

                for course in level1_courses:
                    _, created = CourseProgress.objects.get_or_create(
                        student=profile,
                        course=course,
                        defaults={
                            "status": CourseProgress.Status.COMPLETED,
                            "started_at": now - timedelta(days=random.randint(80, 140)),
                            "completed_at": now - timedelta(days=random.randint(20, 60)),
                        },
                    )
                    if created:
                        cp_count += 1

                _, created = LevelProgress.objects.get_or_create(
                    student=profile,
                    level=levels[0],
                    defaults={
                        "status": LevelProgress.Status.EXAM_PASSED,
                        "started_at": now - timedelta(days=random.randint(100, 150)),
                        "completed_at": now - timedelta(days=random.randint(15, 50)),
                    },
                )
                if created:
                    lp_count += 1
                    profile.highest_cleared_level = levels[0]
                    profile.current_level = levels[1]
                    profile.save()

            elif idx < 20:
                # Partial progress on level 1
                partial_count = random.randint(len(l1_sessions) // 4, len(l1_sessions) // 2)
                for session in l1_sessions[:partial_count]:
                    if session.session_type == Session.SessionType.VIDEO:
                        watched = random.randint(session.duration_seconds // 3, session.duration_seconds)
                        is_done = watched >= int(session.duration_seconds * 0.9)
                        _, created = SessionProgress.objects.get_or_create(
                            student=profile,
                            session=session,
                            defaults={
                                "watched_seconds": watched,
                                "is_completed": is_done,
                                "completed_at": now - timedelta(days=random.randint(5, 40)) if is_done else None,
                            },
                        )
                        if created:
                            sp_count += 1

                for course in level1_courses:
                    _, created = CourseProgress.objects.get_or_create(
                        student=profile,
                        course=course,
                        defaults={
                            "status": CourseProgress.Status.IN_PROGRESS,
                            "started_at": now - timedelta(days=random.randint(30, 80)),
                        },
                    )
                    if created:
                        cp_count += 1

                _, created = LevelProgress.objects.get_or_create(
                    student=profile,
                    level=levels[0],
                    defaults={
                        "status": LevelProgress.Status.IN_PROGRESS,
                        "started_at": now - timedelta(days=random.randint(30, 80)),
                    },
                )
                if created:
                    lp_count += 1
                    profile.current_level = levels[0]
                    profile.save()

            # Level 2 progress for students who cleared level 1
            if idx < 10:
                level2_courses = [c for c in courses if c.level == levels[1]]
                l2_sessions = [s for s in all_sessions if s.week.course.level == levels[1]]
                partial = random.randint(len(l2_sessions) // 4, len(l2_sessions) * 3 // 4)
                for session in l2_sessions[:partial]:
                    if session.session_type == Session.SessionType.VIDEO:
                        _, created = SessionProgress.objects.get_or_create(
                            student=profile,
                            session=session,
                            defaults={
                                "watched_seconds": session.duration_seconds,
                                "is_completed": True,
                                "completed_at": now - timedelta(days=random.randint(5, 30)),
                            },
                        )
                        if created:
                            sp_count += 1

                for course in level2_courses:
                    _, created = CourseProgress.objects.get_or_create(
                        student=profile,
                        course=course,
                        defaults={
                            "status": CourseProgress.Status.IN_PROGRESS,
                            "started_at": now - timedelta(days=random.randint(10, 50)),
                        },
                    )
                    if created:
                        cp_count += 1

                _, created = LevelProgress.objects.get_or_create(
                    student=profile,
                    level=levels[1],
                    defaults={
                        "status": LevelProgress.Status.IN_PROGRESS,
                        "started_at": now - timedelta(days=random.randint(10, 50)),
                    },
                )
                if created:
                    lp_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"  [8/14] {sp_count} session progress, {cp_count} course progress, {lp_count} level progress records"
            )
        )

    # ─── 8. Exam Attempts ─────────────────────────────────────────────────

    def _create_exam_attempts(self, students, levels, now):
        attempt_count = 0
        exams = {e.level_id: e for e in Exam.objects.filter(exam_type=Exam.ExamType.LEVEL_FINAL)}

        for idx, (_user, profile) in enumerate(students):
            if idx >= 15:
                continue

            # Level 1 final exam — passed
            exam = exams.get(levels[0].pk)
            if exam:
                score = Decimal(str(random.randint(int(exam.total_marks * 0.6), exam.total_marks)))
                _, created = ExamAttempt.objects.get_or_create(
                    student=profile,
                    exam=exam,
                    status=ExamAttempt.Status.SUBMITTED,
                    defaults={
                        "score": score,
                        "total_marks": exam.total_marks,
                        "is_passed": True,
                        "submitted_at": now - timedelta(days=random.randint(15, 50)),
                    },
                )
                if created:
                    attempt_count += 1

            # Some students attempted level 2 exam
            if idx < 5:
                exam2 = exams.get(levels[1].pk)
                if exam2:
                    passed = idx < 3
                    score = Decimal(
                        str(
                            random.randint(
                                int(exam2.total_marks * 0.6) if passed else int(exam2.total_marks * 0.2),
                                exam2.total_marks if passed else int(exam2.total_marks * 0.5),
                            )
                        )
                    )
                    _, created = ExamAttempt.objects.get_or_create(
                        student=profile,
                        exam=exam2,
                        status=ExamAttempt.Status.SUBMITTED,
                        defaults={
                            "score": score,
                            "total_marks": exam2.total_marks,
                            "is_passed": passed,
                            "submitted_at": now - timedelta(days=random.randint(3, 15)),
                        },
                    )
                    if created:
                        attempt_count += 1

        # A couple of failed + retried attempts
        for idx in [15, 16, 17]:
            if idx >= len(students):
                break
            user, profile = students[idx]
            exam = exams.get(levels[0].pk)
            if (
                exam
                and Purchase.objects.filter(student=profile, level=levels[0], status=Purchase.Status.ACTIVE).exists()
            ):
                score = Decimal(str(random.randint(0, int(exam.total_marks * 0.4))))
                _, created = ExamAttempt.objects.get_or_create(
                    student=profile,
                    exam=exam,
                    status=ExamAttempt.Status.SUBMITTED,
                    defaults={
                        "score": score,
                        "total_marks": exam.total_marks,
                        "is_passed": False,
                        "submitted_at": now - timedelta(days=random.randint(10, 30)),
                    },
                )
                if created:
                    attempt_count += 1

        self.stdout.write(self.style.SUCCESS(f"  [9/14] {attempt_count} exam attempts created"))

    # ─── 9. Doubts ────────────────────────────────────────────────────────

    def _create_doubts(self, students, staff_users, all_sessions, now):
        doubt_count = 0
        reply_count = 0

        for _idx, (user, profile) in enumerate(students[:15]):
            num_doubts = random.randint(1, 4)
            for _d in range(num_doubts):
                title = random.choice(DOUBT_TITLES)
                context_type = random.choice(
                    [
                        DoubtTicket.ContextType.TOPIC,
                        DoubtTicket.ContextType.SESSION,
                    ]
                )
                session = None
                if context_type == DoubtTicket.ContextType.SESSION and all_sessions:
                    session = random.choice(all_sessions)

                status = random.choice(
                    [
                        DoubtTicket.Status.OPEN,
                        DoubtTicket.Status.IN_REVIEW,
                        DoubtTicket.Status.ANSWERED,
                        DoubtTicket.Status.CLOSED,
                    ]
                )

                ticket = DoubtTicket.objects.create(
                    student=profile,
                    title=title,
                    description="I need help understanding this concept. Specifically, I'm struggling with the application of this in problem-solving scenarios. Could you please explain step by step?",
                    context_type=context_type,
                    session=session,
                    status=status,
                    assigned_to=random.choice(staff_users) if status != DoubtTicket.Status.OPEN else None,
                )
                DoubtTicket.objects.filter(pk=ticket.pk).update(
                    created_at=now - timedelta(days=random.randint(1, 60)),
                )
                doubt_count += 1

                # Add replies for non-open tickets
                if status in (DoubtTicket.Status.IN_REVIEW, DoubtTicket.Status.ANSWERED, DoubtTicket.Status.CLOSED):
                    DoubtReply.objects.create(
                        ticket=ticket,
                        author=random.choice(staff_users),
                        message="Thank you for your question. Let me walk you through this step by step. The key concept here is to understand the underlying principle before applying the formula. Please review the solved examples in the video lecture and try the practice problems. Let me know if you need further clarification.",
                    )
                    reply_count += 1

                    # Student follow-up on some
                    if random.random() > 0.5:
                        DoubtReply.objects.create(
                            ticket=ticket,
                            author=user,
                            message="Thank you for the explanation! I understand the concept better now. Just one more question — does this approach also work for the harder variants of this problem type?",
                        )
                        reply_count += 1

        self.stdout.write(self.style.SUCCESS(f"  [10/14] {doubt_count} doubts, {reply_count} replies created"))

    # ─── 10. Feedback ─────────────────────────────────────────────────────

    def _create_feedback(self, students, all_sessions):
        fb_count = 0
        video_sessions = [s for s in all_sessions if s.session_type == Session.SessionType.VIDEO]
        comments = [
            "Excellent explanation! Very clear and concise.",
            "Good lecture but could use more examples.",
            "The pace was a bit fast for beginners.",
            "Loved the visual demonstrations.",
            "Needs more practice problems at the end.",
            "Great session! The solved examples really helped.",
            "",  # Some students don't leave comments
            "",
            "Very thorough coverage of the topic.",
            "Would appreciate more real-world applications.",
        ]

        for _idx, (_user, profile) in enumerate(students[:15]):
            # Each active student gives feedback on some completed sessions
            sessions_to_review = random.sample(
                video_sessions,
                min(random.randint(3, 8), len(video_sessions)),
            )
            for session in sessions_to_review:
                if SessionProgress.objects.filter(student=profile, session=session, is_completed=True).exists():
                    _, created = SessionFeedback.objects.get_or_create(
                        student=profile,
                        session=session,
                        defaults={
                            "overall_rating": random.randint(3, 5),
                            "difficulty_rating": random.randint(2, 5),
                            "clarity_rating": random.randint(3, 5),
                            "comment": random.choice(comments),
                        },
                    )
                    if created:
                        fb_count += 1

        self.stdout.write(self.style.SUCCESS(f"  [11/14] {fb_count} feedback records created"))

    # ─── 11. Notifications ────────────────────────────────────────────────

    def _create_notifications(self, students, levels, now):
        notif_count = 0
        notif_templates = [
            (
                Notification.NotificationType.PURCHASE,
                "Purchase Confirmed",
                "Your purchase for {level} has been confirmed. You now have access to all courses in this level.",
            ),
            (
                Notification.NotificationType.EXAM_RESULT,
                "Exam Result Available",
                "Your result for {level} Final Exam is now available. Check your dashboard for details.",
            ),
            (
                Notification.NotificationType.LEVEL_UNLOCK,
                "New Level Unlocked!",
                "Congratulations! You've cleared {level} and unlocked the next level.",
            ),
            (
                Notification.NotificationType.GENERAL,
                "Weekly Study Reminder",
                "Don't forget to complete your pending sessions for this week. Consistency is key!",
            ),
            (
                Notification.NotificationType.GENERAL,
                "New Content Available",
                "Fresh practice problems and video lectures have been added to {level}.",
            ),
        ]

        for idx, (user, _profile) in enumerate(students[:20]):
            num_notifs = random.randint(2, 5)
            for _n in range(num_notifs):
                ntype, title, message = random.choice(notif_templates)
                level_name = levels[min(idx // 5, 3)].name
                Notification.objects.create(
                    user=user,
                    title=title,
                    message=message.format(level=level_name),
                    notification_type=ntype,
                    is_read=random.random() > 0.4,
                )
                notif_count += 1

        self.stdout.write(self.style.SUCCESS(f"  [12/14] {notif_count} notifications created"))

    # ─── 12. Banners ──────────────────────────────────────────────────────

    def _create_banners(self):
        for order, (title, subtitle, image_url) in enumerate(BANNER_DATA, start=1):
            Banner.objects.get_or_create(
                title=title,
                defaults={
                    "subtitle": subtitle,
                    "image_url": image_url,
                    "order": order,
                    "is_active": True,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"  [13/14] {len(BANNER_DATA)} banners created"))

    # ─── 13. Analytics ────────────────────────────────────────────────────

    def _create_analytics(self, levels, now):
        rev_count = 0
        la_count = 0

        # 30 days of revenue data
        for days_ago in range(1, 31):
            date = (now - timedelta(days=days_ago)).date()
            _, created = DailyRevenue.objects.get_or_create(
                date=date,
                defaults={
                    "total_revenue": Decimal(str(random.randint(5000, 50000))),
                    "total_transactions": random.randint(2, 20),
                },
            )
            if created:
                rev_count += 1

        # Level analytics for 30 days
        for level in levels:
            for days_ago in range(1, 31):
                date = (now - timedelta(days=days_ago)).date()
                attempts = random.randint(5, 40)
                passes = random.randint(0, attempts)
                _, created = LevelAnalytics.objects.get_or_create(
                    level=level,
                    date=date,
                    defaults={
                        "total_attempts": attempts,
                        "total_passes": passes,
                        "total_failures": attempts - passes,
                        "total_purchases": random.randint(0, 5),
                        "revenue": Decimal(str(random.randint(0, 15000))),
                    },
                )
                if created:
                    la_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"  [14/14] {rev_count} daily revenue, {la_count} level analytics records created")
        )
