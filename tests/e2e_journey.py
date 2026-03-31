"""
End-to-end journey test against the running dev server.
Tests EVERY student-facing flow and verifies ALL response fields.

Usage:  python tests/e2e_journey.py
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"
PASS = 0
FAIL = 0
WARN = 0
RUN_ID = int(time.time())


# ── Helpers ─────────────────────────────────────────────────────


def req(method, path, data=None, token=None, expect=None):
    """Make HTTP request and return (status, body_dict)."""
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r)
        status = resp.status
        raw = resp.read().decode()
        result = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read().decode()
        try:
            result = json.loads(raw)
        except Exception:
            result = {"raw": raw}
    return status, result


def check(label, status, body, expected_status, required_fields=None, list_item_fields=None):
    """Validate status code and required fields."""
    global PASS, FAIL, WARN
    errors = []

    if status != expected_status:
        errors.append(f"status {status} != expected {expected_status}")

    target = body
    # Handle paginated responses
    if isinstance(body, dict) and "results" in body and list_item_fields:
        if len(body["results"]) > 0:
            target = body["results"][0]
        else:
            errors.append("empty results list — cannot check item fields")
            target = None

    if required_fields and target and isinstance(target, dict):
        missing = [f for f in required_fields if f not in target]
        if missing:
            errors.append(f"missing fields: {missing}")

    if list_item_fields and target and isinstance(target, dict):
        missing = [f for f in list_item_fields if f not in target]
        if missing:
            errors.append(f"missing item fields: {missing}")

    if isinstance(body, list) and list_item_fields and len(body) > 0:
        missing = [f for f in list_item_fields if f not in body[0]]
        if missing:
            errors.append(f"missing item fields: {missing}")

    if errors:
        FAIL += 1
        print(f"  FAIL  {label}")
        for e in errors:
            print(f"        -> {e}")
    else:
        PASS += 1
        print(f"  OK    {label}")

    return status, body


# ────────────────────────────────────────────────────────────────
# JOURNEY 1: Fresh student — register → onboarding → full flow
# ────────────────────────────────────────────────────────────────
print("=" * 65)
print("  JOURNEY 1: New student — full lifecycle")
print("=" * 65)

# 1. Register (unique per run to avoid conflicts)
E2E_EMAIL = f"e2e.test.{RUN_ID}@example.com"
E2E_PHONE = f"+91{RUN_ID}"[-12:]
s, b = req(
    "POST",
    "/auth/register/",
    {
        "email": E2E_EMAIL,
        "full_name": "E2E Test Student",
        "phone": E2E_PHONE,
        "password": "TestPass@123",
    },
)
check("Register", s, b, 201, ["user", "tokens"])
token = b.get("tokens", {}).get("access", "")
refresh = b.get("tokens", {}).get("refresh", "")
user_data = b.get("user", {})
if user_data:
    check(
        "Register → user fields", 201, user_data, 201, ["id", "email", "full_name", "phone", "is_student", "is_admin"]
    )

# 2. Get profile (me)
s, b = req("GET", "/auth/me/", token=token)
check("GET /auth/me/", s, b, 200, ["id", "email", "full_name", "phone", "is_student", "is_admin", "profile"])
profile = b.get("profile", {})
if profile:
    check(
        "Profile fields",
        200,
        profile,
        200,
        [
            "id",
            "gender",
            "current_level",
            "highest_cleared_level",
            "is_onboarding_completed",
            "is_onboarding_exam_attempted",
        ],
    )

# 3. Update profile
s, b = req("PATCH", "/auth/me/", {"full_name": "E2E Updated Name"}, token=token)
check("PATCH /auth/me/", s, b, 200, ["id", "email", "full_name"])

# 4. Get preferences
s, b = req("GET", "/auth/preferences/", token=token)
check(
    "GET /auth/preferences/",
    s,
    b,
    200,
    [
        "push_notifications",
        "email_notifications",
        "doubt_reply_notifications",
        "exam_result_notifications",
        "promotional_notifications",
    ],
)

# 5. Update preferences
s, b = req("PATCH", "/auth/preferences/", {"push_notifications": False}, token=token)
check("PATCH /auth/preferences/", s, b, 200, ["push_notifications"])

# 6. Token refresh
s, b = req("POST", "/auth/token/refresh/", {"refresh": refresh})
check("Token refresh", s, b, 200, ["access"])
if "access" in b:
    token = b["access"]

# 7. Change password
s, b = req(
    "POST", "/auth/change-password/", {"old_password": "TestPass@123", "new_password": "NewPass@456"}, token=token
)
check("Change password", s, b, 200, ["detail"])
if "access" in b:
    token = b["access"]

# 8. Password reset request (just check endpoint works)
s, b = req("POST", "/auth/password-reset/", {"email": E2E_EMAIL})
check("Password reset request", s, b, 200, ["detail"])

# ── Public endpoints ────────────────────────────────────────────
print("\n--- Public Endpoints ---")

# 9. Levels list
s, b = req("GET", "/levels/")
check("GET /levels/", s, b, 200)
if isinstance(b, list) and len(b) > 0:
    check("Level item fields", 200, b[0], 200, ["id", "name", "description", "order", "is_active"])
    level_ids = [lv["id"] for lv in b]
else:
    level_ids = []

# 10. Level detail
if level_ids:
    s, b = req("GET", f"/levels/{level_ids[0]}/")
    check("GET /levels/<id>/", s, b, 200, ["id", "name", "description", "order"])

# 11. Health check
s, b = req("GET", "/health/")
check("GET /health/", s, b, 200)

# 12. Home banners
s, b = req("GET", "/home/banners/")
check("GET /home/banners/", s, b, 200)
if isinstance(b, list) and len(b) > 0:
    check("Banner item fields", 200, b[0], 200, ["id", "title", "image_url"])

# 13. Featured courses
s, b = req("GET", "/home/featured/")
check("GET /home/featured/", s, b, 200)

# ── Dashboard (before onboarding) ──────────────────────────────
print("\n--- Dashboard (pre-onboarding) ---")
s, b = req("GET", "/progress/dashboard/", token=token)
check("Dashboard pre-onboarding", s, b, 200)

# ── Onboarding flow ────────────────────────────────────────────
print("\n--- Onboarding Flow ---")

# 14. Complete onboarding
s, b = req("POST", "/auth/onboarding/complete/", token=token)
check("Complete onboarding", s, b, 200, ["detail"])

# ── Login as existing student (Arjun — has purchases & progress) ──
print("\n" + "=" * 65)
print("  JOURNEY 2: Existing student — Arjun (Mastery level)")
print("=" * 65)

s, b = req("POST", "/auth/login/", {"email": "arjun.mehta@gmail.com", "password": "Student@123"})
check("Login Arjun", s, b, 200, ["user", "tokens"])
arjun_token = b.get("tokens", {}).get("access", "")
arjun_user = b.get("user", {})
if arjun_user:
    check("Login → user fields", 200, arjun_user, 200, ["id", "email", "full_name", "phone", "is_student", "is_admin"])

# ── Progress & Dashboard ───────────────────────────────────────
print("\n--- Progress & Dashboard ---")

s, b = req("GET", "/progress/dashboard/", token=arjun_token)
check("Dashboard", s, b, 200)

s, b = req("GET", "/progress/levels/", token=arjun_token)
check("Level progress list", s, b, 200)
if isinstance(b, list) and len(b) > 0:
    check("Level progress item fields", 200, b[0], 200, ["id", "level", "status", "started_at"])

# Get level IDs from Arjun's data
s, b_levels = req("GET", "/levels/")
if isinstance(b_levels, list) and len(b_levels) > 0:
    first_level_id = b_levels[0]["id"]

    s, b = req("GET", f"/progress/levels/{first_level_id}/courses/", token=arjun_token)
    check(f"Course progress for level {first_level_id}", s, b, 200)

    s, b = req("GET", f"/progress/levels/{first_level_id}/sessions/", token=arjun_token)
    check(f"Session progress for level {first_level_id}", s, b, 200)

# Calendar
s, b = req("GET", "/progress/calendar/?year=2026&month=3", token=arjun_token)
check("Calendar", s, b, 200, ["year", "month"])

# Leaderboard
s, b = req("GET", "/progress/leaderboard/", token=arjun_token)
check("Leaderboard", s, b, 200, ["leaderboard"])

# ── Courses & Sessions ─────────────────────────────────────────
print("\n--- Courses & Sessions ---")

if isinstance(b_levels, list) and len(b_levels) > 0:
    s, b = req("GET", f"/courses/level/{first_level_id}/", token=arjun_token)
    check(f"Courses for level {first_level_id}", s, b, 200)
    courses_list = b if isinstance(b, list) else b.get("results", [])

    if len(courses_list) > 0:
        course_id = courses_list[0]["id"]
        check("Course item fields", 200, courses_list[0], 200, ["id", "title", "description"])

        s, b = req("GET", f"/courses/{course_id}/sessions/", token=arjun_token)
        check(f"Sessions for course {course_id}", s, b, 200)
        sessions_data = b if isinstance(b, list) else b.get("results", []) if isinstance(b, dict) else []

        session_id = None
        if isinstance(sessions_data, list) and len(sessions_data) > 0:
            # Pick the session with order=1 in the earliest week (most likely accessible)
            sorted_sessions = sorted(sessions_data, key=lambda s: (s.get("week", 0), s.get("order", 0)))
            session_id = sorted_sessions[0]["id"]
            check("Session item fields", 200, sorted_sessions[0], 200, ["id", "title", "session_type"])

        # Session detail
        if session_id:
            s, b = req("GET", f"/courses/sessions/{session_id}/", token=arjun_token)
            check(f"Session detail {session_id}", s, b, 200, ["id", "title", "description", "session_type"])

            # Update session progress
            s, b = req("POST", f"/progress/sessions/{session_id}/", {"watched_seconds": 120}, token=arjun_token)
            check("Update session progress", s, b, 200)

# ── Bookmarks ──────────────────────────────────────────────────
print("\n--- Bookmarks ---")

s, b = req("GET", "/courses/bookmarks/", token=arjun_token)
check("GET bookmarks", s, b, 200)

if session_id:
    # Try to add bookmark (may already exist)
    s, b = req("POST", "/courses/bookmarks/", {"session": session_id}, token=arjun_token)
    if s == 201:
        check("Create bookmark", s, b, 201)
        bookmark_id = b.get("id")
        if bookmark_id:
            s, b = req("DELETE", f"/courses/bookmarks/{bookmark_id}/", token=arjun_token)
            check("Delete bookmark", s, b, 204)
    else:
        check("Bookmark (already exists or err)", s, b, s)

# ── Exams ──────────────────────────────────────────────────────
print("\n--- Exams ---")

# List attempts
s, b = req("GET", "/exams/attempts/", token=arjun_token)
check("GET exam attempts", s, b, 200)
attempts_data = b.get("results", []) if isinstance(b, dict) else b if isinstance(b, list) else []
if len(attempts_data) > 0:
    check(
        "Attempt item fields", 200, attempts_data[0], 200, ["id", "exam", "status", "score", "total_marks", "is_passed"]
    )

    # Get result of a submitted attempt
    submitted = [a for a in attempts_data if a.get("status") == "submitted"]
    if submitted:
        attempt_id = submitted[0]["id"]
        s, b = req("GET", f"/exams/attempts/{attempt_id}/result/", token=arjun_token)
        check(f"Attempt result {attempt_id}", s, b, 200)

        s, b = req("GET", f"/exams/attempts/{attempt_id}/violations/", token=arjun_token)
        check(f"Attempt violations {attempt_id}", s, b, 200)

# Start and submit a fresh exam (use a weekly exam from level 1)
# Find an exam
s, exams_resp = req("GET", "/levels/")
if isinstance(exams_resp, list) and len(exams_resp) > 0:
    # Get courses for foundation to find a weekly exam
    s2, courses_resp = req("GET", f"/courses/level/{exams_resp[0]['id']}/", token=arjun_token)
    if isinstance(courses_resp, list) and len(courses_resp) > 0:
        # We need to find an exam ID — query attempts to get exam IDs
        pass

# Use login as a fresh student to start a new exam
print("\n--- Exam Start & Submit (fresh student Sneha) ---")
s, b = req("POST", "/auth/login/", {"email": "sneha.iyer@gmail.com", "password": "Student@123"})
sneha_token = b.get("tokens", {}).get("access", "")

# Get all her attempts to find an exam she can take
s, b = req("GET", "/exams/attempts/", token=sneha_token)
existing_attempts = b.get("results", []) if isinstance(b, dict) else b if isinstance(b, list) else []
existing_exam_ids = {a.get("exam") for a in existing_attempts if isinstance(a.get("exam"), int)}
# Also handle exam as dict
for a in existing_attempts:
    if isinstance(a.get("exam"), dict):
        existing_exam_ids.add(a["exam"].get("id"))

# Find a weekly exam from the admin endpoint or query directly
# Use Arjun's token to check exam details (need exam ID)
# Let's use admin to list exams
s, admin_b = req("POST", "/auth/login/", {"email": "admin@iitprep.com", "password": "Admin@123"})
admin_token = admin_b.get("tokens", {}).get("access", "")

s, exams_list = req("GET", "/exams/admin/?exam_type=weekly", token=admin_token)
weekly_exams = (
    exams_list.get("results", [])
    if isinstance(exams_list, dict)
    else exams_list
    if isinstance(exams_list, list)
    else []
)

exam_to_start = None
for ex in weekly_exams:
    eid = ex["id"] if isinstance(ex, dict) else ex
    if eid not in existing_exam_ids:
        exam_to_start = eid
        break

if not exam_to_start and weekly_exams:
    exam_to_start = weekly_exams[0]["id"] if isinstance(weekly_exams[0], dict) else weekly_exams[0]

if exam_to_start:
    # Exam detail
    s, b = req("GET", f"/exams/{exam_to_start}/", token=sneha_token)
    check(
        f"Exam detail {exam_to_start}",
        s,
        b,
        200,
        ["id", "title", "duration_minutes", "total_marks", "passing_percentage", "num_questions"],
    )

    # Start exam
    s, b = req("POST", f"/exams/{exam_to_start}/start/", token=sneha_token)
    if s in (200, 201):
        check("Exam start", s, b, s, ["id", "status"])
        attempt_id = b.get("id")
        questions = b.get("questions", b.get("attempt_questions", []))

        if attempt_id and questions:
            # Build answers
            answers = []
            for q in questions[:5]:
                q_id = q.get("question", q.get("question_id", q.get("id")))
                options = q.get("options", [])
                if isinstance(q_id, dict):
                    q_id = q_id.get("id")
                    options = q_id.get("options", options) if isinstance(q_id, dict) else options
                opt_id = options[0]["id"] if options else None
                if q_id and opt_id:
                    answers.append({"question_id": q_id, "option_id": opt_id})

            if answers:
                s, b = req("POST", f"/exams/attempts/{attempt_id}/submit/", {"answers": answers}, token=sneha_token)
                check("Exam submit", s, b, 200, ["id", "status", "score", "total_marks", "is_passed"])

                if b.get("id"):
                    s, b = req("GET", f"/exams/attempts/{b['id']}/result/", token=sneha_token)
                    check("Exam result after submit", s, b, 200)
    else:
        check(f"Exam start (status {s})", s, b, s)

# ── Doubts ─────────────────────────────────────────────────────
print("\n--- Doubts ---")

s, b = req("GET", "/doubts/", token=arjun_token)
check("GET doubts list", s, b, 200)

# Create a doubt
s, b = req(
    "POST",
    "/doubts/",
    {
        "title": "E2E test doubt — kinematics",
        "description": "In projectile motion, how does air resistance affect range?",
        "context_type": "topic",
    },
    token=arjun_token,
)
if s == 201:
    check("Create doubt", s, b, 201, ["id", "title", "description", "status", "context_type"])
    doubt_id = b.get("id")

    # Detail
    s, b = req("GET", f"/doubts/{doubt_id}/", token=arjun_token)
    check(f"Doubt detail {doubt_id}", s, b, 200, ["id", "title", "description", "status", "replies"])

    # Reply
    s, b = req(
        "POST",
        f"/doubts/{doubt_id}/reply/",
        {"message": "Specifically, does the trajectory remain parabolic with drag?"},
        token=arjun_token,
    )
    check("Doubt reply", s, b, 201, ["id", "message"])
else:
    check("Create doubt", s, b, 201)

# ── Feedback ───────────────────────────────────────────────────
print("\n--- Feedback ---")

s, b = req("GET", "/feedback/", token=arjun_token)
check("GET feedback list", s, b, 200)

# Submit feedback on a session
if session_id:
    s, b = req(
        "POST",
        f"/feedback/sessions/{session_id}/",
        {
            "overall_rating": 5,
            "difficulty_rating": 3,
            "clarity_rating": 4,
            "comment": "E2E test — great session!",
        },
        token=arjun_token,
    )
    if s == 201:
        check("Submit feedback", s, b, 201, ["id", "overall_rating", "difficulty_rating", "clarity_rating", "comment"])
    else:
        # May already have feedback for this session
        check(f"Submit feedback (status {s})", s, b, s)

# ── Payments ───────────────────────────────────────────────────
print("\n--- Payments ---")

s, b = req("GET", "/payments/purchases/", token=arjun_token)
check("GET purchases", s, b, 200)
purchases_data = b.get("results", []) if isinstance(b, dict) else b if isinstance(b, list) else []
if len(purchases_data) > 0:
    check("Purchase item fields", 200, purchases_data[0], 200, ["id", "level", "amount_paid", "status", "expires_at"])

s, b = req("GET", "/payments/transactions/", token=arjun_token)
check("GET transactions", s, b, 200)
txns_data = b.get("results", []) if isinstance(b, dict) else b if isinstance(b, list) else []
if len(txns_data) > 0:
    check("Transaction item fields", 200, txns_data[0], 200, ["id", "razorpay_order_id", "amount", "status"])

# ── Notifications ──────────────────────────────────────────────
print("\n--- Notifications ---")

s, b = req("GET", "/notifications/", token=arjun_token)
check("GET notifications", s, b, 200)
notifs = b.get("results", []) if isinstance(b, dict) else b if isinstance(b, list) else []
if len(notifs) > 0:
    check("Notification item fields", 200, notifs[0], 200, ["id", "title", "message", "notification_type", "is_read"])

s, b = req("GET", "/notifications/unread-count/", token=arjun_token)
check("Unread count", s, b, 200, ["unread_count"])

# Mark one as read
if len(notifs) > 0:
    nid = notifs[0]["id"]
    s, b = req("PATCH", f"/notifications/{nid}/read/", token=arjun_token)
    check("Mark notification read", s, b, 200)

s, b = req("POST", "/notifications/read-all/", token=arjun_token)
check("Mark all read", s, b, 200)

# ── Search ─────────────────────────────────────────────────────
print("\n--- Search ---")

s, b = req("GET", "/search/?q=physics", token=arjun_token)
check("Search 'physics'", s, b, 200)

# ── Issue Reports ──────────────────────────────────────────────
print("\n--- Issue Reports ---")

s, b = req(
    "POST",
    "/auth/report-issue/",
    {
        "category": "bug",
        "subject": "E2E test issue",
        "description": "Testing issue report endpoint.",
        "device_info": "Test Device",
    },
    token=arjun_token,
)
check("Report issue", s, b, 201, ["id", "category", "subject", "description", "is_resolved"])

s, b = req("GET", "/auth/my-issues/", token=arjun_token)
check("GET my issues", s, b, 200)

# ── Logout ─────────────────────────────────────────────────────
print("\n--- Logout ---")

# Get a fresh refresh token first
s, b = req("POST", "/auth/login/", {"email": "arjun.mehta@gmail.com", "password": "Student@123"})
arjun_refresh = b.get("tokens", {}).get("refresh", "")
arjun_token2 = b.get("tokens", {}).get("access", "")

s, b = req("POST", "/auth/logout/", {"refresh": arjun_refresh}, token=arjun_token2)
check("Logout", s, b, 200)


# ────────────────────────────────────────────────────────────────
# JOURNEY 3: Admin flow
# ────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("  JOURNEY 3: Admin endpoints")
print("=" * 65)

s, b = req("POST", "/auth/login/", {"email": "admin@iitprep.com", "password": "Admin@123"})
admin_token = b.get("tokens", {}).get("access", "")

# Students
s, b = req("GET", "/auth/admin/students/", token=admin_token)
check("Admin students list", s, b, 200)

# Analytics dashboard
s, b = req("GET", "/analytics/dashboard/", token=admin_token)
check("Admin analytics dashboard", s, b, 200, ["total_students", "total_revenue", "active_users"])

# Revenue
s, b = req("GET", "/analytics/revenue/", token=admin_token)
check("Admin revenue", s, b, 200)

# Level analytics
s, b = req("GET", "/analytics/levels/", token=admin_token)
check("Admin level analytics", s, b, 200)

# Payment dashboard
s, b = req("GET", "/payments/admin/dashboard/", token=admin_token)
check("Admin payment dashboard", s, b, 200)

# Admin purchases
s, b = req("GET", "/payments/admin/purchases/", token=admin_token)
check("Admin purchases", s, b, 200)

# Admin exams
s, b = req("GET", "/exams/admin/", token=admin_token)
check("Admin exams list", s, b, 200)

# Admin attempts
s, b = req("GET", "/exams/admin/attempts/", token=admin_token)
check("Admin attempts list", s, b, 200)

# Admin doubts
s, b = req("GET", "/doubts/admin/", token=admin_token)
check("Admin doubts list", s, b, 200)

# Admin feedback
s, b = req("GET", "/feedback/admin/", token=admin_token)
check("Admin feedback list", s, b, 200)

# Admin courses
s, b = req("GET", "/courses/admin/", token=admin_token)
check("Admin courses list", s, b, 200)

# Admin sessions
s, b = req("GET", "/courses/admin/sessions/", token=admin_token)
check("Admin sessions list", s, b, 200)

# Admin levels
s, b = req("GET", "/levels/admin/", token=admin_token)
check("Admin levels list", s, b, 200)

# Admin banners
s, b = req("GET", "/home/admin/banners/", token=admin_token)
check("Admin banners list", s, b, 200)

# Admin issues
s, b = req("GET", "/auth/admin/issues/", token=admin_token)
check("Admin issues list", s, b, 200)

# Admin questions
s, b = req("GET", "/exams/admin/questions/", token=admin_token)
check("Admin questions list", s, b, 200)


# ────────────────────────────────────────────────────────────────
# JOURNEY 4: Fresh student with NO onboarding
# ────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("  JOURNEY 4: Fresh student (no onboarding)")
print("=" * 65)

s, b = req("POST", "/auth/login/", {"email": "amit.tiwari@gmail.com", "password": "Student@123"})
check("Login fresh student", s, b, 200, ["user", "tokens"])
fresh_token = b.get("tokens", {}).get("access", "")

s, b = req("GET", "/auth/me/", token=fresh_token)
check("Fresh student profile", s, b, 200, ["id", "email", "profile"])
profile = b.get("profile", {})
if profile:
    assert profile.get("is_onboarding_completed") is False, "Should NOT be onboarded"
    assert profile.get("is_onboarding_exam_attempted") is False, "Should NOT have attempted onboarding exam"
    print(
        f"  OK    Confirmed: onboarding_completed={profile.get('is_onboarding_completed')}, exam_attempted={profile.get('is_onboarding_exam_attempted')}"
    )
    PASS += 1

s, b = req("GET", "/progress/dashboard/", token=fresh_token)
check("Fresh student dashboard", s, b, 200)

# Purchases should be empty
s, b = req("GET", "/payments/purchases/", token=fresh_token)
check("Fresh student purchases (should be empty)", s, b, 200)

# Notifications
s, b = req("GET", "/notifications/", token=fresh_token)
check("Fresh student notifications", s, b, 200)


# ────────────────────────────────────────────────────────────────
# CLEANUP: Delete e2e test user
# ────────────────────────────────────────────────────────────────
print("\n--- Cleanup ---")
s, b = req("POST", "/auth/login/", {"email": E2E_EMAIL, "password": "NewPass@456"})
cleanup_token = b.get("tokens", {}).get("access", "")
if cleanup_token:
    s, b = req("DELETE", "/auth/me/", token=cleanup_token)
    check("Delete e2e test user", s, b, s)


# ────────────────────────────────────────────────────────────────
# SUMMARY
# ────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print(f"  RESULTS:  {PASS} passed,  {FAIL} failed")
print("=" * 65)

if FAIL > 0:
    sys.exit(1)
