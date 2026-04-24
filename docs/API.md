# LMS Backend API Documentation

Refreshed against the codebase on April 24, 2026.

This repository now keeps two API references in sync:

- Human-readable guide: [`docs/API.md`](API.md)
- Exact OpenAPI snapshot generated from the app: [`docs/openapi.yaml`](openapi.yaml)

Live documentation endpoints:

- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI schema: `/api/schema/`

## Base Contract

- Base URL: `/api/v1/`
- Auth: JWT bearer token via `Authorization: Bearer <access_token>`
- Default content type: `application/json`
- File uploads: use `multipart/form-data`
- ID format: path parameters are UUIDs; some request bodies still accept legacy integer IDs through compatibility serializer fields

Permission levels used below:

- `Public`: no authentication required
- `Authenticated`: any logged-in user
- `Student`: authenticated user with `is_student=true`
- `Admin`: authenticated user with `is_admin=true`

## Source Of Truth

Use [`docs/openapi.yaml`](openapi.yaml) when you need the exact request and response schema for a field, enum, nullable value, or serializer expansion.

Regenerate it from the current code with:

```bash
.venv/bin/python manage.py spectacular --file docs/openapi.yaml
```

## Cross-Cutting Behavior

### Authentication

- Access token lifetime: 30 minutes
- Refresh token lifetime: 7 days
- Refresh rotation is enabled
- Logout blacklists the submitted refresh token

### Pagination

| Class | Shape | Default | Max | Used By |
|---|---|---:|---:|---|
| `StandardPagination` | page number | 20 | 100 | most list endpoints |
| `SmallPagination` | page number | 10 | 50 | student-facing lists |
| `LargePagination` | page number | 50 | 200 | admin tables |
| `AnalyticsCursorPagination` | cursor | 50 | 50 | analytics lists |

Page-number responses use:

```json
{
  "count": 42,
  "next": "http://host/api/v1/example/?page=2",
  "previous": null,
  "results": []
}
```

Analytics cursor responses use the standard DRF cursor format with `next`, `previous`, and `results`.

### Rate Limits

| Scope | Limit |
|---|---|
| `anon` | 30/minute |
| `user` | 120/minute |
| `login` | 5/minute |
| `payment` | 10/minute |
| `exam_submit` | 30/hour |
| `search` | 60/minute |
| `doubt_create` | 10/minute |
| `feedback` | 20/minute |
| `progress_update` | 120/minute |

### Common Errors

| Status | Meaning |
|---|---|
| `400` | validation failure or unsupported state transition |
| `401` | missing/invalid authentication |
| `402` | purchase required for gated content |
| `403` | role/eligibility restriction |
| `404` | object not found |
| `429` | throttled |
| `502` | payment gateway failure |

## Endpoint Catalog

### Auth And User Profile

| Method | Path | Access | Notes |
|---|---|---|---|
| `POST` | `/api/v1/auth/register/` | Public | Create a student account and return `{user, tokens}`. |
| `POST` | `/api/v1/auth/login/` | Public | Email/password login. Returns `{user, tokens}`. |
| `POST` | `/api/v1/auth/google/` | Public | Google ID token login. Returns `{user, tokens, created}`. |
| `POST` | `/api/v1/auth/logout/` | Authenticated | Blacklist a refresh token. Body: `refresh`. |
| `POST` | `/api/v1/auth/token/refresh/` | Public | Simple JWT refresh endpoint. |
| `GET` | `/api/v1/auth/me/` | Authenticated | Current user profile. Students also receive `profile`. |
| `PATCH` | `/api/v1/auth/me/` | Authenticated | Update `full_name`, `phone`, `profile_picture`, `gender`. |
| `DELETE` | `/api/v1/auth/me/` | Authenticated | Remove current profile picture. |
| `POST` | `/api/v1/auth/change-password/` | Authenticated | Change password and issue a fresh token pair. |
| `POST` | `/api/v1/auth/password-reset/` | Public | Request password reset email. |
| `POST` | `/api/v1/auth/password-reset/confirm/` | Public | Confirm reset with `uid`, `token`, `new_password`. |
| `POST` | `/api/v1/auth/otp/send/` | Public | Send OTP for `verify` or `password_reset`. |
| `POST` | `/api/v1/auth/otp/verify/` | Public | Verify OTP for a given email and purpose. |
| `GET` | `/api/v1/auth/preferences/` | Authenticated | Read notification preferences. |
| `PATCH` | `/api/v1/auth/preferences/` | Authenticated | Update notification preferences. |
| `POST` | `/api/v1/auth/onboarding/complete/` | Authenticated | Mark onboarding complete. |
| `POST` | `/api/v1/auth/report-issue/` | Authenticated | Submit issue report. Optional screenshot upload supported. |
| `GET` | `/api/v1/auth/my-issues/` | Authenticated | List current user's issue reports. |

