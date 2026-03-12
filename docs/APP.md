# LMS Backend - App API Documentation

**Base URL:** `/api/v1/`
**Authentication:** JWT (Bearer token via `Authorization: Bearer <access_token>`)
**Content-Type:** `application/json` (unless uploading files — use `multipart/form-data`)

---

## Authentication & Tokens

All protected endpoints require a JWT access token in the `Authorization` header.

```
Authorization: Bearer <access_token>
```

Tokens are obtained via `/api/v1/auth/login/`, `/api/v1/auth/register/`, or `/api/v1/auth/google/`.
Access tokens expire after a short period — use `/api/v1/auth/token/refresh/` with a refresh token to get a new pair of tokens (refresh token rotation is enabled).

### Permission Levels

| Permission | Description |
|---|---|
| **Public** | No authentication required |
| **Authenticated** | Any logged-in user |
| **Student** | Only student accounts (`is_student=true`) |

---

## 1. Users & Auth

### `POST /api/v1/auth/register/`
**Permission:** Public
**Rate Limit:** `login` (5/min)

Register a new student account. Returns user data and JWT tokens.

**Request:**
```json
{
  "email": "student@example.com",
  "full_name": "John Doe",
  "phone": "9876543210",
  "password": "securepass123"
}
```

**Response (201):**
```json
{
  "user": {
    "id": 1,
    "email": "student@example.com",
    "full_name": "John Doe",
    "phone": "9876543210",
    "profile_picture": null,
    "is_student": true,
    "is_admin": false
  },
  "tokens": {
    "refresh": "eyJ...",
    "access": "eyJ..."
  }
}
```

---

### `POST /api/v1/auth/login/`
**Permission:** Public
**Rate Limit:** `login` (5/min)

Authenticate with email and password.

**Request:**
```json
{
  "email": "student@example.com",
  "password": "securepass123"
}
```

**Response (200):** Same structure as register response.

---

### `POST /api/v1/auth/google/`
**Permission:** Public
**Rate Limit:** `login` (5/min)

Authenticate using a Google ID token (from Google Sign-In).

**Request:**
```json
{
  "id_token": "google-id-token-string"
}
```

**Response (200):**
```json
{
  "user": {
    "id": 1,
    "email": "student@example.com",
    "full_name": "John Doe",
    "phone": null,
    "profile_picture": null,
    "is_student": true,
    "is_admin": false
  },
  "tokens": {
    "refresh": "eyJ...",
    "access": "eyJ..."
  },
  "created": true
}
```

---

### `POST /api/v1/auth/logout/`
**Permission:** Authenticated

Blacklist the refresh token.

**Request:**
```json
{
  "refresh": "eyJ..."
}
```

**Response (200):**
```json
{
  "detail": "Logged out."
}
```

**Error responses:**
- **400** — Refresh token missing: `{"detail": "Refresh token is required."}`
- **400** — Invalid or expired token: `{"detail": "Invalid or expired token."}`

---

### `POST /api/v1/auth/token/refresh/`
**Permission:** Public

Get a new token pair using a refresh token. Refresh token rotation is enabled — each call returns a new refresh token and blacklists the old one.

**Request:**
```json
{
  "refresh": "eyJ..."
}
```

**Response (200):**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

---

### `GET /api/v1/auth/me/`
**Permission:** Authenticated

Get current user profile. Includes student profile data (with `gender`, `is_onboarding_exam_attempted`) for student accounts.

