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


@shared_task(
    bind=True,
    max_retries=TaskConfig.EMAIL_MAX_RETRIES,
    default_retry_delay=TaskConfig.EMAIL_RETRY_DELAY,
    soft_time_limit=TaskConfig.EMAIL_SOFT_TIME_LIMIT,
    time_limit=TaskConfig.EMAIL_TIME_LIMIT,
)
def send_welcome_email_task(self, email, full_name):
    try:
        from core.emails import EmailService

        EmailService.send_welcome(email, full_name)
        logger.info("Welcome email sent to %s", email)
    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded sending welcome email to %s", email)
        raise
    except _TRANSIENT_EMAIL_ERRORS as exc:
        logger.warning(
            "Transient error sending welcome email to %s (attempt %d/%d): %s",
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
def send_purchase_confirmation_task(self, email, full_name, level_name, amount, expires_at_iso):
    try:
        from datetime import datetime

        from core.emails import EmailService

        expires_at = datetime.fromisoformat(expires_at_iso)
        EmailService.send_purchase_confirmation(email, full_name, level_name, amount, expires_at)
        logger.info("Purchase confirmation email sent to %s", email)
    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded sending purchase confirmation to %s", email)
        raise
    except _TRANSIENT_EMAIL_ERRORS as exc:
        logger.warning(
            "Transient error sending purchase confirmation to %s (attempt %d/%d): %s",
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
def send_exam_result_task(self, email, full_name, exam_title, score, total_marks, is_passed):
    try:
        from core.emails import EmailService

        EmailService.send_exam_result(email, full_name, exam_title, score, total_marks, is_passed)
        logger.info("Exam result email sent to %s", email)
    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded sending exam result to %s", email)
        raise
    except _TRANSIENT_EMAIL_ERRORS as exc:
        logger.warning(
            "Transient error sending exam result to %s (attempt %d/%d): %s",
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
def send_password_reset_task(self, email, full_name, reset_url):
    try:
        from core.emails import EmailService

        EmailService.send_password_reset(email, full_name, reset_url)
        logger.info("Password reset email sent to %s", email)
    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded sending password reset to %s", email)
        raise
    except _TRANSIENT_EMAIL_ERRORS as exc:
        logger.warning(
            "Transient error sending password reset to %s (attempt %d/%d): %s",
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
def send_doubt_reply_task(self, email, full_name, ticket_title, reply_author, reply_preview):
    try:
        from core.emails import EmailService

        EmailService.send_doubt_reply(email, full_name, ticket_title, reply_author, reply_preview)
        logger.info("Doubt reply notification sent to %s", email)
    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded sending doubt reply notification to %s", email)
        raise
    except _TRANSIENT_EMAIL_ERRORS as exc:
        logger.warning(
            "Transient error sending doubt reply notification to %s (attempt %d/%d): %s",
            email,
            self.request.retries + 1,
            self.max_retries + 1,
            exc,
        )
        raise self.retry(exc=exc) from exc