### Admin User Management

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/auth/admin/students/` | Admin | List students. Filters include `current_level`, `highest_cleared_level`, `validity`, `account_status`, `search`. |
| `GET` | `/api/v1/auth/admin/students/{id}/` | Admin | Rich student detail payload for admin UI. Response includes `engagement_status`, `streak_summary` (7-day activity + longest streak), `proctoring_summary`, `support_interaction`, `payment_history`, and enhanced `exam_history` (`auto_submitted`, `violations_count`, `duration_seconds`, `is_disqualified`). See `docs/ADMIN_FRONTEND_API_GUIDE.md` §4 for full shape. |
| `PATCH` | `/api/v1/auth/admin/students/{id}/` | Admin | Update core student fields and level assignments. |
| `DELETE` | `/api/v1/auth/admin/students/{id}/` | Admin | Permanently delete the student account. |
| `PATCH` | `/api/v1/auth/admin/students/{id}/block/` | Admin | Toggle `is_active`. Body: `{"is_active": true|false}`. |
| `POST` | `/api/v1/auth/admin/students/{id}/send-reminder/` | Admin | Send engagement reminder. Optional body: `message`. |
| `POST` | `/api/v1/auth/admin/students/{id}/reset-exam-attempts/` | Admin | Body: `level_id`, `reason`. Resets final exam attempts for that level. |
| `POST` | `/api/v1/auth/admin/students/{id}/unlock-level/` | Admin | Body: `level_id`, `reason`. Grants access manually and returns `purchase`. |
| `POST` | `/api/v1/auth/admin/students/{id}/manual-pass/` | Admin | Body: `level_id`, `reason`. Marks the level as passed manually. |
| `POST` | `/api/v1/auth/admin/students/{id}/extend-validity/` | Admin | Body: `level_id`, `extra_days`, `reason`. Extends the latest purchase for that level. |
| `GET` | `/api/v1/auth/admin/issues/` | Admin | List issue reports. Filters include `category`, `is_resolved`, `search`. |
| `GET` | `/api/v1/auth/admin/issues/{id}/` | Admin | Retrieve one issue report. |
| `PATCH` | `/api/v1/auth/admin/issues/{id}/` | Admin | Update issue resolution fields. |

### Levels

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/levels/` | Public | List active levels. |
| `GET` | `/api/v1/levels/{id}/` | Public | Retrieve one active level with related course data. |
| `GET` | `/api/v1/levels/admin/` | Admin | List all levels, including inactive ones. |
| `POST` | `/api/v1/levels/admin/` | Admin | Create a level. |
| `GET` | `/api/v1/levels/admin/{id}/` | Admin | Retrieve a level. |
| `PUT` | `/api/v1/levels/admin/{id}/` | Admin | Replace a level. |
| `PATCH` | `/api/v1/levels/admin/{id}/` | Admin | Partially update a level. |
| `DELETE` | `/api/v1/levels/admin/{id}/` | Admin | Delete a level. |

### Courses, Weeks, Sessions, Bookmarks

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/courses/level/{level_pk}/` | Authenticated | List active courses in a level. |
| `GET` | `/api/v1/courses/{course_pk}/sessions/` | Student | Purchased-course curriculum. |
| `GET` | `/api/v1/courses/sessions/{id}/` | Student | Session detail with video/resource/markdown/exam linkage. |
| `POST` | `/api/v1/courses/sessions/{id}/complete-resource/` | Student | Mark a resource session complete. |
| `GET` | `/api/v1/courses/bookmarks/` | Student | List bookmarks. |
| `POST` | `/api/v1/courses/bookmarks/` | Student | Create bookmark. Body: `session`. |
| `DELETE` | `/api/v1/courses/bookmarks/{id}/` | Student | Delete bookmark. |
| `GET` | `/api/v1/courses/admin/` | Admin | List courses. Filters include `level`, `is_active`. |
| `POST` | `/api/v1/courses/admin/` | Admin | Create course. |
| `GET` | `/api/v1/courses/admin/{id}/` | Admin | Retrieve course. |
| `PUT` | `/api/v1/courses/admin/{id}/` | Admin | Replace course. |
| `PATCH` | `/api/v1/courses/admin/{id}/` | Admin | Partially update course. |
| `DELETE` | `/api/v1/courses/admin/{id}/` | Admin | Delete course. |
| `GET` | `/api/v1/courses/admin/{course_pk}/weeks/` | Admin | List weeks for a course. |
| `POST` | `/api/v1/courses/admin/{course_pk}/weeks/` | Admin | Create a week for a course. |
| `GET` | `/api/v1/courses/admin/weeks/{id}/` | Admin | Retrieve week. |
| `PUT` | `/api/v1/courses/admin/weeks/{id}/` | Admin | Replace week. |
| `PATCH` | `/api/v1/courses/admin/weeks/{id}/` | Admin | Partially update week. |
| `DELETE` | `/api/v1/courses/admin/weeks/{id}/` | Admin | Delete week. |
| `GET` | `/api/v1/courses/admin/sessions/` | Admin | List sessions. Filters include `week`, `is_active`, `session_type`. |
| `POST` | `/api/v1/courses/admin/sessions/` | Admin | Create session. |
| `GET` | `/api/v1/courses/admin/sessions/{id}/` | Admin | Retrieve session. |
| `PUT` | `/api/v1/courses/admin/sessions/{id}/` | Admin | Replace session. |
| `PATCH` | `/api/v1/courses/admin/sessions/{id}/` | Admin | Partially update session. |
| `DELETE` | `/api/v1/courses/admin/sessions/{id}/` | Admin | Delete session. |

### Exams And Proctoring

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/exams/{id}/` | Student | Exam detail, including eligibility metadata. |
| `POST` | `/api/v1/exams/{id}/start/` | Student | Start or resume an in-progress attempt. |
| `GET` | `/api/v1/exams/attempts/` | Student | List my attempts. Filters include `exam`, `status`, `is_passed`. |
| `POST` | `/api/v1/exams/attempts/{id}/submit/` | Student | Submit answers. Supports single choice, multi-select, and text answers. |
| `GET` | `/api/v1/exams/attempts/{id}/result/` | Student | Result breakdown per question. |
| `GET` | `/api/v1/exams/attempts/{id}/violations/` | Student | Violation history for a proctored attempt. |
| `POST` | `/api/v1/exams/attempts/{id}/report-violation/` | Student | Create a violation entry during the attempt. |
| `GET` | `/api/v1/exams/admin/` | Admin | List exams. Filters include `level`, `exam_type`, `is_active`. |
| `POST` | `/api/v1/exams/admin/` | Admin | Create exam. |
| `GET` | `/api/v1/exams/admin/{id}/` | Admin | Retrieve exam. |
| `PUT` | `/api/v1/exams/admin/{id}/` | Admin | Replace exam. |
| `PATCH` | `/api/v1/exams/admin/{id}/` | Admin | Partially update exam. |
| `DELETE` | `/api/v1/exams/admin/{id}/` | Admin | Delete exam. |
| `GET` | `/api/v1/exams/admin/attempts/` | Admin | List all attempts. Filters include `exam`, `status`, `is_passed`, `is_disqualified`, `exam__level`. |
| `GET` | `/api/v1/exams/admin/{exam_pk}/stats/` | Admin | Aggregate stats for one exam. |
| `GET` | `/api/v1/exams/admin/questions/` | Admin | List questions. Filters include `exam`, `level`, `difficulty`, `question_type`, `is_active`. |
| `POST` | `/api/v1/exams/admin/questions/` | Admin | Create question. |
| `POST` | `/api/v1/exams/admin/questions/bulk/` | Admin | Bulk-create questions. |
| `GET` | `/api/v1/exams/admin/questions/{id}/` | Admin | Retrieve question. |
| `PUT` | `/api/v1/exams/admin/questions/{id}/` | Admin | Replace question. |
| `PATCH` | `/api/v1/exams/admin/questions/{id}/` | Admin | Partially update question. |
| `DELETE` | `/api/v1/exams/admin/questions/{id}/` | Admin | Delete question. |
| `GET` | `/api/v1/exams/admin/questions/{question_pk}/options/` | Admin | List options for a question. |
| `POST` | `/api/v1/exams/admin/questions/{question_pk}/options/` | Admin | Create option. |
| `GET` | `/api/v1/exams/admin/options/{id}/` | Admin | Retrieve option. |
| `PUT` | `/api/v1/exams/admin/options/{id}/` | Admin | Replace option. |
| `PATCH` | `/api/v1/exams/admin/options/{id}/` | Admin | Partially update option. |
| `DELETE` | `/api/v1/exams/admin/options/{id}/` | Admin | Delete option. |