**Response (200):**
```json
{
  "id": 1,
  "email": "student@example.com",
  "full_name": "John Doe",
  "phone": "9876543210",
  "profile_picture": "/media/users/avatars/photo.png",
  "is_student": true,
  "is_admin": false,
  "profile": {
    "id": 1,
    "user": { ... },
    "current_level": 1,
    "current_level_name": "Level 1",
    "highest_cleared_level": null,
    "highest_cleared_level_name": null,
    "gender": "male",
    "is_onboarding_completed": false,
    "is_onboarding_exam_attempted": false,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

The `profile` key is only present when `is_student` is `true`.

---

### `PATCH /api/v1/auth/me/`
**Permission:** Authenticated

Update profile fields. Supports `multipart/form-data` for avatar upload.

**Request (JSON):**
```json
{
  "full_name": "Updated Name",
  "phone": "1234567890",
  "gender": "male"
}
```

**Updatable fields:** `full_name`, `phone`, `profile_picture` (file), `gender` (one of `male`, `female`, `other`).

**Request (multipart for avatar):**
```
Content-Type: multipart/form-data
profile_picture: <file>
```

**Note:** Profile picture uploads have a **5 MB** size limit. Files exceeding 5 MB will receive a `400 Bad Request` response.

**Response (200):** Returns the updated `UserSerializer` data.

---

### `DELETE /api/v1/auth/me/`
**Permission:** Authenticated

Remove the current profile picture.

**Response (200):** Returns the updated `UserSerializer` data.

---

### `POST /api/v1/auth/change-password/`
**Permission:** Authenticated

Change the current user's password. Returns new JWT tokens (old tokens are invalidated).

**Request:**
```json
{
  "old_password": "current123",
  "new_password": "newpass456"
}
```

**Response (200):**
```json
{
  "detail": "Password changed successfully.",
  "refresh": "eyJ...",
  "access": "eyJ..."
}
```

---

### `POST /api/v1/auth/password-reset/`
**Permission:** Public
**Rate Limit:** `login` (5/min)

Request a password reset email. Always returns 200 to prevent email enumeration.

```json
{
  "email": "student@example.com"
}
```

---

### `POST /api/v1/auth/password-reset/confirm/`
**Permission:** Public
**Rate Limit:** `login` (5/min)

```json
{
  "uid": "base64-encoded-user-id",
  "token": "reset-token",
  "new_password": "newpass456"
}
```

---

### `POST /api/v1/auth/otp/send/`
**Permission:** Public
**Rate Limit:** `login` (5/min)

```json
{
  "email": "student@example.com",
  "purpose": "verify"
}
```
Purpose: `"verify"` or `"password_reset"`.

---

### `POST /api/v1/auth/otp/verify/`
**Permission:** Public
**Rate Limit:** `login` (5/min)

```json
{
  "email": "student@example.com",
  "otp": "123456",
  "purpose": "verify"
}
```

**Response (200):**
```json
{
  "detail": "OTP verified.",
  "verified": true
}
```

---

### `GET /api/v1/auth/preferences/`
### `PATCH /api/v1/auth/preferences/`
**Permission:** Authenticated

Get or update notification preferences.

```json
{
  "push_notifications": true,
  "email_notifications": true,
  "doubt_reply_notifications": true,
  "exam_result_notifications": true,
  "promotional_notifications": false
}
```

---

### `POST /api/v1/auth/onboarding/complete/`
**Permission:** Authenticated

Mark onboarding as completed.

**Response (200):**
```json
{
  "detail": "Onboarding completed.",
  "is_onboarding_completed": true
}
```

---

### `POST /api/v1/auth/report-issue/`
**Permission:** Authenticated

Report an issue. Supports optional `screenshot` file via multipart.

```json
{
  "category": "bug",
  "subject": "App crashes on login",
  "description": "Detailed description..."
}
```
Categories: `bug`, `content`, `payment`, `account`, `other`.

**Response (201):**
```json
{
  "id": 1,
  "category": "bug",
  "subject": "App crashes on login",
  "description": "Detailed description...",
  "screenshot": null,
  "is_resolved": false,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### `GET /api/v1/auth/my-issues/`
**Permission:** Authenticated
**Pagination:** SmallPagination (10/page)
**Filters:** `category`, `is_resolved`

List the current user's issue reports.

---

## 2. Levels

### `GET /api/v1/levels/`
**Permission:** Public
**Pagination:** None (returns flat list)
**Cache:** 5 minutes

List all active levels ordered by `order`.

**Response (200):**
```json
[
  {
    "id": 1,
    "name": "Level 1",
    "order": 1,
    "description": "...",
    "is_active": true,
    "passing_percentage": 50.0,
    "price": "999.00",
    "validity_days": 90,
    "max_final_exam_attempts": 3,
    "courses_count": 5,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

---

### `GET /api/v1/levels/<id>/`
**Permission:** Public
**Cache:** 5 minutes

Get level details including its courses.

**Response (200):**
```json
{
  "id": 1,
  "name": "Level 1",
  "order": 1,
  "description": "...",
  "is_active": true,
  "passing_percentage": 50.0,
  "price": "999.00",
  "validity_days": 90,
  "max_final_exam_attempts": 3,
  "courses": [
    {
      "id": 1,
      "title": "Physics",
      "description": "...",
      "is_active": true,
      "weeks_count": 4
    }
  ],
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## 3. Courses

### `GET /api/v1/courses/level/<level_id>/`
**Permission:** Authenticated

Get active courses for a specific level.

**Response (200):**
```json
[
  {
    "id": 1,
    "level": 1,
    "level_name": "Level 1",
    "title": "Physics",
    "description": "...",
    "is_active": true,
    "weeks_count": 4,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

---

### `GET /api/v1/courses/<course_id>/sessions/`
**Permission:** Student (requires active purchase for the course's level)
**Pagination:** StandardPagination (20/page)

List sessions for a purchased course. Returns `402 Payment Required` if no active purchase.

**Response fields per session:** `id`, `week`, `title`, `description`, `duration_seconds`, `order`, `session_type`, `is_active`.

---

### `GET /api/v1/courses/sessions/<id>/`
**Permission:** Student (requires active purchase)

Get full session details including `video_url`, `file_url`, `resource_type`, `markdown_content`, and `exam` FK. Returns `402` if no purchase, `403` if session is not yet accessible.

---

### `POST /api/v1/courses/sessions/<id>/complete-resource/`
**Permission:** Student

Mark a resource-type session (PDF, note, markdown) as completed.

**Response (200):**
```json
{
  "detail": "Resource session marked as completed."
}
```

---

### `GET /api/v1/courses/bookmarks/`
**Permission:** Student
**Pagination:** SmallPagination (10/page)

List the current student's session bookmarks.

### `POST /api/v1/courses/bookmarks/`
**Permission:** Student

Create a session bookmark.

**Request:**
```json
{
  "session": 1
}
```

**Response (201):**
```json
{
  "id": 1,
  "session": 1,
  "session_title": "Introduction to Mechanics",
  "session_week": 1,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### `DELETE /api/v1/courses/bookmarks/<id>/`
**Permission:** Student

Remove a bookmark. Only the owner can delete. Returns `204 No Content`.

---

## 4. Exams

### `GET /api/v1/exams/<id>/`
**Permission:** Student

Get exam info with eligibility status.

**Response (200):**
```json
{
  "id": 1,
  "level": 1,
  "level_name": "Level 1",
  "week": 1,
  "week_name": "Week 1",
  "course": 1,
  "course_title": "Physics",
  "exam_type": "level_final",
  "title": "Level 1 Final Exam",
  "duration_minutes": 60,
  "total_marks": 20,
  "passing_percentage": 50.0,
  "num_questions": 5,
  "pool_size": 20,
  "is_proctored": true,
  "max_warnings": 3,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "is_eligible": true
}
```

**Exam types:** `weekly`, `level_final`, `onboarding`.

---

### `POST /api/v1/exams/<id>/start/`
**Permission:** Student

Start an exam attempt. Returns a random set of questions. If an active (in-progress) attempt exists, returns it with `200` instead of `201`.

**Response (201):**
```json
{
  "id": 1,
  "exam": 1,
  "exam_title": "Level 1 Final Exam",
  "started_at": "2024-01-01T00:00:00Z",
  "submitted_at": null,
  "status": "in_progress",
  "score": null,
  "total_marks": 20,
  "is_passed": false,
  "is_disqualified": false,
  "questions": [
    {
      "id": 1,
      "question": {
        "id": 5,
        "text": "What is...?",
        "image_url": null,
        "marks": 4,
        "question_type": "mcq",
        "options": [
          {"id": 10, "text": "Option A", "image_url": null},
          {"id": 11, "text": "Option B", "image_url": null}
        ]
      },
      "selected_option": null,
      "selected_option_ids": [],
      "text_answer": "",
      "order": 1
    }
  ]
}
```

---

### `POST /api/v1/exams/attempts/<id>/submit/`
**Permission:** Student
**Rate Limit:** `exam_submit` (30/hour)

Submit answers for an exam attempt.

**Request:**
```json
{
  "answers": [
    {"question_id": 5, "option_id": 12},
    {"question_id": 6, "option_ids": [14, 15]},
    {"question_id": 7, "text_answer": "photosynthesis"}
  ]
}
```

**Answer types:**
- MCQ: `option_id` (single integer)
- Multi-Select MCQ: `option_ids` (list of integers, max 20)
- Fill-in-the-Blank: `text_answer` (string, max 1000 chars)

**Response (200):**
```json
{
  "id": 1,
  "exam": 1,
  "exam_title": "Level 1 Final Exam",
  "started_at": "2024-01-01T00:00:00Z",
  "submitted_at": "2024-01-01T01:00:00Z",
  "status": "submitted",
  "score": 16.0,
  "total_marks": 20,
  "is_passed": true,
  "is_disqualified": false
}
```

---

### `GET /api/v1/exams/attempts/<id>/result/`
**Permission:** Student

Get detailed result with per-question breakdown including explanations, correct answers, and marks awarded. Returns `400` if the exam has not been submitted yet.

**Response (200):**
```json
{
  "id": 1,
  "exam": 1,
  "exam_title": "Level 1 Final Exam",
  "started_at": "...",
  "submitted_at": "...",
  "status": "submitted",
  "score": 16.0,
  "total_marks": 20,
  "is_passed": true,
  "is_disqualified": false,
  "questions": [
    {
      "id": 1,
      "question": 5,
      "question_text": "What is...?",
      "question_type": "mcq",
      "selected_option": 12,
      "selected_option_ids": [],
      "text_answer": "",
      "is_correct": true,
      "marks_awarded": 4.0,
      "order": 1,
      "explanation": "Because...",
      "correct_text_answer": null,
      "correct_option_ids": [12]
    }
  ]
}
```

---

### `GET /api/v1/exams/attempts/`
**Permission:** Student
**Pagination:** SmallPagination (10/page)
**Filters:** `exam`, `status`, `is_passed`

List all exam attempts by the current student.

---

### Proctoring

### `POST /api/v1/exams/attempts/<id>/report-violation/`
**Permission:** Student

Report a proctoring violation during an active exam. Auto-disqualifies when `max_warnings` is reached.

**Request:**
```json
{
  "violation_type": "tab_switch",
  "details": "Switched to another tab"
}
```

Violation types: `full_screen_exit`, `tab_switch`, `voice_detected`, `multi_face`, `extension_detected`.

**Response (201):**
```json
{
  "id": 1,
  "attempt": 1,
  "violation_type": "tab_switch",
  "warning_number": 2,
  "details": "Switched to another tab",
  "created_at": "2024-01-01T00:30:00Z",
  "total_warnings": 2,
  "max_warnings": 3,
  "is_disqualified": false
}
```

---

### `GET /api/v1/exams/attempts/<id>/violations/`
**Permission:** Student

Get all proctoring violations for an attempt.

**Response (200):**
```json
{
  "violations": [
    {
      "id": 1,
      "attempt": 1,
      "violation_type": "tab_switch",
      "warning_number": 1,
      "details": "...",
      "created_at": "2024-01-01T00:30:00Z"
    }
  ],
  "total_warnings": 1,
  "max_warnings": 3,
  "is_disqualified": false
}
```

---

## 5. Payments (Razorpay)

### `POST /api/v1/payments/initiate/`
**Permission:** Student
**Rate Limit:** `payment` (10/min)

Create a Razorpay order for level purchase.

**Request:**
```json
{
  "level_id": 1
}
```

**Response (201):**
```json
{
  "transaction_id": 1,
  "razorpay_order_id": "order_abc123",
  "amount": "99900",
  "currency": "INR",
  "level_id": 1,
  "level_name": "Level 1",
  "razorpay_key": "rzp_test_..."
}
```

**Error responses:**
- **404** — Level not found
- **400** — Already purchased / validation error
- **502** — Payment gateway error

---

### `POST /api/v1/payments/verify/`
**Permission:** Student

Verify Razorpay payment and activate purchase.

**Request:**
```json
{
  "razorpay_order_id": "order_abc123",
  "razorpay_payment_id": "pay_xyz789",
  "razorpay_signature": "..."
}
```

**Response (201):**
```json
{
  "id": 1,
  "level": 1,
  "level_name": "Level 1",
  "amount_paid": "999.00",
  "purchased_at": "2024-01-01T00:00:00Z",
  "expires_at": "2024-04-01T00:00:00Z",
  "status": "active",
  "is_valid": true,
  "extended_by_days": 0
}
```

---

### `GET /api/v1/payments/purchases/`
**Permission:** Student
**Pagination:** SmallPagination (10/page)
**Filters:** `level`, `status`

List the current student's purchases.

**Purchase statuses:** `active`, `expired`, `revoked`.

---

### `GET /api/v1/payments/transactions/`
**Permission:** Student
**Pagination:** SmallPagination (10/page)
**Filters:** `status`

List payment transactions.

**Transaction fields:** `id`, `razorpay_order_id`, `razorpay_payment_id`, `amount`, `status`, `created_at`.
**Transaction statuses:** `pending`, `success`, `failed`, `refunded`.

---

## 6. Progress

### `GET /api/v1/progress/dashboard/`
**Permission:** Student

Get student dashboard with current level, progress overview, and next recommended action.

**Response (200):**
```json
{
  "current_level": {"id": 1, "name": "Level 1", "order": 1},
  "level_progress": [
    {
      "id": 1,
      "level": 1,
      "level_name": "Level 1",
      "level_order": 1,
      "status": "in_progress",
      "started_at": "2024-01-01T00:00:00Z",
      "completed_at": null,
      "final_exam_attempts_used": 0
    }
  ],
  "course_progress": [
    {
      "id": 1,
      "course": 1,
      "course_title": "Physics",
      "level_name": "Level 1",
      "status": "in_progress",
      "started_at": "2024-01-01T00:00:00Z",
      "completed_at": null
    }
  ],
  "next_action": "attempt_exam",
  "message": "You are ready to take the Level 1 exam.",
  "is_onboarding_exam_attempted": true
}
```

`next_action` values: `purchase_course`, `watch_sessions`, `submit_feedback`, `attempt_exam`, `all_complete`.

---

### `POST /api/v1/progress/sessions/<session_id>/`
**Permission:** Student
**Rate Limit:** `progress_update` (120/min)

Update watch progress. Auto-completes at 90% if feedback is submitted.

**Request:**
```json
{
  "watched_seconds": 1500
}
```

**Response (200):**
```json
{
  "id": 1,
  "session": 1,
  "session_title": "Introduction to Mechanics",
  "total_duration": 1800,
  "watched_seconds": 1500,
  "is_completed": false,
  "completed_at": null,
  "is_exam_passed": false
}
```

---

### `GET /api/v1/progress/levels/<level_id>/sessions/`
**Permission:** Student
**Pagination:** SmallPagination (10/page)

List session progress for all sessions in a level.

---

### `GET /api/v1/progress/levels/`
**Permission:** Student
**Pagination:** None (returns flat list)

List level progress for all levels.

**Level progress statuses:** `not_started`, `in_progress`, `syllabus_complete`, `exam_passed`, `exam_failed`.

---

### `GET /api/v1/progress/courses/<course_id>/`
**Permission:** Student

Get progress for a specific course.

**Response (200):**
```json
{
  "id": 1,
  "course": 1,
  "course_title": "Physics",
  "level_name": "Level 1",
  "status": "in_progress",
  "started_at": "2024-01-01T00:00:00Z",
  "completed_at": null
}
```

**Course progress statuses:** `not_started`, `in_progress`, `completed`.

---

### `GET /api/v1/progress/levels/<level_id>/courses/`
**Permission:** Student

List course progress for all courses in a level.

**Response (200):** Array of course progress objects.

---

### `GET /api/v1/progress/calendar/?year=2024&month=6`
**Permission:** Student

Get activity calendar showing sessions watched and exams taken per day.

**Query parameters (required):**
- `year` — 2000–2100
- `month` — 1–12

**Response (200):**
```json
{
  "year": 2024,
  "month": 6,
  "active_dates": [
    {"date": "2024-06-01", "sessions_watched": 3, "exams_taken": 0}
  ]
}
```

---

### `GET /api/v1/progress/leaderboard/`
**Permission:** Authenticated

Get leaderboard of top students ranked by levels cleared and total exam scores.

**Query parameters:**
- `level` (optional) — Filter by level ID
- `limit` (optional) — Number of results, default 20, max 50

**Response (200):**
```json
{
  "leaderboard": [
    {
      "rank": 1,
      "student_id": 5,
      "full_name": "Top Student",
      "profile_picture": "/media/users/avatars/photo.png",
      "levels_cleared": 3,
      "total_score": 156.0,
      "exams_passed": 5
    }
  ],
  "my_rank": 12
}
```

---

## 7. Doubts (Q&A Support)

### `GET /api/v1/doubts/`
**Permission:** Student
**Pagination:** SmallPagination (10/page)
**Rate Limit:** `doubt_create` (10/min, applies to POST only)

List the current student's doubt tickets.

**Response fields per ticket:** `id`, `student`, `student_name`, `title`, `status`, `context_type`, `created_at`, `replies_count`.

### `POST /api/v1/doubts/`
**Permission:** Student

Create a doubt ticket.

**Request:**
```json
{
  "context_type": "session",
  "session": 5,
  "title": "Confused about topic X",
  "description": "Can you explain..."
}
```

**Fields:**
- `context_type` (string, required) — One of: `session`, `topic`, `exam_question`.
- `session` (integer, optional) — FK to the session. Required when `context_type` is `session`.
- `exam_question` (integer, optional) — FK to the exam question. Required when `context_type` is `exam_question`.
- `title` (string, required)
- `description` (string, required)
- `screenshot` (file, optional)

**Purchase requirement:** When `context_type` is `session` or `exam_question`, the student must have an active purchase for the associated level. `topic` doubts do **not** require a purchase.

Returns `403 Forbidden` if no active purchase:
```json
{
  "detail": "You must purchase a course for this level to submit a doubt."
}
```

---

### `GET /api/v1/doubts/<id>/`
**Permission:** Student

Get doubt ticket details with all replies.

---

### `POST /api/v1/doubts/<id>/reply/`
**Permission:** Student

Reply to a doubt ticket. Supports `attachment` file via multipart.

**Request:**
```json
{
  "message": "Thanks, I still have a question about..."
}
```

**Response (201):**
```json
{
  "id": 1,
  "ticket": 1,
  "author": 1,
  "author_name": "John Doe",
  "author_role": "student",
  "message": "Thanks, I still have a question about...",
  "attachment": null,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## 8. Feedback

### `POST /api/v1/feedback/sessions/<session_id>/`
**Permission:** Student (requires active purchase for the session's level)
**Rate Limit:** `feedback` (20/min)

Submit mandatory session feedback (required for session completion). The session ID comes from the URL, not the request body.

**Request:**
```json
{
  "overall_rating": 5,
  "difficulty_rating": 3,
  "clarity_rating": 4,
  "comment": "Great session!"
}
```

- `overall_rating` (integer, required) — 1–5
- `difficulty_rating` (integer, optional) — 1–5
- `clarity_rating` (integer, optional) — 1–5
- `comment` (string, optional)

One feedback per session per student. Returns `400` if already submitted.

Returns `403 Forbidden` if no active purchase:
```json
{
  "detail": "You must purchase a course for this level to submit feedback."
}
```

**Response (201):**
```json
{
  "id": 1,
  "session": 1,
  "session_title": "Introduction to Mechanics",
  "overall_rating": 5,
  "difficulty_rating": 3,
  "clarity_rating": 4,
  "comment": "Great session!",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### `GET /api/v1/feedback/`
**Permission:** Student
**Pagination:** SmallPagination (10/page)
**Filters:** `session`, `overall_rating`

List the current student's feedback submissions.

---

## 9. Notifications

### `GET /api/v1/notifications/`
**Permission:** Authenticated
**Pagination:** SmallPagination (10/page)
**Filters:** `is_read`, `notification_type`

List notifications for the current user.

**Notification types:** `purchase`, `exam_result`, `doubt_reply`, `level_unlock`, `course_expiry`, `general`.

---

### `DELETE /api/v1/notifications/<id>/`
**Permission:** Authenticated

Delete a single notification. Returns `204 No Content`.

---

### `PATCH /api/v1/notifications/<id>/read/`
**Permission:** Authenticated

Mark a single notification as read.

---

### `POST /api/v1/notifications/read-all/`
**Permission:** Authenticated

Mark all notifications as read.

**Response (200):**
```json
{
  "detail": "All notifications marked as read.",
  "count": 5
}
```

---

### `DELETE /api/v1/notifications/clear-all/`
**Permission:** Authenticated

Delete all notifications for the current user.

**Response (200):**
```json
{
  "detail": "All notifications cleared.",
  "count": 5
}
```

---

### `GET /api/v1/notifications/unread-count/`
**Permission:** Authenticated

**Response (200):**
```json
{
  "unread_count": 3
}
```

---

## 10. Home

### `GET /api/v1/home/banners/`
**Permission:** Public
**Pagination:** None
**Cache:** 5 minutes

Get active banners for the home screen.

**Response (200):**
```json
[
  {
    "id": 1,
    "title": "New Course Available",
    "subtitle": "Check out our latest physics course",
    "image_url": "https://...",
    "link_type": "course",
    "link_id": 1,
    "link_url": null
  }
]
```

**Banner link types:** `course`, `level`, `url`, `none`.

---

### `GET /api/v1/home/featured/`
**Permission:** Public
**Cache:** 1 minute

Get featured/active courses for the home screen (max 10).

**Response (200):** Array of course objects.

---

## 11. Search

### `GET /api/v1/search/?q=keyword`
**Permission:** Authenticated
**Rate Limit:** `search` (60/min)

Global search across levels, courses, sessions, and questions.

**Query parameters:**
- `q` (required) — Search query, minimum 2 characters
- `level` (optional) — Scope search to a level ID
- `week` (optional) — Scope search to a week ID

**Response (200):**
```json
{
  "levels": [...],
  "courses": [...],
  "sessions": [...],
  "questions_count": 15
}
```

When `level` is provided, `levels` list is empty (already scoped). Results are capped at 5 levels, 10 courses, 10 sessions.

---

## 12. Health Check

### `GET /api/v1/health/`
**Permission:** Public

Check the health of the API, database, and Redis cache.

**Response (200):**
```json
{
  "status": "healthy",
  "database": true,
  "redis": true
}
```

`status` is `"healthy"` when both database and Redis are reachable, `"degraded"` otherwise.

---

## Pagination

List endpoints use one of three page-based pagination classes:

| Class | Page Size | Max Page Size | Used By |
|---|---|---|---|
| **StandardPagination** | 20 | 100 | Default for most endpoints |
| **SmallPagination** | 10 | 50 | Bookmarks, doubts, feedback, attempts, purchases, transactions, notifications, issues, session progress |

Some endpoints have no pagination (flat list): levels, level progress, banners.

**Paginated response format:**
```json
{
  "count": 42,
  "next": "http://host/api/v1/endpoint/?page=2",
  "previous": null,
  "results": [...]
}
```

---

## Error Responses

**400 Bad Request:**
```json
{
  "field_name": ["Error message."]
}
```

**401 Unauthorized:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**402 Payment Required:**
```json
{
  "detail": "You must purchase this course to access its content."
}
```

**403 Forbidden:**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

**403 Forbidden (purchase-related):** Returned by feedback and doubt endpoints when the student does not have an active purchase for the relevant level:
```json
{
  "detail": "You must purchase a course for this level to submit feedback."
}
```
```json
{
  "detail": "You must purchase a course for this level to submit a doubt."
}
```

**404 Not Found:**
```json
{
  "detail": "Not found."
}
```

**429 Too Many Requests:**
```json
{
  "detail": "Request was throttled."
}
```

**502 Bad Gateway:**
```json
{
  "detail": "Payment gateway error."
}
```

---

## Rate Limiting

| Scope | Limit | Endpoints |
|---|---|---|
| Anonymous requests | 30/min | All unauthenticated requests |
| Authenticated requests | 120/min | All authenticated requests |
| `login` | 5/min | Register, login, Google auth, OTP, password reset |
| `payment` | 10/min | Payment initiation |
| `exam_submit` | 30/hour | Exam submission |
| `search` | 60/min | Global search |
| `doubt_create` | 10/min | Doubt ticket creation |
| `feedback` | 20/min | Feedback submission |
| `progress_update` | 120/min | Session progress updates |

---

## Interactive API Docs

- **Swagger UI:** `/api/docs/`
- **ReDoc:** `/api/redoc/`
- **OpenAPI Schema (JSON):** `/api/schema/`
