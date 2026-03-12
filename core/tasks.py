import logging
import smtplib
import socket

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from core.constants import TaskConfig

logger = logging.getLogger(__name__)

_TRANSIENT_EMAIL_ERRORS = (
    smtplib.SMTPException,
    socket.timeout,
    ConnectionError,
    OSError,
)


def _run_email_task(self, email, label, send_fn):
    try:
        send_fn()
        logger.info("%s sent to %s", label, email)
    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded sending %s to %s", label, email)
        raise
    except _TRANSIENT_EMAIL_ERRORS as exc:
        logger.warning(
            "Transient error sending %s to %s (attempt %d/%d): %s",
            label,
            email,
            self.request.retries + 1,
            self.max_retries + 1,
            exc,
        )
        raise self.retry(exc=exc) from exc


@shared_task(
    bind=True,
    max_retries=TaskConfig.EMAIL_MAX_RETRIES,
    default_retry_delay=TaskConfig.EMAIL_RETRY_DELAY,
    soft_time_limit=TaskConfig.EMAIL_SOFT_TIME_LIMIT,
    time_limit=TaskConfig.EMAIL_TIME_LIMIT,
)
def send_welcome_email_task(self, email, full_name):
    from core.emails import EmailService

    _run_email_task(self, email, "welcome email", lambda: EmailService.send_welcome(email, full_name))


@shared_task(
    bind=True,
    max_retries=TaskConfig.EMAIL_MAX_RETRIES,
    default_retry_delay=TaskConfig.EMAIL_RETRY_DELAY,
    soft_time_limit=TaskConfig.EMAIL_SOFT_TIME_LIMIT,
    time_limit=TaskConfig.EMAIL_TIME_LIMIT,
)
def send_purchase_confirmation_task(self, email, full_name, level_name, amount, expires_at_iso):
    from datetime import datetime

    from core.emails import EmailService

    _run_email_task(
        self,
        email,
        "purchase confirmation",
        lambda: EmailService.send_purchase_confirmation(
            email, full_name, level_name, amount, datetime.fromisoformat(expires_at_iso)
        ),
    )


@shared_task(
    bind=True,
    max_retries=TaskConfig.EMAIL_MAX_RETRIES,
    default_retry_delay=TaskConfig.EMAIL_RETRY_DELAY,
    soft_time_limit=TaskConfig.EMAIL_SOFT_TIME_LIMIT,
    time_limit=TaskConfig.EMAIL_TIME_LIMIT,
)
def send_exam_result_task(self, email, full_name, exam_title, score, total_marks, is_passed):
    from core.emails import EmailService

    _run_email_task(
        self,
        email,
        "exam result",
        lambda: EmailService.send_exam_result(email, full_name, exam_title, score, total_marks, is_passed),
    )


@shared_task(
    bind=True,
    max_retries=TaskConfig.EMAIL_MAX_RETRIES,
    default_retry_delay=TaskConfig.EMAIL_RETRY_DELAY,
    soft_time_limit=TaskConfig.EMAIL_SOFT_TIME_LIMIT,
    time_limit=TaskConfig.EMAIL_TIME_LIMIT,
)
def send_password_reset_task(self, email, full_name, reset_url):
    from core.emails import EmailService

    _run_email_task(
        self,
        email,
        "password reset",
        lambda: EmailService.send_password_reset(email, full_name, reset_url),
    )


@shared_task(
    bind=True,
    max_retries=TaskConfig.EMAIL_MAX_RETRIES,
    default_retry_delay=TaskConfig.EMAIL_RETRY_DELAY,
    soft_time_limit=TaskConfig.EMAIL_SOFT_TIME_LIMIT,
    time_limit=TaskConfig.EMAIL_TIME_LIMIT,
)
def send_doubt_reply_task(self, email, full_name, ticket_title, reply_author, reply_preview):
    from core.emails import EmailService

    _run_email_task(
        self,
        email,
        "doubt reply notification",
        lambda: EmailService.send_doubt_reply(email, full_name, ticket_title, reply_author, reply_preview),
    )
