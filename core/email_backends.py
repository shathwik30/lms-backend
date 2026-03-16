from collections.abc import Sequence
from typing import Any, cast

import resend
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend
from resend.emails._emails import Emails


class ResendEmailBackend(BaseEmailBackend):
    """Django email backend that sends via the Resend HTTP API."""

    def __init__(self, fail_silently: bool = False, **kwargs: Any) -> None:
        super().__init__(fail_silently=fail_silently, **kwargs)
        resend.api_key = settings.RESEND_API_KEY

    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        sent = 0
        for message in email_messages:
            try:
                params: dict[str, Any] = {
                    "from": message.from_email,
                    "to": list(message.to),
                    "subject": message.subject,
                }
                if message.body:
                    params["text"] = message.body
                if hasattr(message, "alternatives") and message.alternatives:
                    for content, mimetype in message.alternatives:
                        if mimetype == "text/html":
                            params["html"] = content
                if message.cc:
                    params["cc"] = list(message.cc)
                if message.bcc:
                    params["bcc"] = list(message.bcc)
                if message.reply_to:
                    params["reply_to"] = list(message.reply_to)

                resend.Emails.send(cast(Emails.SendParams, params))
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent
