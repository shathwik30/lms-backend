# LMS Backend - Admin API Documentation

**Base URL:** `/api/v1/`
**Authentication:** JWT (Bearer token via `Authorization: Bearer <access_token>`)
**Content-Type:** `application/json` (unless uploading files — use `multipart/form-data`)

All endpoints in this document require **Admin** permission (`is_admin=true`).

---

## Authentication & Tokens

All admin endpoints require a JWT access token in the `Authorization` header.

```
Authorization: Bearer <access_token>
```

Tokens are obtained via `/api/v1/auth/login/`. See `APP.md` for full auth endpoint documentation.

---

## 1. Students

### `GET /api/v1/auth/admin/students/`
**Pagination:** LargePagination (50/page)
**Filters:** `current_level`, `highest_cleared_level`
**Search:** `user__email`, `user__full_name`

List all students.

### `GET /api/v1/auth/admin/students/<id>/`

Get a student profile.

### `PATCH /api/v1/auth/admin/students/<id>/`

Update a student's level assignment.

**Request:**
```json
{
  "current_level": 2,
  "highest_cleared_level": 1
}
```

---

## 2. Issues

### `GET /api/v1/auth/admin/issues/`
**Pagination:** LargePagination (50/page)
**Filters:** `category`, `is_resolved`
**Search:** `subject`, `user__email`

List all issue reports.

### `PATCH /api/v1/auth/admin/issues/<id>/`

Update an issue report (e.g., mark as resolved).

**Request:**
```json
{
  "is_resolved": true
}
```

---

## 3. Levels

### `GET /api/v1/levels/admin/`
**Pagination:** None (returns flat list)

List all levels (including inactive).

### `POST /api/v1/levels/admin/`

Create a level.

**Request:**
```json
{
  "name": "Level 1",
  "order": 1,
  "description": "...",
  "is_active": true,
  "passing_percentage": 50.0,
  "price": "999.00",
  "validity_days": 90,
  "max_final_exam_attempts": 3
}
```

### `GET|PUT|PATCH|DELETE /api/v1/levels/admin/<id>/`

Full CRUD for individual levels.

---

## 4. Courses

### `GET|POST /api/v1/courses/admin/`
**Pagination:** LargePagination (50/page)
**Filters:** `level`, `is_active`

List or create courses.

### `GET|PUT|PATCH|DELETE /api/v1/courses/admin/<id>/`

Full CRUD for individual courses.

---

## 5. Weeks

### `GET|POST /api/v1/courses/admin/<course_id>/weeks/`
**Pagination:** None

List or create weeks within a course.

**Week fields:** `id`, `course`, `name`, `order`, `is_active`, `created_at`.

### `GET|PUT|PATCH|DELETE /api/v1/courses/admin/weeks/<id>/`

Full CRUD for individual weeks.

---

## 6. Sessions

### `GET|POST /api/v1/courses/admin/sessions/`
**Pagination:** StandardPagination (20/page)
**Filters:** `week`, `is_active`, `session_type`

List or create sessions. On GET, `markdown_content` is deferred for performance.

**Session fields:** `id`, `week`, `title`, `description`, `video_url`, `file_url`, `resource_type`, `markdown_content`, `duration_seconds`, `order`, `session_type`, `exam`, `is_active`.

**Session types:** `video`, `resource`, `practice_exam`, `proctored_exam`.
**Resource types:** `pdf`, `note`, `markdown`.

### `GET|PUT|PATCH|DELETE /api/v1/courses/admin/sessions/<id>/`

Full CRUD for individual sessions.

---

## 7. Exams

### `GET|POST /api/v1/exams/admin/`
**Pagination:** LargePagination (50/page)
**Filters:** `level`, `exam_type`, `is_active`

List or create exams.

### `GET|PUT|PATCH|DELETE /api/v1/exams/admin/<id>/`

Full CRUD for individual exams.

---

## 8. Questions

### `GET|POST /api/v1/exams/admin/questions/`
**Pagination:** LargePagination (50/page)
**Filters:** `exam`, `level`, `difficulty`, `question_type`, `is_active`

List or create questions. Questions include `options` (with `is_correct` visible to admins).

**Question fields:** `id`, `exam`, `level`, `text`, `image_url`, `difficulty`, `question_type`, `marks`, `negative_marks`, `explanation`, `correct_text_answer`, `is_active`, `options`, `created_at`.

