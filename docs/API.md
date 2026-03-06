# LMS Backend - API Documentation

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
Access tokens expire after a short period — use `/api/v1/auth/token/refresh/` with a refresh token to get a new access token.

### Permission Levels

| Permission | Description |
|---|---|
| **Public** | No authentication required |
| **Authenticated** | Any logged-in user |
| **Student** | Only student accounts |
| **Admin** | Only admin/staff accounts |

---

## 1. Users & Auth

### `POST /api/v1/auth/register/`
**Permission:** Public

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
  "user": { ... },
  "tokens": { "refresh": "...", "access": "..." },
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

Get a new access token using a refresh token.

**Request:**
```json
{
  "refresh": "eyJ..."
}
```

**Response (200):**
```json
{
  "access": "eyJ..."
}
```

---

### `GET /api/v1/auth/me/`
**Permission:** Authenticated

Get current user profile. Includes student profile data for student accounts.

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
    "onboarding_completed": false,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

### `PATCH /api/v1/auth/me/`
**Permission:** Authenticated

Update profile fields. Supports `multipart/form-data` for avatar upload.

**Request (JSON):**
```json
{
  "full_name": "Updated Name",
  "phone": "1234567890"
}
```

**Request (multipart for avatar):**
```
Content-Type: multipart/form-data
profile_picture: <file>
```

**Note:** Profile picture uploads have a **5 MB** size limit. Files exceeding 5 MB will receive a `400 Bad Request` response.

---

### `DELETE /api/v1/auth/me/`
**Permission:** Authenticated

Remove the current profile picture.

---

### `POST /api/v1/auth/change-password/`
**Permission:** Authenticated

```json
{
  "old_password": "current123",
  "new_password": "newpass456"
}
```

---

### `POST /api/v1/auth/password-reset/`
**Permission:** Public

Request a password reset email. Always returns 200 to prevent email enumeration.

```json
{
  "email": "student@example.com"
}
```

---

### `POST /api/v1/auth/password-reset/confirm/`
**Permission:** Public

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

```json
{
  "email": "student@example.com",
  "otp": "123456",
  "purpose": "verify"
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
**Permission:** Authenticated (Student only)

Mark onboarding as completed.

---

### `POST /api/v1/auth/report-issue/`
**Permission:** Authenticated

```json
{
  "category": "bug",
  "subject": "App crashes on login",
  "description": "Detailed description..."
}
```
Categories: `bug`, `content`, `payment`, `account`, `other`. Supports optional `screenshot` file via multipart.

---

### `GET /api/v1/auth/my-issues/`
**Permission:** Authenticated

List the current user's issue reports. Paginated.

---

### Admin: `GET /api/v1/auth/admin/students/`
### Admin: `GET|PATCH /api/v1/auth/admin/students/<id>/`
**Permission:** Admin

List/update students. Filterable by `current_level`, `highest_cleared_level`. Searchable by email/name.

---

## 2. Levels

### `GET /api/v1/levels/`
**Permission:** Public

List all active levels ordered by `order`.

**Response (200):**
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "name": "Level 1",
      "order": 1,
      "description": "...",
      "is_active": true
    }
  ]
}
```

---

### `GET /api/v1/levels/<id>/`
**Permission:** Public

Get level details with its weeks.

---

### Admin: `GET|POST /api/v1/levels/admin/`
### Admin: `GET|PATCH|DELETE /api/v1/levels/admin/<id>/`
### Admin: `GET|POST /api/v1/levels/admin/<level_id>/weeks/`
### Admin: `GET|PATCH|DELETE /api/v1/levels/admin/weeks/<id>/`
**Permission:** Admin

Full CRUD for levels and weeks.

---

## 3. Courses

### `GET /api/v1/courses/level/<level_id>/`
**Permission:** Authenticated

Get courses for a specific level.

---

### `GET /api/v1/courses/<course_id>/sessions/`
**Permission:** Student (requires active purchase)

List sessions for a purchased course. Returns `402 Payment Required` if no active purchase.

---

### `GET /api/v1/courses/sessions/<id>/`
**Permission:** Student (requires active purchase)

Get session details including `video_url`. Returns `402` if no purchase.

---

### `GET /api/v1/courses/bookmarks/`
### `POST /api/v1/courses/bookmarks/`
**Permission:** Student

List or create session bookmarks.

**Create request:**
```json
{
  "session": 1
}
```

---

### `DELETE /api/v1/courses/bookmarks/<id>/`
**Permission:** Student

Remove a bookmark. Only the owner can delete.

---

### Admin: Course, Session, Resource CRUD
**Permission:** Admin

- `GET|POST /api/v1/courses/admin/`
- `GET|PATCH|DELETE /api/v1/courses/admin/<id>/`
- `GET|POST /api/v1/courses/admin/sessions/`
- `GET|PATCH|DELETE /api/v1/courses/admin/sessions/<id>/`
- `GET|POST /api/v1/courses/admin/resources/`
- `GET|PATCH|DELETE /api/v1/courses/admin/resources/<id>/`

---

## 4. Exams

### `GET /api/v1/exams/<id>/`
**Permission:** Student

Get exam info with eligibility status.

**Response:**
```json
{
  "id": 1,
  "title": "Level 1 Final Exam",
  "exam_type": "level_final",
  "duration_minutes": 60,
  "total_marks": 20,
  "passing_percentage": 50.0,
  "num_questions": 5,
  "is_proctored": true,
  "max_warnings": 3,
  "is_eligible": true
}
```

---

### `POST /api/v1/exams/<id>/start/`
**Permission:** Student

Start an exam attempt. Returns a random set of questions. If an active attempt exists, returns it instead.

**Response (201):**
```json
{
  "id": 1,
  "exam": { ... },
  "status": "in_progress",
  "total_marks": 20,
  "questions": [
    {
      "id": 1,
      "question": {
        "id": 5,
        "text": "What is...?",
        "question_type": "mcq",
        "options": [...]
      },
      "order": 1
    }
  ]
}
```

---

### `POST /api/v1/exams/attempts/<id>/submit/`
**Permission:** Student

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
- Multi-Select MCQ: `option_ids` (list of integers)
- Fill-in-the-Blank: `text_answer` (string)

**Response (200):**
```json
{
  "id": 1,
  "exam": 1,
  "status": "submitted",
  "score": 16.0,
  "total_marks": 20,
  "is_passed": true,
  "is_disqualified": false,
  "submitted_at": "2024-01-01T01:00:00Z"
}
```

---

### `GET /api/v1/exams/attempts/<id>/result/`
**Permission:** Student

Get detailed result with per-question breakdown (includes explanations and correct answers).

---

### `GET /api/v1/exams/attempts/`
**Permission:** Student

List all exam attempts by the current student. Paginated.

---

### Proctoring

### `POST /api/v1/exams/attempts/<id>/report-violation/`
**Permission:** Student

Report a proctoring violation during an active exam.

```json
{
  "violation_type": "tab_switch",
  "details": "Switched to another tab"
}
```

Violation types: `full_screen_exit`, `tab_switch`, `voice_detected`, `multi_face`, `extension_detected`.

Auto-disqualifies when `max_warnings` is reached.

**Response (201):**
```json
{
  "id": 1,
  "violation_type": "tab_switch",
  "warning_number": 2,
  "total_warnings": 2,
  "max_warnings": 3,
  "is_disqualified": false
}
```

---

### `GET /api/v1/exams/attempts/<id>/violations/`
**Permission:** Student

Get all proctoring violations for an attempt.

---

### Admin: Question, Option, Exam, Attempt CRUD
**Permission:** Admin

- `GET|POST /api/v1/exams/admin/questions/`
- `GET|PATCH|DELETE /api/v1/exams/admin/questions/<id>/`
- `GET|POST /api/v1/exams/admin/questions/<question_id>/options/`
- `GET|POST /api/v1/exams/admin/`
- `GET|PATCH|DELETE /api/v1/exams/admin/<id>/`
- `GET /api/v1/exams/admin/attempts/` (filterable by exam, status, is_passed, is_disqualified, exam__level)

---

## 5. Payments (Razorpay)

### `POST /api/v1/payments/initiate/`
**Permission:** Student

Create a Razorpay order for course purchase.

```json
{
  "course_id": 1
}
```

**Response (201):**
```json
{
  "order_id": "order_abc123",
  "amount": 99900,
  "currency": "INR",
  "key_id": "rzp_test_..."
}
```

---

### `POST /api/v1/payments/verify/`
**Permission:** Student

Verify Razorpay payment and activate purchase.

```json
{
  "razorpay_order_id": "order_abc123",
  "razorpay_payment_id": "pay_xyz789",
  "razorpay_signature": "..."
}
```

---

### `GET /api/v1/payments/purchases/`
**Permission:** Student

List the current student's purchases. Paginated.

---

### `GET /api/v1/payments/transactions/`
**Permission:** Student

List payment transactions. Paginated.

---

### Admin: `GET /api/v1/payments/admin/purchases/`
### Admin: `POST /api/v1/payments/admin/extend/`
**Permission:** Admin

List all purchases / extend purchase validity.

---

## 6. Progress

### `GET /api/v1/progress/dashboard/`
**Permission:** Student

Get student dashboard with current level, progress overview, and next recommended action.

**Response (200):**
```json
{
  "current_level": {"id": 1, "name": "Level 1", "order": 1},
  "level_progress": [...],
  "next_action": "attempt_exam",
  "message": "You are ready to take the Level 1 exam."
}
```

`next_action` values: `purchase_course`, `watch_sessions`, `submit_feedback`, `attempt_exam`, `all_complete`.

---

### `POST /api/v1/progress/sessions/<session_id>/`
**Permission:** Student

Update watch progress. Auto-completes at 90% if feedback is submitted.

```json
{
  "watched_seconds": 1500
}
```

---

### `GET /api/v1/progress/levels/<level_id>/sessions/`
**Permission:** Student

List session progress for a level.

---

### `GET /api/v1/progress/levels/`
**Permission:** Student

List level progress for all levels.

---

### `GET /api/v1/progress/calendar/?year=2024&month=6`
**Permission:** Student

Get activity calendar showing sessions watched and exams taken per day.

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
### `POST /api/v1/doubts/`
**Permission:** Student

List or create doubt tickets.

**Create request:**
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

Get doubt ticket details with replies.

---

### `POST /api/v1/doubts/<id>/reply/`
**Permission:** Student

Reply to a doubt ticket. Supports `attachment` file.

```json
{
  "message": "Thanks, I still have a question about..."
}
```

---

### Admin: Doubt management
**Permission:** Admin

- `GET /api/v1/doubts/admin/` — List all doubts
- `GET /api/v1/doubts/admin/<id>/` — Get doubt details
- `POST /api/v1/doubts/admin/<id>/reply/` — Reply to doubt
- `POST /api/v1/doubts/admin/<id>/assign/` — Assign to admin
- `POST /api/v1/doubts/admin/<id>/status/` — Update status
- `POST /api/v1/doubts/admin/<id>/bonus/` — Award bonus marks

---

## 8. Feedback

### `POST /api/v1/feedback/sessions/<session_id>/`
**Permission:** Student (requires active purchase for the session's level)

Submit mandatory session feedback (required for session completion). The student must have an active purchase for the course at the session's level.

```json
{
  "rating": 5,
  "difficulty_rating": 3,
  "clarity_rating": 4,
  "comment": "Great session!"
}
```
All ratings are 1-5. One feedback per session per student.

Returns `403 Forbidden` if the student has no active purchase:
```json
{
  "detail": "You must purchase a course for this level to submit feedback."
}
```

---

### `GET /api/v1/feedback/`
**Permission:** Student

List the current student's feedback submissions.

---

### Admin: `GET /api/v1/feedback/admin/`
**Permission:** Admin

List all feedback with filters.

---

## 9. Analytics (Admin)

### `GET /api/v1/analytics/revenue/?date=2024-01-01`
**Permission:** Admin

Get daily revenue aggregation. Filterable by `date`.

---

### `GET /api/v1/analytics/levels/?level=1&date=2024-01-01`
**Permission:** Admin

Get level-wise analytics (attempts, passes, failures, purchases, revenue, pass rate). Filterable by `level` and `date`.

---

## 10. Notifications

### `GET /api/v1/notifications/`
**Permission:** Authenticated

List notifications. Paginated.

---

### `PATCH /api/v1/notifications/<id>/read/`
**Permission:** Authenticated

Mark a single notification as read.

---

### `POST /api/v1/notifications/read-all/`
**Permission:** Authenticated

Mark all notifications as read.

---

### `DELETE /api/v1/notifications/clear-all/`
**Permission:** Authenticated

Delete all notifications for the current user.

---

### `GET /api/v1/notifications/unread-count/`
**Permission:** Authenticated

**Response:**
```json
{
  "unread_count": 3
}
```

---

## 11. Certificates

### `GET /api/v1/certificates/`
**Permission:** Student

List the current student's earned certificates.

---

### `GET /api/v1/certificates/<id>/`
**Permission:** Student

Get certificate details (certificate number, score, issue date).

---

### Admin: `GET /api/v1/certificates/admin/`
**Permission:** Admin

List all certificates.

---

## 12. Home

### `GET /api/v1/home/banners/`
**Permission:** Public

Get active banners for the home screen, ordered by `order`.

---

### `GET /api/v1/home/featured/`
**Permission:** Public

Get featured/active courses for the home screen.

---

### Admin: Banner CRUD
**Permission:** Admin

- `GET|POST /api/v1/home/admin/banners/`
- `GET|PATCH|DELETE /api/v1/home/admin/banners/<id>/`

---

## 13. Search

### `GET /api/v1/search/?q=keyword`
**Permission:** Authenticated

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

## Pagination

All list endpoints use page-based pagination:

```json
{
  "count": 42,
  "next": "http://host/api/v1/endpoint/?page=2",
  "previous": null,
  "results": [...]
}
```

Default page size: 20.

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

---

## Rate Limiting

| Scope | Limit |
|---|---|
| Anonymous requests | 30/min |
| Authenticated requests | 120/min |
| Login/Register/OTP | 5/min |
| Payment operations | 10/min |

---

## Interactive API Docs

- **Swagger UI:** `/api/docs/`
- **ReDoc:** `/api/redoc/`
- **OpenAPI Schema (JSON):** `/api/schema/`
