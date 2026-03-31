# Admin Dashboard — Frontend API Integration Guide

> **Base URL:** `/api/v1/`
> **Auth:** Every request needs `Authorization: Bearer <access_token>` header.
> **Role:** All `/admin/` endpoints require the user to have `is_admin=True`. A `403` is returned otherwise.

> **Terminology Mapping (Design → Backend):**
>
> | Design Term | Backend Model | Example |
> |---|---|---|
> | Subject | Course | "Physics", "Chemistry" |
> | Module | Week | "Mechanics", "Thermodynamics" |
> | Topic | Session | "Introduction to Motion" |
> | Unit | Session content | `video_url`, `file_url`, `markdown_content` |

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Dashboard](#2-dashboard)
3. [Student Management](#3-student-management)
4. [Student Details](#4-student-details)
5. [Course Management (Levels)](#5-course-management-levels)
6. [Curriculum Subjects (Courses)](#6-curriculum-subjects-courses)
7. [Curriculum Builder (Modules/Weeks)](#7-curriculum-builder-modulesweeks)
8. [Topic Content (Sessions)](#8-topic-content-sessions)
9. [Add Video Lecture](#9-add-video-lecture)
10. [Add Notes](#10-add-notes)
11. [Add Practice Questions](#11-add-practice-questions)
12. [Exam Management (Level Exams)](#12-exam-management-level-exams)
13. [Create Level Exam](#13-create-level-exam)
14. [Exam Analytics](#14-exam-analytics)
15. [Doubts Management](#15-doubts-management)
16. [Doubt Conversation](#16-doubt-conversation)
17. [Feedback](#17-feedback)
18. [Payments](#18-payments)
19. [Reports (Issue Reports)](#19-reports-issue-reports)
20. [Report Detail](#20-report-detail)
21. [Level Analytics](#21-level-analytics)
22. [Settings](#22-settings)
23. [Delete Confirmation Modal](#23-delete-confirmation-modal)
24. [Banners (Home)](#24-banners-home)
25. [Notifications](#25-notifications)
26. [Pagination & Errors](#26-pagination--errors)

---

## 1. Authentication

### Login

```
POST /api/v1/auth/login/
```

**Request:**
```json
{ "email": "admin@think.com", "password": "yourpassword" }
```

**Response (200):**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

Store both tokens. Include access token in every request:
```
Authorization: Bearer <access_token>
```

### Token Refresh

```
POST /api/v1/auth/token/refresh/
```

**Request:** `{ "refresh": "eyJ..." }`
**Response:** `{ "access": "eyJ..." }`

Call this when you get a `401`. If refresh also fails → redirect to login.

### Logout

```
POST /api/v1/auth/logout/
```

**Request:** `{ "refresh": "eyJ..." }`

### Get Current Admin Profile (Sidebar)

```
GET /api/v1/auth/me/
```

**Response:**
```json
{
  "id": 1,
  "email": "admin@think.com",
  "full_name": "Admin User",
  "phone": "+919876543210",
  "profile_picture": "/media/users/avatars/pic.jpg",
  "is_student": false,
  "is_admin": true
}
```

---

## 2. Dashboard

```
GET /api/v1/analytics/dashboard/
```

**Response:**
```json
{
  "total_students": 5320,
  "total_revenue": "184500.00",
  "active_users": 9,
  "exams_passed_today": 27,
  "open_doubts": 62,
  "daily_active_users": [
    { "date": "2024-03-01", "count": 45 },
    { "date": "2024-03-02", "count": 52 }
  ],
  "streak_retention": {
    "0_days": 120,
    "1_3_days": 340,
    "4_7_days": 210,
    "8_plus_days": 150
  },
  "recent_doubts": [
    {
      "id": 1,
      "student_name": "Aarav Sharma",
      "title": "Projectile motion doubt",
      "status": "open",
      "context_type": "session",
      "created_at": "2024-05-12T10:00:00Z"
    }
  ]
}
```

| Design Label | API Field | Notes |
|---|---|---|
| Total Students | `total_students` | |
| Total Revenue | `total_revenue` | String — parse to number, format as ₹ |
| Active Users | `active_users` | 7-day active. Use this for the "Unique Logins" card |
| Exams Passed | `exams_passed_today` | Today only |
| Daily Active Users chart | `daily_active_users[]` | x=`date`, y=`count`. Last 30 days |
| Streak Retention donut | `streak_retention` | 4 keys. Calculate % on frontend |
| Recent Doubts | `recent_doubts[]` | Up to 10 items |
| "View All Tickets" | Navigate to `/admin/doubts` | |

---

## 3. Student Management

```
GET /api/v1/auth/admin/students/
```

**Query Params:**

| Param | Type | Values | Example |
|---|---|---|---|
| `current_level` | int | Level ID | `?current_level=2` |
| `validity` | string | `active`, `expired`, `none` | `?validity=active` |
| `account_status` | string | `active`, `inactive` | `?account_status=active` |
| `search` | string | Name or email | `?search=aarav` |
| `page` | int | | `?page=2` |
| `page_size` | int | Max 200 | `?page_size=50` |

**Response:**
```json
{
  "count": 523,
  "next": "...?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "user": {
        "id": 10,
        "email": "aarav@gmail.com",
        "full_name": "Aarav Sharma",
        "phone": "+919876543210",
        "profile_picture": "/media/users/avatars/pic.jpg",
        "is_student": true,
        "is_admin": false
      },
      "current_level": 2,
      "current_level_name": "Intermediate",
      "highest_cleared_level": 1,
      "highest_cleared_level_name": "Foundation",
      "gender": "male",
      "is_onboarding_completed": true,
      "is_onboarding_exam_attempted": true,
      "validity_till": "2024-12-15T00:00:00Z",
      "exam_status": "passed",
      "streak": 14,
      "last_active": "2024-05-12T10:24:00Z",
      "account_status": "active",
      "created_at": "2024-01-10T08:00:00Z"
    }
  ]
}
```

| Design Column | API Field | Notes |
|---|---|---|
| Profile pic | `user.profile_picture` | Can be `null` or `""` |
| Student Name | `user.full_name` | |
| Current Level | `current_level_name` | |
| Days Left | Compute from `validity_till` | `Math.max(0, Math.ceil((new Date(validity_till) - Date.now()) / 86400000))`. Show "N/A" if `null` |
| Exam Status | `exam_status` | `"not_attempted"` / `"passed"` / `"in_progress"` / `"failed"` |
| Streak | `streak` | Integer days |
| Last Active | `last_active` | Format as relative time. Can be `null` |
| Account Status | `account_status` | `"active"` / `"inactive"` |
| Level filter dropdown | `?current_level=<id>` | Populate from `GET /api/v1/levels/admin/` |
| Validity filter | `?validity=active\|expired\|none` | |
| Account Status filter | `?account_status=active\|inactive` | |

---

## 4. Student Details

```
GET /api/v1/auth/admin/students/<student_profile_id>/
```

**Response:**
```json
{
  "id": 1,
  "user": {
    "id": 10,
    "email": "aarav@gmail.com",
    "full_name": "Aarav Sharma",
    "phone": "+919876543210",
    "profile_picture": "/media/users/avatars/pic.jpg",
    "is_student": true,
    "is_admin": false
  },
  "current_level": 2,
  "current_level_name": "Intermediate",
  "highest_cleared_level": 1,
  "highest_cleared_level_name": "Foundation",
  "gender": "male",
  "is_onboarding_completed": true,
  "is_onboarding_exam_attempted": true,
  "account_status": "active",
  "validity_till": "2024-12-15T00:00:00+05:30",
  "days_remaining": 215,
  "curriculum_progress": {
    "overall_completion": 45.5,
    "video_completion": 60.0,
    "practice_completion": 25.0,
    "feedback_submitted": 80.0
  },
  "exam_history": [
    {
      "id": 5,
      "exam_title": "Level 2 Final Exam",
      "score": "67.00",
      "total_marks": 100,
      "is_passed": true,
      "started_at": "2024-05-10T10:00:00Z",
      "attempt_number": 2
    }
  ],
  "created_at": "2024-01-10T08:00:00Z"
}
```

| Design Element | API Field | Notes |
|---|---|---|
| Account Status badges (Active/Expired/At Risk) | `account_status` + `days_remaining` | `"active"` with `days_remaining < 30` = "At Risk" |
| Profile Overview | `user.email`, `user.phone`, `current_level_name` | |
| Validity | `validity_till` | `null` if no purchase |
| Days Remaining | `days_remaining` | `null` if no purchase, `0` if expired |
| Curriculum Progress | `curriculum_progress` | All values are percentages (0-100). `null` if no current_level |
| Exam History table | `exam_history[]` | Last 10 attempts. `score` is string, parse to float |

### Management Console Actions

**Extend Validity:**
```
POST /api/v1/payments/admin/extend/
```
```json
{ "purchase_id": 45, "extra_days": 30 }
```

**Update Level / Reset Attempts / Manually Mark Passed:**
```
PATCH /api/v1/auth/admin/students/<student_profile_id>/
```
```json
{
  "current_level": 3,
  "highest_cleared_level": 2
}
```

---

## 5. Course Management (Levels)

### List All Levels

```
GET /api/v1/levels/admin/
```

No pagination — returns all levels.

**Response:**
```json
[
  {
    "id": 1,
    "name": "Foundation",
    "order": 1,
    "description": "...",
    "is_active": true,
    "passing_percentage": "65.00",
    "price": "1999.00",
    "validity_days": 180,
    "max_final_exam_attempts": 3,
    "students_enrolled": 432,
    "courses": [
      { "id": 1, "title": "Physics", "description": "...", "is_active": true, "weeks_count": 5 }
    ],
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

| Design Column | API Field | Notes |
|---|---|---|
| Level Name | Format: `Level {order} - {name}` | |
| Subjects | `courses.length` | Count of courses |
| Students Enrolled | `students_enrolled` | Active purchases for this level |
| Price | `price` | Format as ₹ |
| Status | `is_active` | `true`=Active, `false`=Draft |

### Create Level

```
POST /api/v1/levels/admin/
```
```json
{
  "name": "Proficient",
  "order": 5,
  "description": "...",
  "is_active": false,
  "passing_percentage": "70.00",
  "price": "3499.00",
  "validity_days": 365,
  "max_final_exam_attempts": 3
}
```

### Update Level

```
PATCH /api/v1/levels/admin/<level_id>/
```

### Delete Level

```
DELETE /api/v1/levels/admin/<level_id>/
```
Returns `204 No Content`.

---

## 6. Curriculum Subjects (Courses)

### List Courses for a Level

```
GET /api/v1/courses/admin/?level=<level_id>
```

**Response:**
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "level": 2,
      "level_name": "Intermediate",
      "title": "Physics",
      "description": "...",
      "is_active": true,
      "weeks_count": 5,
      "price": "2999.00",
      "students_enrolled": 287,
      "exam_linked": ["Level 2 Final Exam"],
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

| Design Element | API Field |
|---|---|
| Subject name | `title` |
| Status badge | `is_active` |
| Module count | `weeks_count` |
| Students | `students_enrolled` |

### Create Course

```
POST /api/v1/courses/admin/
```
```json
{ "level": 2, "title": "Biology", "description": "...", "is_active": true }
```

### Update / Delete Course

```
PATCH /api/v1/courses/admin/<course_id>/
DELETE /api/v1/courses/admin/<course_id>/
```

---

## 7. Curriculum Builder (Modules/Weeks)

### List Modules for a Course

```
GET /api/v1/courses/admin/<course_id>/weeks/
```

No pagination — returns all weeks.

**Response:**
```json
[
  {
    "id": 1,
    "course": 1,
    "name": "Mechanics",
    "order": 1,
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### Create Module

```
POST /api/v1/courses/admin/<course_id>/weeks/
```
```json
{ "name": "Thermodynamics", "order": 3, "is_active": true }
```

### Update / Delete Module

```
PATCH /api/v1/courses/admin/weeks/<week_id>/
DELETE /api/v1/courses/admin/weeks/<week_id>/
```

### List Topics in a Module

```
GET /api/v1/courses/admin/sessions/?week=<week_id>
```

Additional filters: `?is_active=true`, `?session_type=video`

---

## 8. Topic Content (Sessions)

```
GET /api/v1/courses/admin/sessions/?week=<week_id>
```

**Response per session:**
```json
{
  "id": 1,
  "week": 1,
  "title": "Introduction to Motion",
  "description": "...",
  "video_url": "https://youtube.com/...",
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

| Design Element | API Field | Notes |
|---|---|---|
| Title | `title` | |
| Type badge | `session_type` | `"video"` → Video Content, `"resource"` → Reading Material, `"practice_exam"` → Practice Quiz, `"proctored_exam"` → Proctored Exam |
| Duration | `duration_seconds` | Format: `Math.floor(duration/60)` mins |
| Thumbnail | `thumbnail_url` | Can be `""` |

### Create Session

```
POST /api/v1/courses/admin/sessions/
```

### Update / Delete Session

```
PATCH /api/v1/courses/admin/sessions/<session_id>/
DELETE /api/v1/courses/admin/sessions/<session_id>/
```

---

## 9. Add Video Lecture

```
POST /api/v1/courses/admin/sessions/
```

**Request:**
```json
{
  "week": 1,
  "title": "Introduction to Motion",
  "description": "Detailed lecture on motion concepts",
  "session_type": "video",
  "video_url": "https://youtube.com/watch?v=abc123",
  "thumbnail_url": "https://storage.example.com/thumb.jpg",
  "duration_seconds": 1800,
  "order": 1,
  "is_active": true
}
```

| Design Field | API Field | Required |
|---|---|---|
| Video Title | `title` | Yes |
| Video Description | `description` | No |
| Video Preview Thumbnail | `thumbnail_url` | No |
| Video Content (YouTube link) | `video_url` | No |
| Duration | `duration_seconds` | No (default 0) |
| Enabled toggle | `is_active` | No (default true) |

---

## 10. Add Notes

```
POST /api/v1/courses/admin/sessions/
```

**Request:**
```json
{
  "week": 1,
  "title": "Motion Formula Notes",
  "description": "Study material for motion formulas",
  "session_type": "resource",
  "resource_type": "pdf",
  "markdown_content": "<p>Rich text content here</p>",
  "file_url": "https://storage.example.com/notes.pdf",
  "order": 2,
  "is_active": true
}
```

| Design Field | API Field |
|---|---|
| Notes Title | `title` |
| Rich text content | `markdown_content` |
| Attachments (PDF) | `file_url` |
| Resource type | `resource_type` — `"pdf"`, `"note"`, `"markdown"` |

---

## 11. Add Practice Questions

Multi-step process:

**Step 1 — Create exam:**
```
POST /api/v1/exams/admin/
```
```json
{
  "level": 2,
  "week": 1,
  "course": 1,
  "exam_type": "weekly",
  "title": "Motion Quiz",
  "duration_minutes": 15,
  "total_marks": 40,
  "passing_percentage": "50.00",
  "num_questions": 10,
  "is_proctored": false,
  "is_active": true
}
```

**Step 2 — Create session linking to exam:**
```
POST /api/v1/courses/admin/sessions/
```
```json
{
  "week": 1,
  "title": "Motion Quiz",
  "session_type": "practice_exam",
  "exam": 5,
  "order": 3,
  "is_active": true
}
```

**Step 3 — Add questions:**
```
POST /api/v1/exams/admin/questions/
```
```json
{
  "exam": 5,
  "text": "What is Newton's first law?",
  "question_type": "mcq",
  "difficulty": "medium",
  "marks": 4,
  "negative_marks": "1.00",
  "explanation": "Newton's first law states...",
  "is_active": true
}
```

`question_type` values: `"mcq"` (Single Choice), `"multi_mcq"` (Multiple Choice), `"fill_blank"` (Fill in Blank).
`difficulty` values: `"easy"`, `"medium"`, `"hard"`.
`level` is auto-set from the exam's level if omitted.

**Step 4 — Add options per question:**
```
POST /api/v1/exams/admin/questions/<question_id>/options/
```
```json
{ "text": "An object at rest stays at rest", "is_correct": true }
```

Repeat for each option (typically 4).

**List options:**
```
GET /api/v1/exams/admin/questions/<question_id>/options/
```

**Update/Delete option:**
```
PATCH /api/v1/exams/admin/options/<option_id>/
DELETE /api/v1/exams/admin/options/<option_id>/
```

**Update/Delete question:**
```
PATCH /api/v1/exams/admin/questions/<question_id>/
DELETE /api/v1/exams/admin/questions/<question_id>/
```

**List questions (with filters):**
```
GET /api/v1/exams/admin/questions/?exam=5&difficulty=medium&question_type=mcq&is_active=true
```

---

## 12. Exam Management (Level Exams)

```
GET /api/v1/exams/admin/?exam_type=level_final
```

Additional filters: `?level=<id>`, `?is_active=true`

**Response per exam:**
```json
{
  "id": 1,
  "level": 1,
  "level_name": "Foundation",
  "week": null,
  "week_name": null,
  "course": null,
  "course_title": null,
  "exam_type": "level_final",
  "title": "Level 1 Final Exam",
  "duration_minutes": 45,
  "total_marks": 100,
  "passing_percentage": "65.00",
  "num_questions": 30,
  "pool_size": 50,
  "is_proctored": true,
  "max_warnings": 3,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "subjects_included": ["Physics", "Chemistry", "Mathematics"]
}
```

| Design Column | API Field |
|---|---|
| Level Name | `level_name` |
| Subjects Included | `subjects_included` — join with ", " |
| Exam Status | `is_active` — `true`=Active, `false`=Draft |
| Duration | `duration_minutes` — format as "45 mins" |
| Questions | `num_questions` (selected from pool of `pool_size`) |

---

## 13. Create Level Exam

```
POST /api/v1/exams/admin/
```

**Request:**
```json
{
  "level": 2,
  "exam_type": "level_final",
  "title": "Level 2 Final Exam",
  "duration_minutes": 60,
  "total_marks": 100,
  "passing_percentage": "65.00",
  "num_questions": 40,
  "is_proctored": true,
  "max_warnings": 3,
  "is_active": true
}
```

| Design Field | API Field | Notes |
|---|---|---|
| Select Level | `level` | Level ID |
| Subject Area checkboxes | — | Cosmetic — subjects are determined by which questions are added to the exam |
| Exam Title | `title` | |
| Duration | `duration_minutes` | |
| Pass % | `passing_percentage` | |
| Attempt Limit | Update the Level: `PATCH /api/v1/levels/admin/<id>/` with `max_final_exam_attempts` | |
| Fullscreen Mode | `is_proctored` | |
| Tab Switching Detection | `is_proctored` + `max_warnings` | |

**Update / Delete Exam:**
```
PATCH /api/v1/exams/admin/<exam_id>/
DELETE /api/v1/exams/admin/<exam_id>/
```

---

## 14. Exam Analytics

### Stats Cards

```
GET /api/v1/exams/admin/<exam_id>/stats/
```

**Response:**
```json
{
  "total_attempts": 158,
  "pass_rate": 71.52,
  "average_score": 74.30,
  "total_violations": 12
}
```

`pass_rate` and `average_score` are `null` if no attempts.

### Student Results Table

```
GET /api/v1/exams/admin/attempts/?exam=<exam_id>
```

Additional filters: `?status=submitted`, `?is_passed=true`, `?is_disqualified=false`, `?exam__level=<id>`

**Response per attempt:**
```json
{
  "id": 1,
  "exam": 2,
  "exam_title": "Level 2 Final Exam",
  "student": 5,
  "student_name": "Aarav Sharma",
  "student_profile_picture": "/media/users/avatars/pic.jpg",
  "started_at": "2024-05-12T10:00:00Z",
  "submitted_at": "2024-05-12T10:45:00Z",
  "status": "submitted",
  "score": "67.00",
  "total_marks": 100,
  "is_passed": true,
  "is_disqualified": false,
  "violations_count": 0,
  "attempt_number": 1
}
```

| Design Column | API Field |
|---|---|
| Student Name | `student_name` |
| Score | `score` / `total_marks` — format as % |
| Result | `is_passed` — `true`=Pass, `false`=Fail |
| Attempt # | `attempt_number` |
| Violations | `violations_count` |
| Date | `started_at` |

---

## 15. Doubts Management

```
GET /api/v1/doubts/admin/
```

**Query Params:**

| Param | Values | Example |
|---|---|---|
| `status` | `open`, `in_review`, `answered`, `closed` | `?status=open` |
| `context_type` | `session`, `topic`, `exam_question` | `?context_type=session` |
| `assigned_to` | Admin user ID | `?assigned_to=5` |
| `search` | Title or student email | `?search=projectile` |

**Response per ticket:**
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

| Design Column | API Field | Notes |
|---|---|---|
| Ticket ID | `id` | Format: `` `SUP-${String(id).padStart(3, '0')}` `` |
| Student Name | `student_name` | |
| Subject | `course_name` | |
| Level | `level_name` | |
| Status | `status` | |
| Tab: All | No status filter | |
| Tab: Open | `?status=open` | |
| Tab: Resolved | `?status=answered` | |
| Tab: Rejected | `?status=closed` | Map to closed |
| Tab: Closed | `?status=closed` | |

---

## 16. Doubt Conversation

### Get Detail

```
GET /api/v1/doubts/admin/<doubt_id>/
```

**Response:**
```json
{
  "id": 1,
  "student": 5,
  "student_name": "Aarav Sharma",
  "student_profile_picture": "/media/users/avatars/pic.jpg",
  "title": "Projectile motion clarification",
  "description": "I am trying to calculate the maximum range...",
  "screenshot": "/media/doubts/screenshots/img.jpg",
  "status": "open",
  "context_type": "session",
  "session": 10,
  "exam_question": null,
  "assigned_to": null,
  "assigned_to_name": null,
  "bonus_marks": null,
  "level_name": "Intermediate",
  "created_at": "2024-05-10T08:30:00Z",
  "updated_at": "2024-05-10T08:30:00Z",
  "replies": [
    {
      "id": 1,
      "ticket": 1,
      "author": 10,
      "author_name": "Aarav Sharma",
      "author_role": "student",
      "message": "Here is my work so far...",
      "attachment": "/media/doubts/attachments/notes.pdf",
      "created_at": "2024-05-10T08:31:00Z"
    }
  ]
}
```

| Design Element | API Field |
|---|---|
| Student pic (header) | `student_profile_picture` |
| Student name | `student_name` |
| Level badge | `level_name` |
| Status badge | `status` |
| Original message | `description` |
| Attachments | `screenshot` + reply `attachment` |
| Replies | `replies[]` — use `author_role` to style student vs admin |

### Send Reply

```
POST /api/v1/doubts/admin/<doubt_id>/reply/
```

**Request** (multipart/form-data if attachment):
```json
{ "message": "Great question! For projectile motion...", "attachment": null }
```

### Close Doubt

```
PATCH /api/v1/doubts/admin/<doubt_id>/status/
```
```json
{ "status": "closed" }
```

### Assign to Admin

```
PATCH /api/v1/doubts/admin/<doubt_id>/assign/
```
```json
{ "assigned_to": 3 }
```

### Award Bonus Marks

```
PATCH /api/v1/doubts/admin/<doubt_id>/bonus/
```
```json
{ "bonus_marks": "5.00" }
```

---

## 17. Feedback

```
GET /api/v1/feedback/admin/
```

**Query Params:**

| Param | Example | Notes |
|---|---|---|
| `overall_rating` | `?overall_rating=5` | Filter by 1-5 stars |
| `difficulty_rating` | `?difficulty_rating=3` | |
| `clarity_rating` | `?clarity_rating=4` | |
| `session` | `?session=10` | Specific lecture |
| `session__week__course` | `?session__week__course=1` | Filter by Subject |
| `session__week__course__level` | `?session__week__course__level=2` | Filter by Level |
| `search` | `?search=aarav@gmail.com` | By student email |

**Response per feedback:**
```json
{
  "id": 1,
  "student": 5,
  "student_name": "Aarav Sharma",
  "session": 10,
  "session_title": "Motion in One Dimension",
  "level_name": "Intermediate",
  "subject_name": "Physics",
  "overall_rating": 4,
  "difficulty_rating": 3,
  "clarity_rating": 5,
  "comment": "Very clear explanation...",
  "created_at": "2024-05-10T08:30:00Z"
}
```

| Design Column | API Field |
|---|---|
| Student Name | `student_name` |
| Level | `level_name` |
| Subject | `subject_name` |
| Lecture | `session_title` |
| Rating (stars) | `overall_rating` (1-5) |
| Comment | `comment` |
| Date | `created_at` |
| Filter: Rating | `?overall_rating=<1-5>` |
| Filter: Subject | `?session__week__course=<course_id>` |
| Filter: Level | `?session__week__course__level=<level_id>` |

To populate filter dropdowns: use levels from `GET /api/v1/levels/admin/` and courses from `GET /api/v1/courses/admin/?level=<id>`.

---

## 18. Payments

### Dashboard Stats

```
GET /api/v1/payments/admin/dashboard/
```

**Response:**
```json
{
  "total_revenue": "245000.00",
  "successful_payments": 1240,
  "failed_payments": 32,
  "refunded_payments": 6,
  "revenue_trend": [
    { "month": "2024-01-01T00:00:00Z", "revenue": "45000.00", "count": 120 },
    { "month": "2024-02-01T00:00:00Z", "revenue": "52000.00", "count": 145 }
  ],
  "top_purchased_levels": [
    { "level_id": 1, "level_name": "Foundation", "purchase_count": 420 },
    { "level_id": 2, "level_name": "Intermediate", "purchase_count": 315 }
  ]
}
```

| Design Element | API Field |
|---|---|
| Total Revenue | `total_revenue` — format as ₹ |
| Successful Payments | `successful_payments` |
| Failed Payments | `failed_payments` |
| Refunded Payments | `refunded_payments` |
| Revenue Trend chart | `revenue_trend[]` — x=`month`, y=`revenue` |
| Top Purchased Courses donut | `top_purchased_levels[]` |

### See All Payments (Purchase List)

```
GET /api/v1/payments/admin/purchases/
```

Filters: `?status=active|expired|revoked`, `?level=<id>`

**Response per purchase:**
```json
{
  "id": 1,
  "level": 2,
  "level_name": "Intermediate",
  "amount_paid": "2999.00",
  "purchased_at": "2024-03-15T10:00:00Z",
  "expires_at": "2024-09-15T10:00:00Z",
  "status": "active",
  "is_valid": true,
  "extended_by_days": 0
}
```

### Extend Validity

```
POST /api/v1/payments/admin/extend/
```
```json
{ "purchase_id": 45, "extra_days": 30 }
```

---

## 19. Reports (Issue Reports)

```
GET /api/v1/auth/admin/issues/
```

**Query Params:**

| Param | Values | Notes |
|---|---|---|
| `is_resolved` | `true`, `false` | Tab: Reports=`false`, Resolved=`true` |
| `category` | `bug`, `content`, `payment`, `account`, `other` | |
| `search` | Subject or email | |

**Response per report:**
```json
{
  "id": 1,
  "user": 10,
  "user_email": "aarav@gmail.com",
  "student_name": "Aarav Sharma",
  "student_profile_picture": "/media/users/avatars/pic.jpg",
  "category": "bug",
  "subject": "Course video not playing",
  "description": "The video for Projectile Motion is not loading...",
  "screenshot": "/media/issues/screenshots/img.jpg",
  "device_info": "iPhone 13",
  "browser_info": "Chrome 120",
  "os_info": "iOS 17",
  "admin_response": "",
  "is_resolved": false,
  "created_at": "2024-05-12T10:00:00Z"
}
```

| Design Column | API Field |
|---|---|
| Report ID | `id` — format: `` `REP-${String(id).padStart(4, '0')}` `` |
| Student Name | `student_name` |
| Description Preview | `subject` |
| Date | `created_at` |
| Tab: Reports | `?is_resolved=false` |
| Tab: Resolved | `?is_resolved=true` |

---

## 20. Report Detail

Use the same data from the list response (all fields included). For the detail view layout:

| Design Element | API Field |
|---|---|
| Student Name | `student_name` |
| Student Pic | `student_profile_picture` |
| Device | `device_info` |
| Browser | `browser_info` |
| OS | `os_info` |
| Issue Description | `description` |
| Attachments | `screenshot` |
| Admin Response | `admin_response` |

### Update Report (Admin Response + Resolve)

```
PATCH /api/v1/auth/admin/issues/<issue_id>/
```

**Request:**
```json
{
  "admin_response": "We've identified the issue and deployed a fix.",
  "is_resolved": true
}
```

Both `admin_response` and `is_resolved` are writable. All other fields are read-only.

---

## 21. Level Analytics

```
GET /api/v1/analytics/levels/<level_id>/detail/
```

**Query Params:** `?days=7` or `?days=30` or `?days=90` (default: 30, max: 90)

**Response:**
```json
{
  "level_id": 2,
  "level_name": "Intermediate",
  "students_enrolled": 287,
  "completion_rate": 65.0,
  "exam_pass_rate": 58.33,
  "average_score": 72.45,
  "student_activity": [
    { "date": "2024-05-01", "active_students": 45 },
    { "date": "2024-05-02", "active_students": 52 }
  ],
  "module_completion_rate": [
    {
      "course_id": 1,
      "course_title": "Physics",
      "completion_rate": 85.0,
      "total_students": 200,
      "completed_students": 170
    }
  ]
}
```

| Design Element | API Field | Notes |
|---|---|---|
| Students Enrolled | `students_enrolled` | |
| Completion Rate | `completion_rate` | % or `null` if no students |
| Exam Pass Rate | `exam_pass_rate` | % or `null` |
| Average Score | `average_score` | Or `null` |
| Student Activity bar chart | `student_activity[]` | x=`date`, y=`active_students` |
| Module Completion donut | `module_completion_rate[]` | Per course with `completion_rate` |
| Toggle: Last 7/30/90 Days | `?days=7`, `?days=30`, `?days=90` | |

---

## 22. Settings

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

```
PATCH /api/v1/auth/preferences/
```

**Request (partial — send only changed fields):**
```json
{
  "payment_notifications": false,
  "feedback_reminder_notifications": false
}
```

| Design Toggle | API Field |
|---|---|
| Payment Confirmation | `payment_notifications` |
| Exam Completion | `exam_result_notifications` |
| Doubt Reply | `doubt_reply_notifications` |
| Issue Report | `issue_report_notifications` |
| Feedback Reminder | `feedback_reminder_notifications` |

---

## 23. Delete Confirmation Modal

Frontend-only component. The actual DELETE call depends on the resource:

| Resource | Endpoint | Returns |
|---|---|---|
| Level | `DELETE /api/v1/levels/admin/<id>/` | `204` |
| Course | `DELETE /api/v1/courses/admin/<id>/` | `204` |
| Module/Week | `DELETE /api/v1/courses/admin/weeks/<id>/` | `204` |
| Session/Topic | `DELETE /api/v1/courses/admin/sessions/<id>/` | `204` |
| Exam | `DELETE /api/v1/exams/admin/<id>/` | `204` |
| Question | `DELETE /api/v1/exams/admin/questions/<id>/` | `204` |
| Option | `DELETE /api/v1/exams/admin/options/<id>/` | `204` |
| Banner | `DELETE /api/v1/home/admin/banners/<id>/` | `204` |

---

## 24. Banners (Home)

### List Banners

```
GET /api/v1/home/admin/banners/
```

**Response per banner:**
```json
{
  "id": 1,
  "title": "New Course Launch",
  "subtitle": "Advanced Physics now available",
  "image_url": "https://storage.example.com/banner.jpg",
  "link_type": "course",
  "link_id": 5,
  "link_url": "",
  "order": 1,
  "is_active": true
}
```

`link_type` values: `"course"`, `"level"`, `"url"`, `"none"`

### Create Banner

```
POST /api/v1/home/admin/banners/
```

### Update / Delete Banner

```
PATCH /api/v1/home/admin/banners/<id>/
DELETE /api/v1/home/admin/banners/<id>/
```

---

## 25. Notifications

### List Notifications

```
GET /api/v1/notifications/
```

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

### Mark as Read

```
PATCH /api/v1/notifications/<id>/read/
```

### Mark All as Read

```
POST /api/v1/notifications/read-all/
```

### Delete One

```
DELETE /api/v1/notifications/<id>/
```

### Clear All

```
DELETE /api/v1/notifications/clear-all/
```

### Unread Count (for badge)

```
GET /api/v1/notifications/unread-count/
```

---

## 26. Pagination & Errors

### Paginated Response Format

All paginated endpoints return:
```json
{
  "count": 100,
  "next": "https://api.example.com/endpoint/?page=3",
  "previous": "https://api.example.com/endpoint/?page=1",
  "results": [...]
}
```

| Endpoint Type | Default Page Size | Max |
|---|---|---|
| Admin lists (students, attempts, purchases, issues, feedback, doubts) | 50 | 200 |
| Student-facing lists | 10 | 50 |

Override with `?page_size=25`.

**Non-paginated endpoints** (return plain arrays): Levels list, Weeks list, Options list.

### Error Format

```json
{ "detail": "Error message here." }
```

Validation errors:
```json
{ "field_name": ["Error message for this field."] }
```

| Code | Meaning |
|---|---|
| `200` | Success |
| `201` | Created |
| `204` | Deleted (no body) |
| `400` | Validation error |
| `401` | Token expired / not authenticated |
| `402` | Purchase required |
| `403` | Not admin / permission denied |
| `404` | Not found |
| `429` | Rate limited |
| `500` | Server error |

### Rate Limits

| Scope | Limit |
|---|---|
| Authenticated requests | 120/minute |
| Login/Register | 5/minute |
| Search | 60/minute |

---

## Complete Endpoint Reference

| Method | Endpoint | Section |
|---|---|---|
| `POST` | `/auth/login/` | [1](#1-authentication) |
| `POST` | `/auth/token/refresh/` | [1](#1-authentication) |
| `POST` | `/auth/logout/` | [1](#1-authentication) |
| `GET` | `/auth/me/` | [1](#1-authentication) |
| `GET` | `/analytics/dashboard/` | [2](#2-dashboard) |
| `GET` | `/auth/admin/students/` | [3](#3-student-management) |
| `GET` | `/auth/admin/students/<pk>/` | [4](#4-student-details) |
| `PATCH` | `/auth/admin/students/<pk>/` | [4](#4-student-details) |
| `GET` | `/levels/admin/` | [5](#5-course-management-levels) |
| `POST` | `/levels/admin/` | [5](#5-course-management-levels) |
| `PATCH` | `/levels/admin/<id>/` | [5](#5-course-management-levels) |
| `DELETE` | `/levels/admin/<id>/` | [5](#5-course-management-levels) |
| `GET` | `/courses/admin/?level=<id>` | [6](#6-curriculum-subjects-courses) |
| `POST` | `/courses/admin/` | [6](#6-curriculum-subjects-courses) |
| `PATCH` | `/courses/admin/<id>/` | [6](#6-curriculum-subjects-courses) |
| `DELETE` | `/courses/admin/<id>/` | [6](#6-curriculum-subjects-courses) |
| `GET` | `/courses/admin/<course_id>/weeks/` | [7](#7-curriculum-builder-modulesweeks) |
| `POST` | `/courses/admin/<course_id>/weeks/` | [7](#7-curriculum-builder-modulesweeks) |
| `PATCH` | `/courses/admin/weeks/<id>/` | [7](#7-curriculum-builder-modulesweeks) |
| `DELETE` | `/courses/admin/weeks/<id>/` | [7](#7-curriculum-builder-modulesweeks) |
| `GET` | `/courses/admin/sessions/?week=<id>` | [8](#8-topic-content-sessions) |
| `POST` | `/courses/admin/sessions/` | [9](#9-add-video-lecture), [10](#10-add-notes) |
| `PATCH` | `/courses/admin/sessions/<id>/` | [8](#8-topic-content-sessions) |
| `DELETE` | `/courses/admin/sessions/<id>/` | [23](#23-delete-confirmation-modal) |
| `GET` | `/exams/admin/` | [12](#12-exam-management-level-exams) |
| `POST` | `/exams/admin/` | [13](#13-create-level-exam) |
| `PATCH` | `/exams/admin/<id>/` | [13](#13-create-level-exam) |
| `DELETE` | `/exams/admin/<id>/` | [23](#23-delete-confirmation-modal) |
| `GET` | `/exams/admin/<exam_pk>/stats/` | [14](#14-exam-analytics) |
| `GET` | `/exams/admin/attempts/?exam=<id>` | [14](#14-exam-analytics) |
| `GET` | `/exams/admin/questions/?exam=<id>` | [11](#11-add-practice-questions) |
| `POST` | `/exams/admin/questions/` | [11](#11-add-practice-questions) |
| `PATCH` | `/exams/admin/questions/<id>/` | [11](#11-add-practice-questions) |
| `DELETE` | `/exams/admin/questions/<id>/` | [11](#11-add-practice-questions) |
| `GET` | `/exams/admin/questions/<id>/options/` | [11](#11-add-practice-questions) |
| `POST` | `/exams/admin/questions/<id>/options/` | [11](#11-add-practice-questions) |
| `PATCH` | `/exams/admin/options/<id>/` | [11](#11-add-practice-questions) |
| `DELETE` | `/exams/admin/options/<id>/` | [11](#11-add-practice-questions) |
| `GET` | `/doubts/admin/` | [15](#15-doubts-management) |
| `GET` | `/doubts/admin/<id>/` | [16](#16-doubt-conversation) |
| `POST` | `/doubts/admin/<id>/reply/` | [16](#16-doubt-conversation) |
| `PATCH` | `/doubts/admin/<id>/status/` | [16](#16-doubt-conversation) |
| `PATCH` | `/doubts/admin/<id>/assign/` | [16](#16-doubt-conversation) |
| `PATCH` | `/doubts/admin/<id>/bonus/` | [16](#16-doubt-conversation) |
| `GET` | `/feedback/admin/` | [17](#17-feedback) |
| `GET` | `/payments/admin/dashboard/` | [18](#18-payments) |
| `GET` | `/payments/admin/purchases/` | [18](#18-payments) |
| `POST` | `/payments/admin/extend/` | [18](#18-payments) |
| `GET` | `/auth/admin/issues/` | [19](#19-reports-issue-reports) |
| `PATCH` | `/auth/admin/issues/<id>/` | [20](#20-report-detail) |
| `GET` | `/analytics/levels/<level_pk>/detail/` | [21](#21-level-analytics) |
| `GET` | `/auth/preferences/` | [22](#22-settings) |
| `PATCH` | `/auth/preferences/` | [22](#22-settings) |
| `GET` | `/home/admin/banners/` | [24](#24-banners-home) |
| `POST` | `/home/admin/banners/` | [24](#24-banners-home) |
| `PATCH` | `/home/admin/banners/<id>/` | [24](#24-banners-home) |
| `DELETE` | `/home/admin/banners/<id>/` | [24](#24-banners-home) |
| `GET` | `/notifications/` | [25](#25-notifications) |
| `PATCH` | `/notifications/<id>/read/` | [25](#25-notifications) |
| `POST` | `/notifications/read-all/` | [25](#25-notifications) |
| `DELETE` | `/notifications/<id>/` | [25](#25-notifications) |
| `DELETE` | `/notifications/clear-all/` | [25](#25-notifications) |
| `GET` | `/notifications/unread-count/` | [25](#25-notifications) |