### Payments

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/payments/preview/{level_id}/` | Student | Purchase preview for a level, including syllabus and benefit summary. |
| `POST` | `/api/v1/payments/initiate/` | Student | Body: `level_id`. Creates Razorpay order or grants free access immediately. |
| `POST` | `/api/v1/payments/verify/` | Student | Body: `razorpay_order_id`, `razorpay_payment_id`, `razorpay_signature`. |
| `POST` | `/api/v1/payments/dev-purchase/` | Student | Development shortcut that creates a purchase without Razorpay. |
| `GET` | `/api/v1/payments/purchases/` | Student | List my purchases. Filters include `level`, `status`. |
| `GET` | `/api/v1/payments/purchases/{id}/` | Student | Retrieve one of my purchases. |
| `GET` | `/api/v1/payments/transactions/` | Student | List my payment transactions. Filter: `status`. |
| `GET` | `/api/v1/payments/transactions/{id}/` | Student | Retrieve one of my payment transactions. |
| `GET` | `/api/v1/payments/admin/dashboard/` | Admin | Payment dashboard totals, monthly trend, top purchased levels. |
| `POST` | `/api/v1/payments/admin/extend/` | Admin | Body: `purchase_id`, `extra_days`, optional `reason`. |
| `GET` | `/api/v1/payments/admin/purchases/` | Admin | List all purchases. Filters include `status`, `level`. Each row now includes `transaction_id`, `payment_status`, `payment_method`, `payment_gateway` derived from the linked `PaymentTransaction`. |
| `GET` | `/api/v1/payments/admin/purchases/{id}/` | Admin | Retrieve a purchase (same enriched shape as the list). |
| `GET` | `/api/v1/payments/admin/transactions/{id}/` | Admin | Retrieve a payment transaction. |

### Progress

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/progress/dashboard/` | Student | Dashboard summary and next action. |
| `POST` | `/api/v1/progress/sessions/{session_pk}/` | Student | Update watched seconds for a video session. |
| `GET` | `/api/v1/progress/levels/{level_pk}/sessions/` | Student | Session progress for a level. |
| `GET` | `/api/v1/progress/levels/` | Student | Level progress list. |
| `GET` | `/api/v1/progress/courses/{course_pk}/` | Student | One course's progress. |
| `GET` | `/api/v1/progress/levels/{level_pk}/courses/` | Student | Course progress for all courses in a level. |
| `GET` | `/api/v1/progress/calendar/` | Student | Activity calendar. Required query params: `year`, `month`. |
| `GET` | `/api/v1/progress/leaderboard/` | Authenticated | Optional query params: `level`, `limit`. |

### Doubts

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/doubts/` | Student | List my doubt tickets. |
| `POST` | `/api/v1/doubts/` | Student | Create doubt ticket. Supports screenshot upload. |
| `GET` | `/api/v1/doubts/{id}/` | Student | Retrieve one of my doubt tickets with replies. |
| `POST` | `/api/v1/doubts/{id}/reply/` | Student | Reply to a ticket. Supports attachment upload. |
| `GET` | `/api/v1/doubts/admin/` | Admin | List all tickets. Filters include `status`, `context_type`, `assigned_to`, `search`. |
| `GET` | `/api/v1/doubts/admin/{id}/` | Admin | Retrieve ticket detail. |
| `POST` | `/api/v1/doubts/admin/{id}/reply/` | Admin | Reply as admin. |
| `PATCH` | `/api/v1/doubts/admin/{id}/assign/` | Admin | Assign ticket to an admin user. |
| `PATCH` | `/api/v1/doubts/admin/{id}/status/` | Admin | Update ticket status. |
| `PATCH` | `/api/v1/doubts/admin/{id}/bonus/` | Admin | Award bonus marks. |

### Feedback

| Method | Path | Access | Notes |
|---|---|---|---|
| `POST` | `/api/v1/feedback/sessions/{session_pk}/` | Student | Submit feedback for a session. |
| `GET` | `/api/v1/feedback/` | Student | List my submitted feedback. |
| `GET` | `/api/v1/feedback/admin/` | Admin | List all feedback records. |

### Analytics

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/analytics/dashboard/` | Admin | Admin overview metrics. |
| `GET` | `/api/v1/analytics/revenue/` | Admin | Cursor-paginated daily revenue records. Filter: `date`. |
| `GET` | `/api/v1/analytics/levels/` | Admin | Cursor-paginated level analytics. Filters: `level`, `date`. |
| `GET` | `/api/v1/analytics/levels/{level_pk}/detail/` | Admin | Detailed level analytics. Optional query param: `days` (default 30, capped at 90). |

