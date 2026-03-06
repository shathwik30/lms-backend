from django.conf import settings
from django.core.mail import send_mail


class EmailService:
    @staticmethod
    def _send(subject, message, recipient_list):
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )

    @classmethod
    def send_welcome(cls, email, full_name):
        cls._send(
            subject="Welcome to LMS!",
            message=(
                f"Hi {full_name},\n\n"
                f"Welcome to the IIT/JEE Preparation LMS! "
                f"Your account has been created successfully.\n\n"
                f"Start by browsing available levels and purchasing your first course.\n\n"
                f"Good luck with your preparation!"
            ),
            recipient_list=[email],
        )

    @classmethod
    def send_purchase_confirmation(cls, email, full_name, course_title, amount, expires_at):
        cls._send(
            subject=f"Purchase Confirmed — {course_title}",
            message=(
                f"Hi {full_name},\n\n"
                f"Your purchase has been confirmed!\n\n"
                f"Course: {course_title}\n"
                f"Amount Paid: INR {amount}\n"
                f"Valid Until: {expires_at.strftime('%d %b %Y')}\n\n"
                f"You can now access all sessions and resources for this course. "
                f"Happy learning!"
            ),
            recipient_list=[email],
        )

    @classmethod
    def send_exam_result(cls, email, full_name, exam_title, score, total_marks, is_passed):
        result = "PASSED" if is_passed else "NOT PASSED"
        cls._send(
            subject=f"Exam Result: {exam_title} — {result}",
            message=(
                f"Hi {full_name},\n\n"
                f"Your exam has been graded.\n\n"
                f"Exam: {exam_title}\n"
                f"Score: {score}/{total_marks}\n"
                f"Result: {result}\n\n"
                + (
                    "Congratulations! You can now proceed to the next level.\n"
                    if is_passed
                    else "Don't worry — review the material and try again when ready.\n"
                )
            ),
            recipient_list=[email],
        )

    @classmethod
    def send_doubt_reply(cls, email, full_name, ticket_title, reply_author, reply_preview):
        cls._send(
            subject=f"New Reply on Your Doubt — {ticket_title}",
            message=(
                f"Hi {full_name},\n\n"
                f"You have a new reply on your doubt ticket:\n"
                f'"{ticket_title}"\n\n'
                f"Reply by {reply_author}:\n"
                f"{reply_preview}\n\n"
                f"Log in to view the full conversation and respond."
            ),
            recipient_list=[email],
        )
