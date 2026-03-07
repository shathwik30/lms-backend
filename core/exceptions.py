from rest_framework.exceptions import APIException


class LevelLocked(APIException):
    status_code = 403
    default_detail = "You have not cleared the prerequisite level."
    default_code = "level_locked"


class SyllabusIncomplete(APIException):
    status_code = 403
    default_detail = "Complete the syllabus before attempting the exam."
    default_code = "syllabus_incomplete"


class LevelExpired(APIException):
    status_code = 403
    default_detail = "Your level access has expired."
    default_code = "level_expired"


class PurchaseRequired(APIException):
    status_code = 402
    default_detail = "You must purchase this level first."
    default_code = "purchase_required"


class OnboardingAlreadyAttempted(APIException):
    status_code = 403
    default_detail = "You have already taken the placement test."
    default_code = "onboarding_already_attempted"


class FinalExamAttemptsExhausted(APIException):
    status_code = 403
    default_detail = "All final exam attempts have been used."
    default_code = "final_exam_attempts_exhausted"


class SessionNotAccessible(APIException):
    status_code = 403
    default_detail = "Complete prior sessions and weeks before accessing this session."
    default_code = "session_not_accessible"