### Notifications

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/notifications/` | Authenticated | List notifications. Filters include `is_read`, `notification_type`. |
| `DELETE` | `/api/v1/notifications/{id}/` | Authenticated | Delete one notification. |
| `PATCH` | `/api/v1/notifications/{id}/read/` | Authenticated | Mark one notification as read. |
| `POST` | `/api/v1/notifications/read-all/` | Authenticated | Mark all notifications as read. |
| `DELETE` | `/api/v1/notifications/clear-all/` | Authenticated | Delete all notifications. |
| `GET` | `/api/v1/notifications/unread-count/` | Authenticated | Return unread notification count. |

### Home

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/home/banners/` | Public | List active banners. |
| `GET` | `/api/v1/home/featured/` | Public | List up to 10 active courses for home. |
| `GET` | `/api/v1/home/levels/{level_id}/exams/` | Public | Level exam feed for home. Authenticated students also receive attempt stats and eligibility. |
| `GET` | `/api/v1/home/admin/banners/` | Admin | List all banners. |
| `POST` | `/api/v1/home/admin/banners/` | Admin | Create banner. |
| `GET` | `/api/v1/home/admin/banners/{id}/` | Admin | Retrieve banner. |
| `PUT` | `/api/v1/home/admin/banners/{id}/` | Admin | Replace banner. |
| `PATCH` | `/api/v1/home/admin/banners/{id}/` | Admin | Partially update banner. |
| `DELETE` | `/api/v1/home/admin/banners/{id}/` | Admin | Delete banner. |

### Search

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/search/` | Authenticated | Global search. Query param `q` is required. Optional `level`, `week`. |

### Health And Utility Endpoints

| Method | Path | Access | Notes |
|---|---|---|---|
| `GET` | `/api/v1/health/` | Public | API, DB, and Redis health check. |
| `GET` | `/api/schema/` | Environment-dependent | Generated OpenAPI schema endpoint. Public in production settings. |
| `GET` | `/api/docs/` | Environment-dependent | Swagger UI. |
| `GET` | `/api/redoc/` | Environment-dependent | ReDoc UI. |
| `GET` | `/metrics/` | Admin | Prometheus metrics export. |

## Important Behavioral Notes

### Purchases And Content Gating

- Paid levels use `/payments/initiate/` plus `/payments/verify/`.
- Free levels are granted immediately by `/payments/initiate/`; the response sets `is_free=true` and includes `purchase_id` and `expires_at`.
- `/payments/dev-purchase/` is a development/testing shortcut that skips Razorpay entirely.
- Session content, exam access, feedback submission, and some doubt flows are gated by active purchases or level eligibility. The API can return `402` or `403` depending on the check.

### Exams

- Supported question types: `mcq`, `multi_mcq`, `fill_blank`.
- Submission payload supports `option_id`, `option_ids`, and `text_answer` depending on question type.
- Proctoring violations are tracked separately and can auto-disqualify attempts when the warning cap is reached.
- Weekly exams may also appear as course sessions through the curriculum APIs.

### Student Admin Actions

- `reset-exam-attempts`, `unlock-level`, and `manual-pass` all require both `level_id` and a non-empty `reason`.
- `extend-validity` from student management targets the latest purchase for the specified level.
- Admin payment extend and admin student extend share the same underlying purchase-extension service but accept different lookup inputs.

### Analytics Pagination

- `/analytics/revenue/` and `/analytics/levels/` use cursor pagination, not page-number pagination.
- The dashboard and level-detail endpoints are unpaginated aggregate responses.

## Recommended Consumer Workflow

For frontend or mobile work:

1. Use [`docs/API.md`](API.md) to discover routes, permissions, pagination, and behavior.
2. Use [`docs/openapi.yaml`](openapi.yaml) or `/api/schema/` for exact payload shapes.
3. Use `/api/docs/` during development for live request testing.
