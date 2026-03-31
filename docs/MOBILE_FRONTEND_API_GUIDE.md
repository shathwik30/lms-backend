# Mobile App — Frontend API Integration Guide

> **Base URL:** `/api/v1/`
> **Auth:** After login, include `Authorization: Bearer <access_token>` in every request.
> **Role:** All student endpoints require `is_student=True` unless noted as `AllowAny`.

---

## Table of Contents

1. [Auth — Get Started / Landing](#1-auth--get-started--landing)
2. [Auth — Sign Up (Email)](#2-auth--sign-up-email)
3. [Auth — Sign Up (Phone + OTP)](#3-auth--sign-up-phone--otp)
4. [Auth — Login (Email + Password)](#4-auth--login-email--password)
5. [Auth — Login (Phone + OTP)](#5-auth--login-phone--otp)
6. [Auth — Google Sign In](#6-auth--google-sign-in)
7. [Auth — Forgot Password](#7-auth--forgot-password)
8. [Auth — Reset Password](#8-auth--reset-password)
9. [Auth — Change Password](#9-auth--change-password)
10. [Onboarding Carousel](#10-onboarding-carousel)
11. [Onboarding Assessment (Placement Exam)](#11-onboarding-assessment-placement-exam)
12. [Home Page](#12-home-page)
13. [Calendar](#13-calendar)
14. [Notifications](#14-notifications)
15. [Courses List](#15-courses-list)
16. [Course Detail / Tasks](#16-course-detail--tasks)
17. [Modules & Sessions](#17-modules--sessions)
18. [Video Session (Watch + Progress)](#18-video-session-watch--progress)
19. [Notes / Resource Session](#19-notes--resource-session)
20. [Session Feedback](#20-session-feedback)
21. [Exam Flow](#21-exam-flow)
22. [Exam Result](#22-exam-result)
23. [Doubts](#23-doubts)
24. [Payments & Checkout](#24-payments--checkout)
25. [Purchase History](#25-purchase-history)
26. [Profile Page](#26-profile-page)
27. [Account Settings](#27-account-settings)
28. [Report an Issue](#28-report-an-issue)
29. [Bookmarks](#29-bookmarks)
30. [Leaderboard](#30-leaderboard)
31. [Search](#31-search)
32. [Complete Endpoint Reference](#32-complete-endpoint-reference)

---

## 1. Auth — Get Started / Landing

Static UI screen. No API call. Show "Create Account" and "Already have an account? Sign in" buttons.

---

## 2. Auth — Sign Up (Email)

```
POST /api/v1/auth/register/
```

**Request:**
```json
{
  "full_name": "Aarav Sharma",
  "email": "aarav@gmail.com",
  "phone": "+919876543210",
  "password": "securepass123"
}
```

**Response (201):**
```json
{
  "id": 1,
  "email": "aarav@gmail.com",
  "full_name": "Aarav Sharma",
  "phone": "+919876543210"
}
```

After successful registration, auto-login by calling the login endpoint.

---

## 3. Auth — Sign Up (Phone + OTP)

**Step 1 — Send OTP:**
```
POST /api/v1/auth/otp/send/
```
```json
{ "email": "aarav@gmail.com", "purpose": "verify" }
```

**Response:** `{ "detail": "OTP sent successfully." }`

**Step 2 — Verify OTP:**
```
POST /api/v1/auth/otp/verify/
```
```json
{ "email": "aarav@gmail.com", "otp": "123456", "purpose": "verify" }
```

**Response:** `{ "detail": "OTP verified.", "verified": true }`

**Step 3 — Register** (same as Section 2).

OTP is 6 digits. 5-minute expiry. 60-second cooldown between sends. Max 5 attempts.

---

## 4. Auth — Login (Email + Password)

```
POST /api/v1/auth/login/
```

**Request:**
```json
{ "email": "aarav@gmail.com", "password": "securepass123" }
```

**Response (200):**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": {
    "id": 1,
    "email": "aarav@gmail.com",
    "full_name": "Aarav Sharma",
    "phone": "+919876543210",
    "profile_picture": "/media/users/avatars/pic.jpg",
    "is_student": true,
    "is_admin": false
  }
}
```

Store both tokens securely. Access token expires in 30 minutes. Refresh token expires in 7 days.

### Token Refresh

```
POST /api/v1/auth/token/refresh/
```
```json
{ "refresh": "eyJ..." }
```
**Response:** `{ "access": "eyJ..." }`

---

## 5. Auth — Login (Phone + OTP)

**Step 1:** `POST /api/v1/auth/otp/send/` with `{ "email": "...", "purpose": "verify" }`
**Step 2:** `POST /api/v1/auth/otp/verify/` with `{ "email": "...", "otp": "123456", "purpose": "verify" }`
**Step 3:** `POST /api/v1/auth/login/` with email + password.

> Note: The OTP flow in the design uses mobile number, but the backend OTP is email-based. The phone-number login screen sends OTP to the email associated with that phone number. The frontend should collect the phone number, then prompt for OTP sent to the linked email.

---

## 6. Auth — Google Sign In

```
POST /api/v1/auth/google/
```

**Request:**
```json
{ "id_token": "google_id_token_from_client_sdk" }
```

**Response (200 or 201):**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": { ... },
  "created": true
}
```

`created: true` means new account, `false` means existing user logged in.

---

## 7. Auth — Forgot Password

```
POST /api/v1/auth/password-reset/
```

**Request:**
```json
{ "email": "aarav@gmail.com" }
```

**Response:** `{ "detail": "Password reset link sent." }`

A reset link is emailed to the user. The link contains `uid` and `token` parameters.

---

## 8. Auth — Reset Password

```
POST /api/v1/auth/password-reset/confirm/
```

**Request:**
```json
{
  "uid": "MQ",
  "token": "abc123-def456",
  "new_password": "newsecurepass123"
}
```

**Response:** `{ "detail": "Password has been reset." }`

Extract `uid` and `token` from the deep link / reset URL.

---

## 9. Auth — Change Password

```
POST /api/v1/auth/change-password/
```

**Request:**
```json
{
  "old_password": "currentpass",
  "new_password": "newsecurepass123"
}
```

**Response:**
```json
{
  "detail": "Password changed successfully.",
  "refresh": "eyJ...",
  "access": "eyJ..."
}
```

New tokens are returned because all old sessions are invalidated. Replace stored tokens.

---

## 10. Onboarding Carousel

Static UI screens (3 pages). No API calls. After user taps "Start Level 1":

```
POST /api/v1/auth/onboarding/complete/
```

**Response:** `{ "detail": "Onboarding completed.", "is_onboarding_completed": true }`

---

## 11. Onboarding Assessment (Placement Exam)

### Step 1 — Get the onboarding exam

```
GET /api/v1/progress/dashboard/
```

**Response includes:**
```json
{
  "next_action": "take_onboarding_exam",
  "exam_id": 1,
  "message": "Take the placement exam to determine your level"
}
```

### Step 2 — Start the exam

```
POST /api/v1/exams/<exam_id>/start/
```

**Response (201):**
```json
{
  "id": 5,
  "exam": 1,
  "exam_title": "Placement Exam",
  "started_at": "2024-05-12T10:00:00Z",
  "submitted_at": null,
  "status": "in_progress",
  "score": null,
  "total_marks": 80,
  "is_passed": null,
  "is_disqualified": false,
  "questions": [
    {
      "id": 1,
      "question": {
        "id": 10,
        "text": "What is Newton's first law?",
        "image_url": "",
        "marks": 4,
        "question_type": "mcq",
        "options": [
          { "id": 1, "text": "An object at rest stays at rest", "image_url": "" },
          { "id": 2, "text": "F = ma", "image_url": "" },
          { "id": 3, "text": "Every action has a reaction", "image_url": "" },
          { "id": 4, "text": "Energy is conserved", "image_url": "" }
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

### Step 3 — Submit answers

```
POST /api/v1/exams/attempts/<attempt_id>/submit/
```

**Request:**
```json
{
  "answers": [
    { "question_id": 10, "option_id": 1 },
    { "question_id": 11, "option_id": 5 },
    { "question_id": 12, "option_ids": [8, 9] },
    { "question_id": 13, "text_answer": "9.8 m/s²" }
  ]
}
```

**Response:**
```json
{
  "id": 5,
  "exam": 1,
  "exam_title": "Placement Exam",
  "started_at": "2024-05-12T10:00:00Z",
  "submitted_at": "2024-05-12T10:15:00Z",
  "status": "submitted",
  "score": "58.00",
  "total_marks": 80,
  "is_passed": true,
  "is_disqualified": false
}
```

### Step 4 — Get result with per-level breakdown

```
GET /api/v1/exams/attempts/<attempt_id>/result/
```

**Response includes `questions[]` with level info:**
```json
{
  "id": 5,
  "questions": [
    {
      "id": 1,
      "question": 10,
      "question_text": "What is Newton's first law?",
      "question_type": "mcq",
      "question_level": 1,
      "question_level_name": "Foundation",
      "selected_option": 1,
      "selected_option_ids": [],
      "text_answer": "",
      "is_correct": true,
      "marks_awarded": "4.00",
      "order": 1,
      "explanation": "Newton's first law states...",
      "correct_text_answer": "",
      "correct_option_ids": [1]
    }
  ]
}
```

**To build the per-level score breakdown** (shown in design):
```javascript
// Group questions by level and calculate per-level score
const levelScores = {};
questions.forEach(q => {
  const key = q.question_level;
  if (!levelScores[key]) {
    levelScores[key] = { name: q.question_level_name, scored: 0, total: 0 };
  }
  levelScores[key].total += parseFloat(q.marks_awarded >= 0 ? /* question marks */ 4 : 0);
  levelScores[key].scored += parseFloat(q.marks_awarded);
});
```

---

## 12. Home Page

### Dashboard Data

```
GET /api/v1/progress/dashboard/
```

**Response:**
```json
{
  "current_level": {
    "id": 2,
    "name": "Intermediate"
  },
  "level_progress": {
    "status": "in_progress",
    "final_exam_attempts_used": 0
  },
  "course_progress": [
    { "course_id": 1, "course_title": "Physics", "status": "in_progress" }
  ],
  "next_action": "complete_courses",
  "message": "Complete all courses to unlock the final exam",
  "is_onboarding_exam_attempted": true,
  "exam_id": null
}
```

`next_action` values: `"take_onboarding_exam"`, `"purchase_level"`, `"complete_courses"`, `"take_final_exam"`, `"redo_level"`, `"all_complete"`, `"no_levels"`.

### Banners (Top carousel)

```
GET /api/v1/home/banners/
```

**Response:**
```json
[
  {
    "id": 1,
    "title": "New Course Launch",
    "subtitle": "Advanced Physics now available",
    "image_url": "https://storage.example.com/banner.jpg",
    "link_type": "course",
    "link_id": 5,
    "link_url": ""
  }
]
```

### Continue Learning section

Use dashboard `course_progress[]` to show current courses. For session-level "continue" data:

```
GET /api/v1/progress/levels/<level_id>/sessions/
```

Shows per-session progress. The first incomplete session is the "continue" target.

---

## 13. Calendar

```
GET /api/v1/progress/calendar/?year=2025&month=8
```

**Response:**
```json
{
  "year": 2025,
  "month": 8,
  "active_dates": [
    { "date": "2025-08-01", "sessions_watched": 3, "exams_taken": 0 },
    { "date": "2025-08-02", "sessions_watched": 1, "exams_taken": 1 }
  ]
}
```

Highlight dates with activity (green dots in design). Show streak count from dashboard or compute from consecutive active dates.

---

## 14. Notifications

### List

```
GET /api/v1/notifications/
```

**Query Params:** `?is_read=false`, `?notification_type=purchase`

**Response per notification:**
```json
{
  "id": 1,
  "title": "Purchase Confirmed",
  "message": "Your Level 2 access is now active",
  "notification_type": "purchase",
  "is_read": false,
  "data": { "level_id": 2 },
  "created_at": "2024-05-10T08:30:00Z"
}
```

`notification_type` values: `"purchase"`, `"exam_result"`, `"doubt_reply"`, `"level_unlock"`, `"course_expiry"`, `"general"`

### Mark as Read

```
PATCH /api/v1/notifications/<id>/read/
```

### Mark All as Read

```
POST /api/v1/notifications/read-all/
```

### Unread Badge Count

```
GET /api/v1/notifications/unread-count/
```
**Response:** `{ "unread_count": 5 }`

### Delete / Clear

```
DELETE /api/v1/notifications/<id>/
DELETE /api/v1/notifications/clear-all/
```

---

## 15. Courses List

### All Levels with progress

```
GET /api/v1/levels/
```

Returns all levels. To show lock/unlock state and progress per level:

```
GET /api/v1/progress/levels/
```

**Response:**
```json
[
  {
    "id": 1,
    "level": 1,
    "level_name": "Foundation",
    "level_order": 1,
    "status": "exam_passed",
    "started_at": "2024-01-15T10:00:00Z",
    "completed_at": "2024-03-10T10:00:00Z",
    "final_exam_attempts_used": 1
  },
  {
    "id": 2,
    "level": 2,
    "level_name": "Intermediate",
    "level_order": 2,
    "status": "in_progress",
    "started_at": "2024-03-15T10:00:00Z",
    "completed_at": null,
    "final_exam_attempts_used": 0
  }
]
```

`status` values: `"not_started"`, `"in_progress"`, `"syllabus_complete"`, `"exam_passed"`, `"exam_failed"`

| Design Element | Logic |
|---|---|
| Level completed (✓) | `status == "exam_passed"` |
| Currently learning | `status == "in_progress"` or `"syllabus_complete"` |
| Locked | No progress record or `not_started` without purchase |

### Courses for a Level (Tabs: COURSES / EXAMS)

```
GET /api/v1/courses/level/<level_id>/
```

**Response:** Array of `CourseSerializer` (id, level, title, description, is_active, weeks_count).

### Tasks for a Level (EXAMS tab)

```
GET /api/v1/progress/levels/<level_id>/courses/
```

Returns per-course progress. Also shows the level final exam from dashboard `exam_id`.

---

## 16. Course Detail / Tasks

### Course Progress

```
GET /api/v1/progress/courses/<course_id>/
```

**Response:**
```json
{
  "id": 1,
  "course": 1,
  "course_title": "Physics",
  "level_name": "Intermediate",
  "status": "in_progress",
  "started_at": "2024-03-15T10:00:00Z",
  "completed_at": null
}
```

---

## 17. Modules & Sessions

### Sessions for a Course

```
GET /api/v1/courses/<course_id>/sessions/
```

**Response per session:**
```json
{
  "id": 1,
  "week": 1,
  "title": "Introduction to Motion",
  "description": "...",
  "duration_seconds": 1800,
  "order": 1,
  "session_type": "video",
  "is_active": true
}
```

### Session Progress for Level

```
GET /api/v1/progress/levels/<level_id>/sessions/
```

**Response per session progress:**
```json
{
  "id": 1,
  "session": 5,
  "session_title": "Introduction to Motion",
  "total_duration": 1800,
  "watched_seconds": 1200,
  "is_completed": false,
  "completed_at": null,
  "is_exam_passed": null
}
```

| Design Element | Logic |
|---|---|
| Progress bar | `watched_seconds / total_duration * 100` |
| Completed (✓) | `is_completed == true` |
| Exam passed badge | `is_exam_passed == true` |

---

## 18. Video Session (Watch + Progress)

### Get Session Detail

```
GET /api/v1/courses/sessions/<session_id>/
```

**Response:**
```json
{
  "id": 1,
  "week": 1,
  "title": "Introduction to Motion",
  "description": "...",
  "video_url": "https://youtube.com/watch?v=abc123",
  "file_url": "",
  "resource_type": "",
  "markdown_content": "",
  "thumbnail_url": "https://storage.example.com/thumb.jpg",
  "duration_seconds": 1800,
  "order": 1,
  "session_type": "video",
  "exam": null,
  "is_active": true
}
```

### Update Watch Progress (send periodically while watching)

```
POST /api/v1/progress/sessions/<session_id>/
```

**Request:**
```json
{ "watched_seconds": 900 }
```

**Response:**
```json
{
  "id": 1,
  "session": 1,
  "session_title": "Introduction to Motion",
  "total_duration": 1800,
  "watched_seconds": 900,
  "is_completed": false,
  "completed_at": null,
  "is_exam_passed": null
}
```

Session auto-completes at 90% watch + feedback submitted.

---

## 19. Notes / Resource Session

### Get Session Detail (same endpoint)

```
GET /api/v1/courses/sessions/<session_id>/
```

For resource sessions: render `markdown_content` as rich text, show `file_url` as downloadable attachment.

### Mark Resource as Complete

```
POST /api/v1/courses/sessions/<session_id>/complete-resource/
```

**Response:** `{ "detail": "Session marked as completed." }`

---

## 20. Session Feedback

```
POST /api/v1/feedback/sessions/<session_id>/
```

**Request:**
```json
{
  "overall_rating": 4,
  "difficulty_rating": 3,
  "clarity_rating": 5,
  "comment": "Very clear explanation"
}
```

**Response (201):**
```json
{
  "id": 1,
  "session": 10,
  "session_title": "Introduction to Motion",
  "overall_rating": 4,
  "difficulty_rating": 3,
  "clarity_rating": 5,
  "comment": "Very clear explanation",
  "created_at": "2024-05-12T10:30:00Z"
}
```

Ratings are 1-5. Only `overall_rating` is required. Can only submit once per session.

---

## 21. Exam Flow

### Get Exam Info

```
GET /api/v1/exams/<exam_id>/
```

**Response:**
```json
{
  "id": 2,
  "level": 2,
  "level_name": "Intermediate",
  "exam_type": "level_final",
  "title": "Level 2 - Intermediate Exam",
  "duration_minutes": 60,
  "total_marks": 100,
  "passing_percentage": "65.00",
  "num_questions": 40,
  "pool_size": 80,
  "is_proctored": true,
  "max_warnings": 3,
  "is_active": true,
  "is_eligible": true
}
```

`is_eligible` tells whether the student can start this exam.

### Start Exam

```
POST /api/v1/exams/<exam_id>/start/
```

Returns `ExamAttemptDetailSerializer` with questions (same format as Section 11 Step 2).

### Submit Exam

```
POST /api/v1/exams/attempts/<attempt_id>/submit/
```

Same format as Section 11 Step 3.

### Report Proctoring Violation (during exam)

```
POST /api/v1/exams/attempts/<attempt_id>/report-violation/
```

**Request:**
```json
{ "violation_type": "tab_switch", "details": "User switched to another app" }
```

**Response (201):**
```json
{
  "id": 1,
  "attempt": 5,
  "violation_type": "tab_switch",
  "warning_number": 1,
  "details": "...",
  "created_at": "...",
  "total_warnings": 1,
  "max_warnings": 3,
  "is_disqualified": false
}
```

`violation_type` values: `"full_screen_exit"`, `"tab_switch"`, `"voice_detected"`, `"multi_face"`, `"extension_detected"`

When `is_disqualified` becomes `true`, end the exam immediately.

### Get Violations

```
GET /api/v1/exams/attempts/<attempt_id>/violations/
```

---

## 22. Exam Result

```
GET /api/v1/exams/attempts/<attempt_id>/result/
```

Same as Section 11 Step 4. Each question includes `question_level` and `question_level_name` to build per-level score breakdowns.

### Previous Attempts

```
GET /api/v1/exams/attempts/?exam=<exam_id>
```

---

## 23. Doubts

### List My Doubts

```
GET /api/v1/doubts/
```

**Response per doubt:**
```json
{
  "id": 1,
  "student": 5,
  "student_name": "Aarav Sharma",
  "title": "Projectile motion clarification",
  "status": "open",
  "context_type": "session",
  "level_name": "Intermediate",
  "course_name": "Physics",
  "created_at": "2024-05-10T08:30:00Z",
  "replies_count": 2
}
```

### Create Doubt

```
POST /api/v1/doubts/
```

**Request (multipart/form-data if screenshot):**
```json
{
  "title": "Projectile motion clarification",
  "description": "I am trying to calculate the maximum range...",
  "screenshot": "<file>",
  "context_type": "session",
  "session": 10
}
```

`context_type` values: `"session"`, `"topic"`, `"exam_question"`

### Doubt Detail

```
GET /api/v1/doubts/<doubt_id>/
```

Returns full detail with `replies[]`, `student_profile_picture`, `level_name`, `description`, `screenshot`.

### Reply to Doubt

```
POST /api/v1/doubts/<doubt_id>/reply/
```

**Request:**
```json
{ "message": "Here is more context...", "attachment": null }
```

### Empty States

| State | Text |
|---|---|
| No doubts | "No Doubts Found" |
| No student replies | "No Student Learn Boards" |
| No closed doubts | "No Closed Doubts" |

---

## 24. Payments & Checkout

### Proceed to Checkout Screen

Use the level detail to show what's included:

```
GET /api/v1/levels/<level_id>/
```

Shows courses, price, validity_days.

### Initiate Payment

```
POST /api/v1/payments/initiate/
```

**Request:**
```json
{ "level_id": 2 }
```

**Response (201):**
```json
{
  "transaction_id": 15,
  "razorpay_order_id": "order_abc123",
  "amount": "299900",
  "currency": "INR",
  "level_id": 2,
  "level_name": "Intermediate",
  "razorpay_key": "rzp_live_xxx"
}
```

`amount` is in **paise** (multiply display price by 100). Open Razorpay checkout with `razorpay_order_id`, `amount`, `razorpay_key`.

### Verify Payment (after Razorpay callback)

```
POST /api/v1/payments/verify/
```

**Request:**
```json
{
  "razorpay_order_id": "order_abc123",
  "razorpay_payment_id": "pay_xyz789",
  "razorpay_signature": "sig_..."
}
```

**Success Response (201):**
```json
{
  "id": 1,
  "level": 2,
  "level_name": "Intermediate",
  "amount_paid": "2999.00",
  "purchased_at": "2024-05-12T10:00:00Z",
  "expires_at": "2024-11-12T10:00:00Z",
  "status": "active",
  "is_valid": true,
  "extended_by_days": 0
}
```

**Error Response (400):**
```json
{ "detail": "Payment verification failed." }
```

Show "Payment Successful" or "Payment Failed" screen accordingly.

---

## 25. Purchase History

```
GET /api/v1/payments/purchases/
```

**Query Params:** `?level=<id>`, `?status=active|expired|revoked`

**Response per purchase:**
```json
{
  "id": 1,
  "level": 2,
  "level_name": "Intermediate",
  "amount_paid": "2999.00",
  "purchased_at": "2024-05-12T10:00:00Z",
  "expires_at": "2024-11-12T10:00:00Z",
  "status": "active",
  "is_valid": true,
  "extended_by_days": 0
}
```

| Design Element | API Field |
|---|---|
| Level Name | `level_name` |
| Price | `amount_paid` — format as ₹ |
| Status badge | `status` — `"active"`=Paid, `"expired"`=Expired, `"revoked"`=Completed |
| Purchase Date | `purchased_at` |
| Validity | `expires_at` |
| "View Details" | Navigate to level courses |

---

## 26. Profile Page

### Get Profile

```
GET /api/v1/auth/me/
```

**Response:**
```json
{
  "id": 1,
  "email": "aarav@gmail.com",
  "full_name": "Aarav Sharma",
  "phone": "+919876543210",
  "profile_picture": "/media/users/avatars/pic.jpg",
  "is_student": true,
  "is_admin": false,
  "student_profile": {
    "id": 1,
    "current_level": 2,
    "current_level_name": "Intermediate",
    "highest_cleared_level": 1,
    "highest_cleared_level_name": "Foundation",
    "gender": "male",
    "is_onboarding_completed": true,
    "is_onboarding_exam_attempted": true,
    "created_at": "2024-01-10T08:00:00Z"
  }
}
```

### Update Profile

```
PATCH /api/v1/auth/me/
```

**Request (multipart/form-data for picture):**
```json
{ "full_name": "Aryan Sharma", "phone": "+919876543211", "gender": "male" }
```

Or upload profile picture:
```
Content-Type: multipart/form-data
profile_picture: <file>
```

### Remove Profile Picture

```
DELETE /api/v1/auth/me/
```

### Course Roadmap Section

Use `GET /api/v1/progress/levels/` to build the level progression roadmap.

### Overall Progress

Use `GET /api/v1/progress/dashboard/` — `level_progress.status` and course completion from `course_progress[]`.

### Expired State

Check `GET /api/v1/payments/purchases/?status=active` — if empty or all expired, show "Level X Access Expired" with "Renew Level Access" button → navigate to payment.

---

## 27. Account Settings

### Get Preferences

```
GET /api/v1/auth/preferences/
```

**Response:**
```json
{
  "push_notifications": true,
  "email_notifications": true,
  "doubt_reply_notifications": true,
  "exam_result_notifications": true,
  "promotional_notifications": true,
  "payment_notifications": true,
  "issue_report_notifications": true,
  "feedback_reminder_notifications": true
}
```

### Update Preferences

```
PATCH /api/v1/auth/preferences/
```
```json
{ "push_notifications": false }
```

### Logout

```
POST /api/v1/auth/logout/
```
```json
{ "refresh": "eyJ..." }
```

Clear stored tokens. Navigate to login.

### Static Pages

Terms & Conditions, Privacy Policy, Refund & Cancellation Policy — render from static content or WebView. No API needed.

---

## 28. Report an Issue

```
POST /api/v1/auth/report-issue/
```

**Request (multipart/form-data if screenshot):**
```json
{
  "category": "bug",
  "subject": "Video not playing",
  "description": "The video for Projectile Motion is not loading on my phone...",
  "screenshot": "<file>",
  "device_info": "iPhone 13",
  "browser_info": "Safari 17",
  "os_info": "iOS 17.2"
}
```

`category` values: `"bug"`, `"content"`, `"payment"`, `"account"`, `"other"`

**Response (201):** Full `IssueReportSerializer` response.

### List My Issues

```
GET /api/v1/auth/my-issues/
```

Filter: `?category=bug`, `?is_resolved=true`

---

## 29. Bookmarks

### List Bookmarks

```
GET /api/v1/courses/bookmarks/
```

**Response per bookmark:**
```json
{
  "id": 1,
  "session": 10,
  "session_title": "Introduction to Motion",
  "session_week": 3,
  "created_at": "2024-05-10T08:30:00Z"
}
```

### Add Bookmark

```
POST /api/v1/courses/bookmarks/
```
```json
{ "session": 10 }
```

### Remove Bookmark

```
DELETE /api/v1/courses/bookmarks/<bookmark_id>/
```

---

## 30. Leaderboard

```
GET /api/v1/progress/leaderboard/
```

**Query Params:** `?level=<id>` (optional), `?limit=20` (default 20, max 50)

**Response:**
```json
{
  "leaderboard": [
    {
      "rank": 1,
      "student_id": 5,
      "full_name": "Aarav Sharma",
      "profile_picture": "/media/users/avatars/pic.jpg",
      "levels_cleared": 3,
      "total_score": 450,
      "exams_passed": 8
    }
  ],
  "my_rank": 12
}
```

---

## 31. Search

```
GET /api/v1/search/?q=motion
```

**Query Params:** `?q=<query>` (min 2 chars), `?level=<id>`, `?week=<id>`

**Response:**
```json
{
  "levels": [...],
  "courses": [...],
  "sessions": [...],
  "questions_count": 15
}
```

---

## 32. Complete Endpoint Reference

| Method | Endpoint | Auth | Section |
|---|---|---|---|
| `POST` | `/auth/register/` | No | [2](#2-auth--sign-up-email) |
| `POST` | `/auth/login/` | No | [4](#4-auth--login-email--password) |
| `POST` | `/auth/google/` | No | [6](#6-auth--google-sign-in) |
| `POST` | `/auth/logout/` | Yes | [27](#27-account-settings) |
| `POST` | `/auth/token/refresh/` | No | [4](#4-auth--login-email--password) |
| `GET/PATCH` | `/auth/me/` | Yes | [26](#26-profile-page) |
| `DELETE` | `/auth/me/` | Yes | [26](#26-profile-page) |
| `POST` | `/auth/change-password/` | Yes | [9](#9-auth--change-password) |
| `POST` | `/auth/password-reset/` | No | [7](#7-auth--forgot-password) |
| `POST` | `/auth/password-reset/confirm/` | No | [8](#8-auth--reset-password) |
| `POST` | `/auth/otp/send/` | No | [3](#3-auth--sign-up-phone--otp) |
| `POST` | `/auth/otp/verify/` | No | [3](#3-auth--sign-up-phone--otp) |
| `POST` | `/auth/onboarding/complete/` | Yes | [10](#10-onboarding-carousel) |
| `GET/PATCH` | `/auth/preferences/` | Yes | [27](#27-account-settings) |
| `POST` | `/auth/report-issue/` | Yes | [28](#28-report-an-issue) |
| `GET` | `/auth/my-issues/` | Yes | [28](#28-report-an-issue) |
| `GET` | `/levels/` | No | [15](#15-courses-list) |
| `GET` | `/levels/<id>/` | No | [24](#24-payments--checkout) |
| `GET` | `/courses/level/<level_id>/` | Yes | [15](#15-courses-list) |
| `GET` | `/courses/<course_id>/sessions/` | Yes | [17](#17-modules--sessions) |
| `GET` | `/courses/sessions/<id>/` | Yes | [18](#18-video-session-watch--progress) |
| `POST` | `/courses/sessions/<id>/complete-resource/` | Yes | [19](#19-notes--resource-session) |
| `GET/POST` | `/courses/bookmarks/` | Yes | [29](#29-bookmarks) |
| `DELETE` | `/courses/bookmarks/<id>/` | Yes | [29](#29-bookmarks) |
| `GET` | `/exams/<id>/` | Yes | [21](#21-exam-flow) |
| `POST` | `/exams/<id>/start/` | Yes | [21](#21-exam-flow) |
| `POST` | `/exams/attempts/<id>/submit/` | Yes | [21](#21-exam-flow) |
| `GET` | `/exams/attempts/<id>/result/` | Yes | [22](#22-exam-result) |
| `GET` | `/exams/attempts/` | Yes | [22](#22-exam-result) |
| `POST` | `/exams/attempts/<id>/report-violation/` | Yes | [21](#21-exam-flow) |
| `GET` | `/exams/attempts/<id>/violations/` | Yes | [21](#21-exam-flow) |
| `POST` | `/payments/initiate/` | Yes | [24](#24-payments--checkout) |
| `POST` | `/payments/verify/` | Yes | [24](#24-payments--checkout) |
| `GET` | `/payments/purchases/` | Yes | [25](#25-purchase-history) |
| `GET` | `/payments/transactions/` | Yes | [25](#25-purchase-history) |
| `GET` | `/progress/dashboard/` | Yes | [12](#12-home-page) |
| `POST` | `/progress/sessions/<session_id>/` | Yes | [18](#18-video-session-watch--progress) |
| `GET` | `/progress/levels/<level_id>/sessions/` | Yes | [17](#17-modules--sessions) |
| `GET` | `/progress/levels/` | Yes | [15](#15-courses-list) |
| `GET` | `/progress/courses/<course_id>/` | Yes | [16](#16-course-detail--tasks) |
| `GET` | `/progress/levels/<level_id>/courses/` | Yes | [16](#16-course-detail--tasks) |
| `GET` | `/progress/calendar/` | Yes | [13](#13-calendar) |
| `GET` | `/progress/leaderboard/` | Yes | [30](#30-leaderboard) |
| `GET/POST` | `/doubts/` | Yes | [23](#23-doubts) |
| `GET` | `/doubts/<id>/` | Yes | [23](#23-doubts) |
| `POST` | `/doubts/<id>/reply/` | Yes | [23](#23-doubts) |
| `POST` | `/feedback/sessions/<session_id>/` | Yes | [20](#20-session-feedback) |
| `GET` | `/feedback/` | Yes | [20](#20-session-feedback) |
| `GET` | `/notifications/` | Yes | [14](#14-notifications) |
| `PATCH` | `/notifications/<id>/read/` | Yes | [14](#14-notifications) |
| `POST` | `/notifications/read-all/` | Yes | [14](#14-notifications) |
| `DELETE` | `/notifications/<id>/` | Yes | [14](#14-notifications) |
| `DELETE` | `/notifications/clear-all/` | Yes | [14](#14-notifications) |
| `GET` | `/notifications/unread-count/` | Yes | [14](#14-notifications) |
| `GET` | `/home/banners/` | No | [12](#12-home-page) |
| `GET` | `/home/featured/` | No | [12](#12-home-page) |
| `GET` | `/search/?q=<query>` | Yes | [31](#31-search) |

---

## Pagination

Paginated responses follow:
```json
{ "count": 100, "next": "...?page=2", "previous": null, "results": [...] }
```

Student lists use **SmallPagination** (10 per page, max 50). Override with `?page_size=20`.

## Error Format

```json
{ "detail": "Error message." }
```

Validation:
```json
{ "email": ["This field is required."], "password": ["Ensure this field has at least 8 characters."] }
```

| Code | Meaning |
|---|---|
| `200` | Success |
| `201` | Created |
| `204` | Deleted |
| `400` | Validation / bad request |
| `401` | Token expired — refresh or re-login |
| `402` | Purchase required |
| `403` | Not authorized / syllabus incomplete / level locked |
| `404` | Not found |
| `429` | Rate limited |

## Rate Limits

| Scope | Limit |
|---|---|
| Login / Register / OTP | 5/min |
| Authenticated requests | 120/min |
| Exam submit | 30/hour |
| Search | 60/min |
| Doubt create | 10/min |
| Feedback | 20/min |
| Payment | 10/min |
| Progress update | 120/min |
