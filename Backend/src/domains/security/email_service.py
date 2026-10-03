"""
SMTP email service for sending account verification and password reset emails.
"""

import logging
import smtplib
from email.mime.text import MIMEText

from src.sdk.config import get_settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, html_body: str) -> None:
    settings = get_settings()
    if not settings.SMTP_HOST:
        logger.warning(
            "SMTP not configured - email not sent. to=%s subject=%s",
            to_email,
            subject,
        )
        return

    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        logger.exception("Email sending failed: %s", e)
