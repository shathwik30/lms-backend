# Change Summary - 2026-04-09

This document summarizes the local changes committed on 2026-04-09.

## 1. Weekly Exam Progression Fix

Problem addressed:
- Passed weekly exams could still appear incomplete in course curriculum.
- Later sessions or weeks could remain locked if weekly exam-linked `SessionProgress` was missing or stale.
- A failed retake could overwrite an already-passed weekly exam session.

What changed:
- Added lazy repair logic to restore weekly exam `SessionProgress` from passed `ExamAttempt` records.
- Wired that repair into:
  - course curriculum loading
  - session accessibility checks
- Made passed exam session completion sticky so later failed retakes do not downgrade already-cleared progress.

Files:
- `apps/progress/services.py`
- `apps/courses/views.py`
- `core/services/eligibility.py`
- `tests/test_courses/test_views.py`
- `tests/test_progress/test_services.py`

## 2. Admin Student Management APIs

Added new admin student action endpoints:
- `POST /api/v1/auth/admin/students/<student_id>/reset-exam-attempts/`
- `POST /api/v1/auth/admin/students/<student_id>/unlock-level/`
- `POST /api/v1/auth/admin/students/<student_id>/manual-pass/`
- `POST /api/v1/auth/admin/students/<student_id>/extend-validity/`

Behavior:
- `reset-exam-attempts`
  - Resets `final_exam_attempts_used` for a level.
  - Moves non-passed levels back to `in_progress` or `syllabus_complete` depending on syllabus state.
- `unlock-level`
  - Grants manual level access by creating or reusing a purchase and provisioning progress.
- `manual-pass`
  - Marks a level as passed in `LevelProgress`.
  - Updates student `highest_cleared_level` and `current_level` when needed.
- `extend-validity`
  - Extends the latest purchase for a student and level from the student-management surface.

Files:
- `apps/users/urls.py`
- `apps/users/views.py`
- `apps/users/services.py`
- `tests/test_users/test_admin_student_actions.py`

## 3. Audit Trail for Admin Actions

Added persistent audit logging for admin student actions.

New model:
- `AdminStudentActionLog`

Tracked action types:
- `reset_exam_attempts`
- `unlock_level`
- `manual_pass`
- `extend_validity`

Stored audit fields:
- student
- admin user
- action type
- optional level
- optional purchase
- required reason
- metadata JSON

Files:
- `apps/users/models.py`
- `apps/users/migrations/0007_adminstudentactionlog.py`
- `apps/users/serializers.py`

Student detail response now includes:
- `admin_action_history`

## 4. Reason Support for Validity Extension

Added `reason` support to validity extension flows so the action is included in the audit trail.

Files:
- `apps/payments/serializers.py`
- `apps/payments/services.py`
- `apps/payments/views.py`

## 5. Admin Issue Detail GET Support

Problem addressed:
- `GET /api/v1/auth/admin/issues/<id>/` returned `Method "GET" not allowed.`

What changed:
- Added `GET` support to the existing admin issue detail endpoint while keeping `PATCH` support.

Files:
- `apps/users/views.py`
- `tests/test_users/test_admin_issues.py`

## 6. Exam Attempt Result Payload Fix

Problem addressed:
- The student exam result endpoint exposed only option IDs for selected and correct answers.
- Frontend consumers could not render readable answer review data from `/api/v1/exams/attempts/<id>/result/`.

What changed:
- Kept the existing ID fields for backward compatibility.
- Added readable selected-answer and correct-answer payloads:
  - `selected_option_detail`
  - `selected_options_detail`
  - `correct_options`
  - `options`
- `options` now returns each option with:
  - `id`
  - `text`
  - `image_url`
  - `is_correct`
  - `is_selected`
- Updated the result view query to prefetch the option relations used by the serializer.

Files:
- `apps/exams/serializers.py`
- `apps/exams/views.py`
- `tests/test_exams/test_views.py`

## 7. Test Coverage Added or Updated

Covered:
- weekly exam session recreation and progress repair
- sticky passed exam status on retake failure
- reset exam attempts admin action
- unlock level admin action
- manual pass admin action
- extend validity with audit reason
- admin student detail audit history
- admin issue detail GET

Targeted test commands run:

```bash
python manage.py test tests.test_users.test_admin_student_detail \
  tests.test_users.test_admin_student_actions \
  tests.test_users.test_admin_issues \
  tests.test_payments.test_views.AdminPaymentAPITests \
  tests.test_payments.test_services.PaymentServiceExtendValidityTests \
  --keepdb --noinput
```

Result:
- 44 tests passed

Additional targeted verification:

```bash
python manage.py test tests.test_exams.test_views --keepdb --noinput
```

Result:
- 59 tests passed

## 8. Notes

- These changes include both the admin student-management work and the earlier weekly exam progression fix because both were still pending in the local worktree.
- Database migration required:
  - `apps/users/migrations/0007_adminstudentactionlog.py`
