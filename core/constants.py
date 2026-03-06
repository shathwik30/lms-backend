from enum import Enum


class NextAction(str, Enum):
    """Actions returned by EligibilityService.get_next_action()."""

    ATTEMPT_EXAM = "attempt_exam"
    COMPLETE_SYLLABUS = "complete_syllabus"
    PURCHASE_COURSE = "purchase_course"
    ALL_COMPLETE = "all_complete"
    NO_LEVELS = "no_levels"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"


# ── Error Messages ──


class ErrorMessage:
    NOT_FOUND = "Not found."
    USER_NOT_FOUND = "User not found."
    SESSION_NOT_FOUND = "Session not found."
    COURSE_NOT_FOUND = "Course not found."
    TRANSACTION_NOT_FOUND = "Transaction not found."
    PURCHASE_NOT_FOUND = "Purchase not found."

    # Auth
    INVALID_CREDENTIALS = "Invalid credentials."
    INVALID_GOOGLE_TOKEN = "Invalid Google token."
    GOOGLE_EMAIL_NOT_VERIFIED = "Google account email not verified."
    ACCOUNT_DEACTIVATED = "Account is deactivated."
    INCORRECT_PASSWORD = "Incorrect password."
    INVALID_RESET_LINK = "Invalid reset link."
    INVALID_OR_EXPIRED_RESET_LINK = "Invalid or expired reset link."
    INVALID_OR_EXPIRED_TOKEN = "Invalid or expired token."
    REFRESH_TOKEN_REQUIRED = "Refresh token is required."
    ONLY_STUDENTS_ONBOARDING = "Only students have onboarding."

    # Payment
    ACTIVE_PURCHASE_EXISTS = "You already have an active purchase for this course."
    PAYMENT_GATEWAY_ERROR = "Payment gateway error. Please try again."
    PAYMENT_VERIFICATION_FAILED = "Payment verification failed."
    COURSE_NOT_LINKED = "Could not match course. Contact support."
    AMOUNT_MISMATCH = "Payment amount does not match course price."

    # Exam
    NO_QUESTIONS_AVAILABLE = "No questions available for this exam."
    EXAM_NOT_SUBMITTED = "Exam not yet submitted."
    ATTEMPT_DISQUALIFIED = "This attempt has been disqualified."
    ATTEMPT_ALREADY_SUBMITTED = "This attempt has already been submitted."
    SUBMISSION_DEADLINE_PASSED = "Submission deadline has passed. This attempt has been timed out."
    EXAM_NOT_PROCTORED = "This exam is not proctored."
    ATTEMPT_ALREADY_DISQUALIFIED = "Attempt already disqualified."

    # Feedback
    PURCHASE_REQUIRED_FOR_FEEDBACK = "You must purchase a course for this level to submit feedback."
    FEEDBACK_ALREADY_SUBMITTED = "Feedback already submitted for this session."

    # Doubt
    PURCHASE_REQUIRED_FOR_DOUBT = "You must purchase a course for this level to submit a doubt."
    TICKET_CLOSED = "This ticket is closed."
    ASSIGN_STAFF_ONLY = "Can only assign to staff or admin users."

    # Calendar
    YEAR_MONTH_REQUIRED = "year and month query params are required."

    # Search
    SEARCH_QUERY_TOO_SHORT = "Search query must be at least 2 characters."


# ── Success Messages ──


class SuccessMessage:
    LOGGED_OUT = "Logged out."
    PASSWORD_CHANGED = "Password changed successfully."
    PASSWORD_RESET_SENT = "If that email exists, a reset link has been sent."
    PASSWORD_RESET_DONE = "Password has been reset successfully."
    ONBOARDING_COMPLETED = "Onboarding completed."
    MARKED_AS_READ = "Marked as read."
    ALL_NOTIFICATIONS_READ = "All notifications marked as read."
    ALL_NOTIFICATIONS_CLEARED = "All notifications cleared."


# ── Next Action Messages ──


class NextActionMessage:
    ALL_COMPLETE = "Congratulations! You have cleared all levels."
    NO_LEVELS = "No levels available yet."

    @staticmethod
    def attempt_exam(level_order):
        return f"Attempt the Level {level_order} exam."

    @staticmethod
    def retry_exam(level_order):
        return f"Syllabus complete. Retry Level {level_order} exam."

    @staticmethod
    def complete_syllabus(level_order):
        return f"Complete the Level {level_order} syllabus."

    @staticmethod
    def complete_syllabus_to_unlock(level_order):
        return f"Complete the Level {level_order} syllabus to unlock the exam."

    @staticmethod
    def purchase_course_to_retry(level_order):
        return f"Purchase the Level {level_order} course to retry."

    @staticmethod
    def syllabus_complete_attempt(level_order):
        return f"Syllabus complete. Attempt Level {level_order} exam."


# ── Payment ──


class PaymentConstants:
    DEFAULT_CURRENCY = "INR"
    RECEIPT_FORMAT = "course_{course_id}_student_{student_id}"
    DEV_ORDER_FORMAT = "dev_order_{timestamp}_{student_pk}"


# ── Progress Thresholds ──


class ProgressConstants:
    SESSION_COMPLETION_THRESHOLD = 0.9
    DEFAULT_LEADERBOARD_LIMIT = 20
    MAX_LEADERBOARD_LIMIT = 50


# ── Search Limits ──


class SearchConstants:
    MAX_LEVELS = 5
    MAX_COURSES = 10
    MAX_SESSIONS = 10
    MIN_QUERY_LENGTH = 2


# ── Exam ──


class ExamConstants:
    SUBMISSION_GRACE_SECONDS = 30
    PERCENTAGE_DIVISOR = 100


# ── Task Configuration ──


class TaskConfig:
    # Email tasks
    EMAIL_MAX_RETRIES = 3
    EMAIL_RETRY_DELAY = 60
    EMAIL_SOFT_TIME_LIMIT = 30
    EMAIL_TIME_LIMIT = 60

    # Heavy tasks (analytics, purchases, exams)
    HEAVY_MAX_RETRIES = 2
    HEAVY_SOFT_TIME_LIMIT = 300
    HEAVY_TIME_LIMIT = 600


# ── Health Check ──


class HealthCheckConstants:
    CACHE_KEY = "_health_check"
    CACHE_VALUE = "ok"
    CACHE_TIMEOUT = 5


# ── Certificate ──


class CertificateConstants:
    NUMBER_PREFIX = "CERT-"
