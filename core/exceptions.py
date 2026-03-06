from rest_framework.exceptions import APIException


class LevelLocked(APIException):
    status_code = 403
    default_detail = "You have not cleared the prerequisite level."
    default_code = "level_locked"


class SyllabusIncomplete(APIException):
    status_code = 403
    default_detail = "Complete the syllabus before attempting the exam."
    default_code = "syllabus_incomplete"


class CourseExpired(APIException):
    status_code = 403
    default_detail = "Your course access has expired."
    default_code = "course_expired"


class PurchaseRequired(APIException):
    status_code = 402
    default_detail = "You must purchase this course first."
    default_code = "purchase_required"