**Question types:** `mcq`, `multi_mcq`, `fill_blank`.
**Difficulties:** `easy`, `medium`, `hard`.

### `GET|PUT|PATCH|DELETE /api/v1/exams/admin/questions/<id>/`

Full CRUD for individual questions.

---

## 9. Options

### `GET|POST /api/v1/exams/admin/questions/<question_id>/options/`
**Pagination:** None

List or create options for a question.

**Option fields:** `id`, `question`, `text`, `image_url`, `is_correct`.

### `GET|PUT|PATCH|DELETE /api/v1/exams/admin/options/<id>/`

Full CRUD for individual options.

---

## 10. Attempts

### `GET /api/v1/exams/admin/attempts/`
**Pagination:** LargePagination (50/page)
**Filters:** `exam`, `status`, `is_passed`, `is_disqualified`, `exam__level`

List all exam attempts.

---

## 11. Purchases

### `GET /api/v1/payments/admin/purchases/`
**Pagination:** LargePagination (50/page)
**Filters:** `status`, `level`

List all purchases.

### `POST /api/v1/payments/admin/extend/`

Extend a purchase's validity period.

**Request:**
```json
{
  "purchase_id": 1,
  "extra_days": 30
}
```

**Response (200):** Returns the updated purchase object.

---

## 12. Doubts

### `GET /api/v1/doubts/admin/`
**Pagination:** LargePagination (50/page)
**Filters:** `status`, `context_type`, `assigned_to`
**Search:** `title`, `student__user__email`

List all doubt tickets.

### `GET /api/v1/doubts/admin/<id>/`

Get doubt ticket details with replies.

### `POST /api/v1/doubts/admin/<id>/reply/`

Reply to a doubt ticket as admin.

### `PATCH /api/v1/doubts/admin/<id>/assign/`

Assign a doubt ticket to an admin user.

**Request:**
```json
{
  "assigned_to": 2
}
```

### `PATCH /api/v1/doubts/admin/<id>/status/`

Update doubt ticket status.

**Request:**
```json
{
  "status": "answered"
}
```

**Doubt statuses:** `open`, `in_review`, `answered`, `closed`.

### `PATCH /api/v1/doubts/admin/<id>/bonus/`

Award bonus marks to the student.

**Request:**
```json
{
  "bonus_marks": 5.00
}
```

---

## 13. Feedback

### `GET /api/v1/feedback/admin/`
**Pagination:** LargePagination (50/page)
**Filters:** `session`, `overall_rating`, `difficulty_rating`, `clarity_rating`
**Search:** `student__user__email`

List all feedback.

---

## 14. Analytics

### `GET /api/v1/analytics/revenue/`
**Pagination:** LargePagination (50/page)
**Filters:** `date`

Get daily revenue records.

**Response fields:** `id`, `date`, `total_revenue`, `total_transactions`.

---

### `GET /api/v1/analytics/levels/`
**Pagination:** LargePagination (50/page)
**Filters:** `level`, `date`

Get per-level analytics.

**Response fields:** `id`, `level`, `level_name`, `date`, `total_attempts`, `total_passes`, `total_failures`, `total_purchases`, `revenue`, `pass_rate`.

---

## 15. Banners

### `GET|POST /api/v1/home/admin/banners/`
**Pagination:** None

List or create banners.

**Banner fields:** `id`, `title`, `subtitle`, `image_url`, `link_type`, `link_id`, `link_url`, `order`, `is_active`.

### `GET|PUT|PATCH|DELETE /api/v1/home/admin/banners/<id>/`

Full CRUD for individual banners.

---

## Pagination

Admin list endpoints use **LargePagination** (50/page, max 200). Some endpoints have no pagination (flat list): levels, weeks, banners, options.

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

**401 Unauthorized:**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**403 Forbidden:**
```json
{
  "detail": "You do not have permission to perform this action."
}
```

**404 Not Found:**
```json
{
  "detail": "Not found."
}
```

**400 Bad Request:**
```json
{
  "field_name": ["Error message."]
}
```

---

## Interactive API Docs

- **Swagger UI:** `/api/docs/`
- **ReDoc:** `/api/redoc/`
- **OpenAPI Schema (JSON):** `/api/schema/`
